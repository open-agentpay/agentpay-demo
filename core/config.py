import os
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Agent Key (API Key issued by AgentPay Gateway)
    AGENT_KEY: str = Field(
        default="apk_live_209aaf0b44c4fbd955457368ab63a2a745ceea0ccd107ad2",
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
    GATEWAY_PORT: int = 8000
    GATEWAY_URL: str = "http://127.0.0.1:8000/gateway"

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
    OPENAI_MODEL: str = "gpt-4o"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()


def base_units_to_usdc(amount: int) -> float:
    return amount / 1_000_000.0


def format_usdc(amount: int) -> str:
    return f"${base_units_to_usdc(amount):.4f} USDC"
