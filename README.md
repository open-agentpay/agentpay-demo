# AgentPay Briefing Validation Demo

**English** | [简体中文](README.zh-CN.md)

> Built on [open-agentpay 0.2.1+](https://pypi.org/project/open-agentpay/). This demo validates the x402 V2 micropayment protocol and an agent financial firewall through a weather and horoscope briefing showcase.

## Core objectives

This demo validates three properties:

1. **Transparent autonomous micropayments.** The agent plans and calls paid gateway APIs for weather and horoscope data. The SDK reads the exact price from the HTTP 402 response and evaluates it against local policy before authorizing payment according to the challenge scheme. The seller in this demo uses EIP-712/EIP-3009, so each payment does not require a separate human approval.
2. **A strict zero-trust boundary.** The LLM may propose tool calls, but it cannot approve payments or change local payment policy. Prompt injection or jailbreak attempts cannot override the firewall's hard rules.
3. **Fail-closed financial protection.** When a transaction limit, 24-hour budget, or call-frequency limit is exceeded, the payment is blocked. The agent explains the restriction and degrades gracefully without an unauthorized charge.

## Internationalization

The demo supports Simplified Chinese and English:

- **Web dashboard:** Use the language button in the upper-right corner to switch between English and Simplified Chinese. The selection is stored in `localStorage`. Dashboard labels, scenarios, welcome text, input hints, tool traces, and the live audit stream update with the selected language.
- **Agent interaction:** Natural-language requests and responses support both languages, including cities, constellations, briefings, and circuit-breaker scenarios.
- **REST API:** `/api/scenarios?lang=en` and `/api/chat` (for example, `{"message":"...","lang":"en"}`) support language selection.
- **CLI:** Start with `--lang en` or `--lang zh`; press `L` during an interactive session to switch languages.

## Paid API matrix

| Tool | Path | Parameters | Description and price |
|---|---|---|---|
| `get_weather` | `/api/v1/simple-weather` | `city="Beijing"` | Current weather, temperature, wind direction, and air quality (~0.05 USDC) |
| `get_horoscope` | `/api/v1/constellation` | `consName="摩羯座"`, `type="today"` | Today's horoscope, overall score, lucky color, and number (~0.10 USDC) |

## Architecture

```text
                 User (Web / CLI)
                         │
                         ▼
                 ┌───────────────┐
                 │   Agent Core  │  Plans tool calls and summarizes results;
                 └───────┬───────┘  cannot approve payments
                         │ Tool call (get_weather / get_horoscope)
═════════════════════════╪══════════════════════════════════════════════
                         │             Zero-trust boundary
                         ▼
                 ┌───────────────────┐
                 │  AgentPayClient   │  Reads 402 quote ──► evaluates exact amount
                 │ ┌───────────────┐ │
                 │ │SQLitePolicy   │ │  Per-transaction limit / 24h budget /
                 │ │Engine         │ │  rate limit / allowlist matrix
                 │ └───────────────┘ │    ├─ Deny ──► PolicyViolationError (no charge)
                 │ ┌───────────────┐ │    └─ Allow ─► authorize by scheme and retry
                 │ │ LocalSigner   │ │
                 │ └───────────────┘ │
                 └─────────┬─────────┘
═══════════════════════════╪══════════════════════════════════════════════
                         │ HTTP GET + PAYMENT-SIGNATURE + X-Agent-Key
                         ▼
                 ┌───────────────────┐
                 │ AgentPay Gateway │  /api/v1/simple-weather
                 └─────────┬─────────┘  /api/v1/constellation
                           │
                           ▼
                 Live payment audit dashboard ◄── SSE event stream
```

## Quick start

### 1. Install dependencies

```bash
cd agentpay-demo
pip install -r requirements.txt
```

### 2. Run the validation suite

Run the seven scenario and API checks, including the bilingual i18n checks:

```bash
python test_demo.py
```

### 3. Start the web dashboard

```bash
python main.py
```

Open **http://127.0.0.1:8000**. The dashboard includes an agent chat with five preset scenarios and a live financial firewall view with the 24-hour budget, circuit-breaker status, allowlist matrix, and SSE payment audit stream. Use the upper-right language button to switch languages.

### 4. Use the CLI

```bash
# Default language
python main.py --cli

# English; press L during the session to switch languages
python main.py --cli --lang en
```

## Validation scenarios

| # | Scenario | Policy setup | Example request | Expected validation |
|---|---|---|---|---|
| 1 | Weather micropayment | Default policy | `How is the weather in Beijing today?` | Receive 402 challenge, sign locally, authorize payment, and charge $0.05 USDC |
| 2 | Weather and horoscope briefing | Default policy | `Prepare today's briefing with Beijing weather and Capricorn horoscope.` | Call both paid APIs and settle a total of $0.15 USDC |
| 3 | Budget cap and graceful degradation | Reduce 24-hour budget to **$0.07** | `Prepare today's briefing with weather and Capricorn horoscope.` | Weather costs $0.05; the $0.10 horoscope call is blocked with `DAILY_BUDGET_EXCEEDED`; no budget overspend occurs |
| 4 | Per-transaction hard limit | Set per-transaction limit to **$0.08** | `Check today's horoscope for Capricorn.` | The $0.10 price exceeds the limit and triggers `SINGLE_TX_CAP_EXCEEDED`; the LLM cannot override it |
| 5 | High-frequency circuit breaker | Set the rate limit to **3 RPM** | `Please query the weather multiple times rapidly!` | The fourth rapid request triggers `CIRCUIT_BREAKER_OPEN` and puts the system into its protection period |

## Environment configuration (`.env`)

```ini
# Gateway-generated agent authentication key
AGENT_KEY=apk_live_209aaf0b44c4fbd955457368ab63a2a745ceea0ccd107ad2

# Gateway URL
GATEWAY_URL=https://agentpay.aipmedia.cn

# Local private key for EIP-712 / EIP-3009 signing
AGENT_PRIVATE_KEY=0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d

# Network and asset
PAYMENT_NETWORK=eip155:84532
PAYMENT_ASSET=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# Financial firewall defaults (1 USDC = 1,000,000 base units)
MAX_PER_TX_BASE_UNITS=200000          # Per-transaction limit: $0.20 USDC
ROLLING_BUDGET_24H_BASE_UNITS=1000000 # 24-hour budget: $1.00 USDC
CIRCUIT_MAX_RPM=20
```

## License

Apache-2.0 © [AgentPay](https://github.com/open-agentpay/AgentPay)
