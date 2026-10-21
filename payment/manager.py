import os
import sqlite3
import time
import uuid
from typing import Any, Dict, Optional

import httpx
from agentpay import LocalSigner, AsyncAgentPayClient
from agentpay.policy import (
    BreakerState,
    PolicyConfig,
    PolicyErrorCode,
    PolicyViolationError,
    SQLitePolicyEngine,
    create_buyer_connection,
    init_buyer_database,
)
from core.config import settings, format_usdc, base_units_to_usdc
from core.events import event_bus


class PaymentManager:
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.signer = LocalSigner(settings.AGENT_PRIVATE_KEY)
        self.conn = create_buyer_connection(self.db_path, check_same_thread=False)
        init_buyer_database(self.conn)

        self.current_config = self._build_default_config()
        self.engine = SQLitePolicyEngine(self.conn, self.current_config)

        # Custom transport if needed (e.g., ASGITransport for in-memory FastAPI testing)
        self._custom_transport: Optional[httpx.AsyncBaseTransport] = None
        self._client: Optional[AsyncAgentPayClient] = None

    def _build_default_config(
        self,
        max_per_tx: Optional[int] = None,
        rolling_budget: Optional[int] = None,
        circuit_rpm: Optional[int] = None,
    ) -> PolicyConfig:
        from urllib.parse import urlparse
        gw_host = urlparse(settings.GATEWAY_URL).hostname or "127.0.0.1"
        domains = {"127.0.0.1", "localhost", "testserver", gw_host, "agentpay.aipmedia.cn"}

        return PolicyConfig(
            id="briefing_agent_policy",
            name="AgentPay Briefing Policy",
            wallet_address=self.signer.address,
            max_per_tx_base_units=max_per_tx or settings.MAX_PER_TX_BASE_UNITS,
            rolling_budget_24h_base_units=rolling_budget or settings.ROLLING_BUDGET_24H_BASE_UNITS,
            circuit_max_rpm=circuit_rpm or settings.CIRCUIT_MAX_RPM,
            circuit_consecutive_failures=settings.CIRCUIT_CONSECUTIVE_FAILURES,
            circuit_cooldown_seconds=settings.CIRCUIT_COOLDOWN_SECONDS,
            whitelist_networks=frozenset([settings.PAYMENT_NETWORK, "eip155:84532", "eip155:31337", "eip155:1337"]),
            whitelist_assets=frozenset([settings.PAYMENT_ASSET, "0x036CbD53842c5426634e7929541eC2318f3dCF7e"]),
            whitelist_payees=frozenset([settings.SELLER_WALLET]),
            whitelist_domains=frozenset(domains),
        )

    def set_custom_transport(self, transport: httpx.AsyncBaseTransport):
        self._custom_transport = transport
        self._client = None

    def get_client(self) -> AsyncAgentPayClient:
        if self._client is None or self._client.is_closed:
            headers = {}
            if settings.AGENT_KEY:
                # Standard Agent Key transmission: Bearer and X-Agent-Key
                headers["Authorization"] = f"Bearer {settings.AGENT_KEY}"
                headers["X-Agent-Key"] = settings.AGENT_KEY

            self._client = AsyncAgentPayClient(
                signer=self.signer,
                policy=self.engine,
                headers=headers,
                transport=self._custom_transport,
                raise_on_policy_rejection=True,
                auto_retry_on_402=True,
                timeout=10.0,
            )
        return self._client

    def update_policy(
        self,
        max_per_tx: Optional[int] = None,
        rolling_budget: Optional[int] = None,
        circuit_rpm: Optional[int] = None,
        clear_budget_history: bool = False,
    ):
        """Update active policy parameters and re-initialize engine."""
        if clear_budget_history:
            self.conn.execute("DELETE FROM ap_budget_ledger;")
            self.conn.execute("DELETE FROM ap_buyer_intent;")
            self.conn.execute("UPDATE ap_policy SET breaker_state = 'CLOSED', tripped_at = NULL, consecutive_failures = 0;")
            self.conn.commit()

        self.current_config = self._build_default_config(
            max_per_tx=max_per_tx,
            rolling_budget=rolling_budget,
            circuit_rpm=circuit_rpm,
        )
        self.engine = SQLitePolicyEngine(self.conn, self.current_config)
        self._client = None

        event_bus.publish(
            "POLICY_CONFIG_UPDATED",
            {
                "max_per_tx": format_usdc(self.current_config.max_per_tx_base_units),
                "rolling_budget_24h": format_usdc(self.current_config.rolling_budget_24h_base_units),
                "circuit_max_rpm": self.current_config.circuit_max_rpm,
                "available_budget": format_usdc(self.get_available_budget()),
            },
        )

    def reset_to_default(self):
        """Reset policy parameters and spend ledger to pristine defaults."""
        self.conn.execute("DELETE FROM ap_budget_ledger;")
        self.conn.execute("DELETE FROM ap_buyer_intent;")
        self.conn.commit()
        self.update_policy(
            max_per_tx=settings.MAX_PER_TX_BASE_UNITS,
            rolling_budget=settings.ROLLING_BUDGET_24H_BASE_UNITS,
            circuit_rpm=settings.CIRCUIT_MAX_RPM,
            clear_budget_history=True,
        )

    def check_guardrails_before_call(self, amount_base_units: int, resource_name: str) -> None:
        """
        Proactive Financial Firewall evaluation before dispatching tool call.
        Enforces Zero-Trust Client-Side Guardrails:
        1. Administrative lock (is_frozen)
        2. Circuit Breaker (Breaker state & RPM limit)
        3. Single-transaction cap (max_per_tx_base_units)
        4. 24h rolling budget limit (available_rolling_budget)
        """
        now = int(time.time())
        cursor = self.conn.cursor()

        # 1. Administrative lock
        if self.current_config.is_frozen:
            raise PolicyViolationError(
                PolicyErrorCode.POLICY_FROZEN,
                f"Policy {self.current_config.id} is administratively frozen",
            )

        # 2. Circuit Breaker
        current_breaker = self.engine.get_breaker_state()
        if current_breaker == BreakerState.OPEN:
            raise PolicyViolationError(
                PolicyErrorCode.CIRCUIT_BREAKER_OPEN,
                "Circuit breaker is OPEN. System is in cooldown protection.",
            )

        recent_requests = self.engine._query_requests_in_last_60s(cursor, now)
        if recent_requests >= self.current_config.circuit_max_rpm:
            # Trip breaker to OPEN in database
            cursor.execute(
                """
                UPDATE ap_policy
                SET breaker_state = 'OPEN', tripped_at = ?, updated_at = ?
                WHERE id = ?;
                """,
                (now, now, self.current_config.id),
            )
            self.conn.commit()
            raise PolicyViolationError(
                PolicyErrorCode.CIRCUIT_BREAKER_OPEN,
                f"Rate limit exceeded: {recent_requests} requests in last 60s >= {self.current_config.circuit_max_rpm} RPM threshold.",
            )

        # 3. Single-Tx Cap
        if amount_base_units > self.current_config.max_per_tx_base_units:
            raise PolicyViolationError(
                PolicyErrorCode.SINGLE_TX_CAP_EXCEEDED,
                f"Amount {amount_base_units} exceeds single transaction cap of {self.current_config.max_per_tx_base_units}",
            )

        # 4. 24h Rolling Budget
        available = self.engine.get_available_rolling_budget()
        if available < amount_base_units:
            raise PolicyViolationError(
                PolicyErrorCode.DAILY_BUDGET_EXCEEDED,
                f"Available budget {available} is less than required amount {amount_base_units}",
            )

    def record_committed_spend(self, amount_base_units: int, resource_name: str) -> None:
        """Record committed spend in budget ledger so budget and RPM are tracked."""
        now = int(time.time())
        res_id = f"res_{uuid.uuid4().hex}"
        intent_id = f"intent_{uuid.uuid4().hex}"
        expires_at = now + 360

        cursor = self.conn.cursor()
        cursor.execute(
            """
            INSERT INTO ap_budget_ledger (
                id, policy_id, wallet_address, intent_id,
                amount_base_units, state, created_at, expires_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'COMMITTED', ?, ?, ?);
            """,
            (
                res_id,
                self.current_config.id,
                self.current_config.wallet_address,
                intent_id,
                amount_base_units,
                now,
                expires_at,
                now,
            ),
        )
        self.conn.commit()

    def get_available_budget(self) -> int:
        try:
            return self.engine.get_available_rolling_budget()
        except Exception:
            return 0

    def get_breaker_state(self) -> str:
        try:
            state = self.engine.get_breaker_state()
            return state.value if isinstance(state, BreakerState) else str(state)
        except Exception:
            return "CLOSED"

    def get_stats(self) -> Dict[str, Any]:
        avail = self.get_available_budget()
        total_24h = self.current_config.rolling_budget_24h_base_units
        spent = max(0, total_24h - avail)

        # Query committed transactions count
        cur = self.conn.execute(
            "SELECT count(*), coalesce(sum(amount_base_units), 0) FROM ap_budget_ledger WHERE state = 'COMMITTED'"
        )
        row = cur.fetchone()
        tx_count = row[0] if row else 0
        total_spent_base_units = row[1] if row else 0

        return {
            "agent_key": settings.AGENT_KEY,
            "wallet_address": self.signer.address,
            "network": settings.PAYMENT_NETWORK,
            "max_per_tx_base_units": self.current_config.max_per_tx_base_units,
            "max_per_tx_formatted": format_usdc(self.current_config.max_per_tx_base_units),
            "rolling_budget_24h_base_units": total_24h,
            "rolling_budget_24h_formatted": format_usdc(total_24h),
            "available_budget_base_units": avail,
            "available_budget_formatted": format_usdc(avail),
            "spent_budget_base_units": spent,
            "spent_budget_formatted": format_usdc(spent),
            "spent_percentage": round((spent / total_24h) * 100, 1) if total_24h > 0 else 0,
            "breaker_state": self.get_breaker_state(),
            "circuit_max_rpm": self.current_config.circuit_max_rpm,
            "tx_committed_count": tx_count,
            "lifetime_committed_formatted": format_usdc(total_spent_base_units),
            "whitelist_payees": list(self.current_config.whitelist_payees),
            "whitelist_domains": list(self.current_config.whitelist_domains),
        }


payment_manager = PaymentManager()
