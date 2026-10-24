import logging
import re
from typing import Any, Dict, Optional

import httpx
from agentpay import AsyncAgentPayClient, LocalSigner
from agentpay.policy import (
    BreakerState,
    PolicyConfig,
    SQLitePolicyEngine,
    create_buyer_connection,
    init_buyer_database,
)
from core.config import settings, format_usdc, base_units_to_usdc
from core.events import event_bus

_http_debug_logger = logging.getLogger("agentpay.demo.http")
_SENSITIVE_HEADER = re.compile(
    r"authorization|proxy-authorization|cookie|set-cookie|api[-_]?key|agent[-_]?key|"
    r"payment[-_]signature|payment[-_]authorization|secret|token",
    re.IGNORECASE,
)


def _debug_headers(headers: httpx.Headers) -> list[tuple[str, str]]:
    """Keep the full header list while masking values that can authorize requests."""
    return [
        (name, "<redacted>" if _SENSITIVE_HEADER.search(name) else value)
        for name, value in headers.multi_items()
    ]


class _DebugHTTPTransport(httpx.AsyncBaseTransport):
    """Log each actual network exchange, including the 402 and signed retry."""

    def __init__(self, inner: httpx.AsyncBaseTransport):
        self._inner = inner

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        if settings.HTTP_DEBUG_LOGGING:
            body = await request.aread()
            _http_debug_logger.info(
                "HTTP REQUEST OUTBOUND\n%s %s\nheaders=%r\nbody=%s",
                request.method,
                request.url,
                _debug_headers(request.headers),
                body.decode("utf-8", errors="replace"),
            )
        try:
            response = await self._inner.handle_async_request(request)
        except Exception as exc:
            if settings.HTTP_DEBUG_LOGGING:
                _http_debug_logger.error(
                    "HTTP REQUEST FAILED (Network / Transport Exception)\n%s %s\nheaders=%r\nerror=%s: %s",
                    request.method,
                    request.url,
                    _debug_headers(request.headers),
                    type(exc).__name__,
                    exc,
                    exc_info=True,
                )
            raise

        if settings.HTTP_DEBUG_LOGGING:
            response_body = await response.aread()
            _http_debug_logger.info(
                "HTTP RESPONSE INBOUND\n%s %s\nstatus=%s\nheaders=%r\nbody=%s",
                request.method,
                request.url,
                response.status_code,
                _debug_headers(response.headers),
                response_body.decode("utf-8", errors="replace"),
            )
        return response

    async def aclose(self) -> None:
        await self._inner.aclose()


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
        return PolicyConfig(
            id="briefing_agent_policy",
            name="AgentPay Briefing Policy",
            wallet_address=self.signer.address,
            max_per_tx_base_units=max_per_tx or settings.MAX_PER_TX_BASE_UNITS,
            rolling_budget_24h_base_units=rolling_budget or settings.ROLLING_BUDGET_24H_BASE_UNITS,
            circuit_max_rpm=circuit_rpm or settings.CIRCUIT_MAX_RPM,
            circuit_consecutive_failures=settings.CIRCUIT_CONSECUTIVE_FAILURES,
            circuit_cooldown_seconds=settings.CIRCUIT_COOLDOWN_SECONDS,
            whitelist_networks=frozenset([settings.PAYMENT_NETWORK, "eip155:31337", "eip155:1337", "eip155:84532"]),
            whitelist_assets=frozenset([settings.PAYMENT_ASSET]),
            whitelist_payees=frozenset([settings.SELLER_WALLET]),
            whitelist_domains=frozenset(["127.0.0.1", "localhost", "testserver", "agentpay.aipmedia.cn"]),
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

            inner_transport = self._custom_transport or httpx.AsyncHTTPTransport()
            transport = (
                _DebugHTTPTransport(inner_transport)
                if settings.HTTP_DEBUG_LOGGING
                else inner_transport
            )
            self._client = AsyncAgentPayClient(
                signer=self.signer,
                policy=self.engine,
                headers=headers,
                # Skip fixed credential estimates: evaluate the exact x402 challenge price instead.
                # This demo's seller returns EIP-3009 challenges; the SDK dispatches by scheme.
                wallet_challenge_mode=bool(settings.AGENT_KEY),
                transport=transport,
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
        try:
            self.engine.reset_breaker()
        except Exception:
            pass

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
