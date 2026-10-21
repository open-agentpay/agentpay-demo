# AgentPay 简报验证 Demo

[English](README.md) | **简体中文**

> 基于 [open-agentpay 0.2.1+](https://pypi.org/project/open-agentpay/)。本 Demo 通过天气与星座简报场景，验证 x402 V2 微支付协议和智能体金融防火墙。

## 核心目标

本 Demo 验证以下三项能力：

1. **透明的自主微支付。** Agent 自主规划并调用网关上的付费接口，查询天气和星座信息。SDK 先从 HTTP 402 响应读取准确价格，再交由本地策略评估，最后按照 challenge scheme 授权。本 Demo 的卖方使用 EIP-712/EIP-3009，无需人工逐笔审批。
2. **严格的 Zero-Trust 权限隔离。** LLM 可以提议调用工具，但无权批准付款或修改本地付款策略。即使遇到 Prompt 注入或越狱，也无法突破金融防火墙的硬规则。
3. **Fail-Closed 资金保护。** 当单笔限额、24 小时预算或调用频率超限时，系统会阻止付款。Agent 如实说明限制并优雅降级，不会产生未经授权的扣款。

## 国际化支持

Demo 支持简体中文和英文：

- **Web 可视化面板：** 通过右上角的语言按钮切换中英文，选择会保存到 `localStorage`。看板标题、预设场景、欢迎指引、输入提示、工具调用轨迹和实时审计流会随语言切换。
- **智能体交互：** 支持中英文自然语言请求与回复，包括城市、星座、简报和熔断场景。
- **REST API：** `/api/scenarios?lang=en` 和 `/api/chat`（例如 `{"message":"...","lang":"en"}`）支持语言选择。
- **CLI：** 使用 `--lang en` 或 `--lang zh` 指定语言；交互过程中按 `L` 可切换语言。

## 付费 API 清单

| 工具 | 路径 | 参数 | 说明与价格 |
|---|---|---|---|
| `get_weather` | `/api/v1/simple-weather` | `city="北京"` | 查询城市天气、温度、风向与空气质量（约 0.05 USDC） |
| `get_horoscope` | `/api/v1/constellation` | `consName="摩羯座"`, `type="today"` | 查询今日运势、综合分、幸运色和幸运数字（约 0.10 USDC） |

## 架构

```text
                 用户（Web / CLI）
                         │
                         ▼
                 ┌───────────────┐
                 │   Agent Core  │  规划工具调用并汇总结果；无权批准付款
                 └───────┬───────┘
                         │ 工具调用（get_weather / get_horoscope）
═════════════════════════╪══════════════════════════════════════════════
                         │             Zero-Trust 隔离边界
                         ▼
                 ┌───────────────────┐
                 │  AgentPayClient   │  获取 402 报价 ──► 按确切金额评估策略
                 │ ┌───────────────┐ │
                 │ │SQLitePolicy   │ │  单笔限额 / 24 小时预算 /
                 │ │Engine         │ │  频率限制 / 白名单矩阵
                 │ └───────────────┘ │    ├─ 拒绝 ──► PolicyViolationError（零扣费）
                 │ ┌───────────────┐ │    └─ 放行 ──► 按 scheme 授权并重试
                 │ │ LocalSigner   │ │
                 │ └───────────────┘ │
                 └─────────┬─────────┘
═══════════════════════════╪══════════════════════════════════════════════
                         │ HTTP GET + PAYMENT-SIGNATURE + X-Agent-Key
                         ▼
                 ┌───────────────────┐
                 │ AgentPay 网关     │  /api/v1/simple-weather
                 └─────────┬─────────┘  /api/v1/constellation
                           │
                           ▼
                 实时支付审计看板 ◄── SSE 事件流
```

## 快速上手

### 1. 安装依赖

```bash
cd agentpay-demo
pip install -r requirements.txt
```

### 2. 运行验证套件

运行七大场景及 API 验证，包括双语 i18n 验证：

```bash
python test_demo.py
```

### 3. 启动 Web 看板

```bash
python main.py
```

打开 **http://127.0.0.1:8000**。看板包含带有五个预设场景的智能体对话窗口，以及实时金融防火墙视图，其中显示 24 小时预算、熔断状态、白名单矩阵和 SSE 支付审计流。使用右上角语言按钮切换中英文。

### 4. 使用 CLI

```bash
# 默认语言
python main.py --cli

# 英文模式；交互时按 L 可切换语言
python main.py --cli --lang en
```

## 验证场景

| # | 场景 | 策略设置 | 示例请求 | 验证重点 |
|---|---|---|---|---|
| 1 | 天气微支付 | 默认策略 | `今天北京天气怎么样？` | 获取 402 挑战、本地签名、付款放行并扣款 $0.05 USDC |
| 2 | 天气与星座简报 | 默认策略 | `准备今天的简报，包含北京天气和摩羯座运势。` | 连续调用两个付费 API，合计结算 $0.15 USDC |
| 3 | 预算拦截与优雅降级 | 将 24 小时预算缩至 **$0.07** | `准备今天的简报，包含天气和摩羯座运势。` | 天气费用为 $0.05；星座费用 $0.10 的请求被 `DAILY_BUDGET_EXCEEDED` 拦截，预算不会超支 |
| 4 | 单笔限额硬拦截 | 将单笔限额设为 **$0.08** | `查询摩羯座今日运势。` | $0.10 的价格超过限额并触发 `SINGLE_TX_CAP_EXCEEDED`；LLM 无法越权批准 |
| 5 | 高频调用熔断 | 将频率上限设为 **3 RPM** | `请快速连续查询天气状况！` | 第四次快速请求触发 `CIRCUIT_BREAKER_OPEN`，系统进入保护期 |

## 环境配置（`.env`）

```ini
# 网关生成的 Agent 身份鉴权密钥
AGENT_KEY=apk_live_209aaf0b44c4fbd955457368ab63a2a745ceea0ccd107ad2

# 网关地址
GATEWAY_URL=https://agentpay.aipmedia.cn

# 用于 EIP-712 / EIP-3009 签名的本地私钥
AGENT_PRIVATE_KEY=0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d

# 网络与资产
PAYMENT_NETWORK=eip155:84532
PAYMENT_ASSET=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# 金融防火墙默认策略（1 USDC = 1,000,000 个基础单位）
MAX_PER_TX_BASE_UNITS=200000          # 单笔上限：$0.20 USDC
ROLLING_BUDGET_24H_BASE_UNITS=1000000 # 24 小时预算：$1.00 USDC
CIRCUIT_MAX_RPM=20
```

## License

Apache-2.0 © [AgentPay](https://github.com/open-agentpay/AgentPay)
