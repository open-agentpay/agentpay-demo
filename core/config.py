import logging
import os
import re
from typing import Any
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings

# Configure root logger format so all components output structured, timestamped logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_logger = logging.getLogger("agentpay.demo.config")
_EVM_ADDRESS_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


class Settings(BaseSettings):
    # Agent Key (API Key issued by AgentPay Gateway)
    AGENT_KEY: str = Field(
        default="",
        description="Agent key issued by AgentPay gateway for caller authentication",
    )

    # Agent Wallet Private Key (for EIP-712 / EIP-3009 offline signing)
    AGENT_PRIVATE_KEY: str = Field(
        default="0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d",
        description="Private key of agent local signer (Anvil test key by default)",
    )

    # Network & Asset (CAIP-2 format)
    PAYMENT_NETWORK: str = Field(default="eip155:421614", description="Arbitrum Sepolia CAIP-2 id")
    PAYMENT_ASSET: str = Field(
        default="0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d",
        description="USDC contract address on Sepolia",
    )
    PAYMENT_ASSET_SYMBOL: str = Field(default="USDC")
    SELLER_WALLET: str = Field(
        default="0x1111111111111111111111111111111111111111",
        description="Seller address receiving payments",
    )

    # Gateway URLs
    GATEWAY_HOST: str = "127.0.0.1"
    GATEWAY_PORT: int = 8090
    GATEWAY_URL: str = "http://127.0.0.1:8090/gateway"
    FACILITATOR_URL: str = "http://127.0.0.1:8001"

    # Financial Firewall Defaults (in base units: 1 USDC = 1_000_000)
    MAX_PER_TX_BASE_UNITS: int = 200_000  # $0.200 USDC
    ROLLING_BUDGET_24H_BASE_UNITS: int = 1_000_000  # $1.000 USDC
    CIRCUIT_MAX_RPM: int = 20
    CIRCUIT_CONSECUTIVE_FAILURES: int = 5
    CIRCUIT_COOLDOWN_SECONDS: int = 120

    # LLM Settings
    LLM_PROVIDER: str = "mock"  # mock | anthropic | openai
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "deepseek-flash"

    # HTTP Debug Logging (logs raw HTTP request/response headers & body)
    HTTP_DEBUG_LOGGING: bool = Field(
        default=False,
        validation_alias=AliasChoices("HTTP_DEBUG_LOGGING", "HTTP_DEBUG", "LOG_HTTP_DEBUG", "DEBUG_HTTP"),
        description="Whether to log detailed HTTP outbound/inbound request and response headers/bodies. Defaults to False.",
    )

    @field_validator("PAYMENT_ASSET", mode="before")
    @classmethod
    def validate_payment_asset(cls, v: Any) -> str:
        if not isinstance(v, str):
            return str(v)
        val = v.strip()
        if val.upper() == "USDC":
            corrected = "0x75faf114eafb1BDbe2F0316DF893fd58CE46AA4d"
            _logger.warning(
                "⚠️ [配置纠偏] PAYMENT_ASSET 被填成了代币符号 'USDC'，而非 EVM 合约地址！"
                "EIP-3009 链上结算要求 0x 开头的 40 位十六进制地址。\n"
                f"   -> 自动纠偏为标准测试网 USDC 合约地址: {corrected}\n"
                "   -> 提示: 代币显示符号请配置在 PAYMENT_ASSET_SYMBOL=USDC 中。"
            )
            return corrected

        if not _EVM_ADDRESS_RE.match(val):
            _logger.warning(
                f"⚠️ [配置警告] PAYMENT_ASSET ('{val}') 不是标准的 0x+40位十六进制 EVM 合约地址！"
                "底层 AgentPay 协议校验 (X402ValidationError) 可能会因此阻止支付。"
            )
        return val

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

if not settings.HTTP_DEBUG_LOGGING:
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("agentpay.demo.http").setLevel(logging.WARNING)


def base_units_to_usdc(amount: int) -> float:
    return amount / 1_000_000.0


def format_usdc(amount: int) -> str:
    return f"${base_units_to_usdc(amount):.4f} USDC"
