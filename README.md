# AgentPay 简报验证 Demo (Weather & Constellation Showcase)

> **基于 [open-agentpay 0.2.0](https://pypi.org/project/open-agentpay/)**  
> 官方微支付协议（x402 V2）与智能体金融防火墙（Financial Firewall）落地验证套件。  
> **✨ 支持中英双语国际化 (Bilingual i18n Supported: 🇨🇳 中文 / 🇺🇸 English)**

---

## 🌟 Demo 核心目标与要证明的三件事 / Core Objectives

1. **自主透明的微支付（Autonomous Micro-Payments）**：  
   Agent 自主规划并调用网关上的付费接口（天气查询、星座运势），底层通过 HTTP 402 与 EIP-712/3009 离线签名完成代付放行，**无需人工逐笔审批确认**。
2. **严格的 Zero-Trust 权限隔离（Zero-Trust Boundary）**：  
   LLM 只能“提议”调用工具，**无权批准或篡改本地付款策略**。即使 LLM 遭到 Prompt 注入或越狱，也无法突破本地金融防火墙的硬规则约束。
3. **Fail-Closed 资金零损失保障（Financial Firewall Protection）**：  
   单笔超限、24h 预算超限、异常高频调用时，系统严格实行 Fail-Closed（零资金扣减），Agent 向用户如实解释并优雅降级。

---

## 🌐 国际化支持 (Internationalization / i18n)

本 Demo 项目已全面实现中英双语国际化：
- **Web 可视化面板**：右上角提供一键切换中英文语言按钮（`English` / `简体中文`），支持 localStorage 持久化。切换后看板标题、预设场景、欢迎指引、输入占位符、工具调用轨迹、实时审计流等即时响应。
- **智能体意图与回复双语适配**：支持中英文自然语言意图识别（城市、星座、简报、熔断等）与中英文双语回复生成。
- **REST API**：`/api/scenarios?lang=en` 与 `/api/chat`（支持 `{"message": "...", "lang": "en"}`）原生支持多语言。
- **终端交互模式（CLI Mode）**：支持 `--lang en` 或 `--lang zh`，交互中随时按 `L` 键一键切换双语。

---

## 🛠️ 集成的付费 API 清单 / Paid API Matrix

| 工具名称 | 路径 (Path) | 请求参数 | 说明与价格 |
|---|---|---|---|
| `get_weather` | `/api/v1/simple-weather` | `city="北京"` / `city="Beijing"` | 查询城市实时天气、温度、风向与空气质量 (~0.05 USDC) |
| `get_horoscope` | `/api/v1/constellation` | `consName="摩羯座"`, `type="today"` | 查询星座今日运势、综合分、幸运色/数 (~0.10 USDC) |

---

## 🏗️ 架构与调用时序 / Architecture

```
           用户 (Web / CLI) [中英双语 / i18n]
                 │
                 ▼
     ┌───────────────────────┐
     │      Agent Core       │  自主规划工具、汇总结果；无权批准付款
     └───────────┬───────────┘
                 │ Tool Call (get_weather / get_horoscope)
                 ▼
 ════════════════╪══════════════════════════════════════════════════════
                 │               【Zero-Trust 隔离边界】
                 ▼
     ┌───────────────────────┐
     │    AgentPayClient     │  捕获 402 挑战 ──► 提交防火墙评估
     │ ┌───────────────────┐ │
     │ │SQLitePolicyEngine │ │  单笔限额 / 24h 预算 / 频次熔断 / 白名单矩阵
     │ └───────────────────┘ │    ├─ 拒绝 ──► 抛出 PolicyViolationError（零扣费）
     │ ┌───────────────────┐ │    └─ 放行 ──► EIP-712/3009 离线签名
     │ │   LocalSigner     │ │
     │ └───────────────────┘ │
     └───────────┬───────────┘
 ════════════════╪══════════════════════════════════════════════════════
                 │ HTTP GET + PAYMENT-SIGNATURE + X-Agent-Key
                 ▼
     ┌───────────────────────┐
     │  AgentPay 网关服务    │  /api/v1/simple-weather & /api/v1/constellation
     └───────────┬───────────┘
                 │
                 ▼
      [实时微支付流水看板] ◄── SSE Event Stream 毫秒级推流
```

---

## 🚀 快速上手 (Quick Start)

### 1. 安装依赖
```bash
cd agentpay-demo
pip install -r requirements.txt
```

### 2. 运行自动化验证套件
验证全部 7 大场景与 API 接口（含 i18n 双语套件）：
```bash
python test_demo.py
```

### 3. 启动 Web 可视化看板（推荐）
```bash
python main.py
```
打开浏览器访问：**`http://127.0.0.1:8000`**
- **右上角**：可随时点击语言按钮切换 **English / 简体中文**。
- **左侧**：智能体交互窗口，顶部提供 5 大场景一键触发按钮（根据当前语言自适应显示）。
- **右侧**：实时金融防火墙监控（24H 预算进度条、熔断状态指示灯、白名单矩阵）与 SSE 实时微支付流水审计瀑布流。

### 4. 终端交互模式（CLI Mode）
```bash
# 默认中文模式
python main.py --cli

# 英文模式（或在 CLI 内输入 L 随时切换）
python main.py --cli --lang en
```

---

## 🎯 五大核心验证场景 / Five Core Scenarios

| # | 场景 (ZH / EN) | 预设策略 | 用户指令 (ZH / EN) | 验证重点 |
|---|---|---|---|---|
| **1** | **单次天气微支付**<br>Weather Micro-Payment | 默认策略 | `今天北京天气怎么样？`<br>`How is the weather in Beijing today?` | 捕获 402 挑战 ➔ 离线签名 ➔ 代付放行 ➔ 扣减 $0.05 USDC |
| **2** | **天气与运势协同**<br>Weather & Horoscope Multi-Tool | 默认策略 | `早安，帮我准备今天的简报，包含北京天气和摩羯座今日运势`<br>`Good morning! Prepare today's briefing with Beijing weather and Capricorn horoscope.` | 自主连续调用天气与星座两个付费接口，合计结算 $0.15 USDC 并汇总 |
| **3** | **预算拦截与降级**<br>Budget Cap & Degradation | 24h 预算缩至 **$0.07** | `帮我准备今天的简报（包含天气和摩羯座运势）`<br>`Please prepare today's briefing (including weather and Capricorn horoscope).` | 天气(0.05)消耗后，星座(0.10)被 **DAILY_BUDGET_EXCEEDED** 阻断；Agent 优雅降级，**资金零超支** |
| **4** | **单笔限额硬拦截**<br>Single-Tx Cap Hard Block | 单笔限额设为 **$0.08** | `查询摩羯座今日运势`<br>`Check today's horoscope for Capricorn.` | 星座标价 $0.10 > $0.08，触发 **SINGLE_TX_CAP_EXCEEDED** 拦截；LLM 无法越权批准 |
| **5** | **高频调用熔断保护**<br>High-Frequency Circuit Breaker | 频次上限设为 **3 RPM** | `请快速连续查询天气状况！`<br>`Please query the weather multiple times rapidly!` | 连续请求在第 4 次触发 **CIRCUIT_BREAKER_OPEN** 熔断，整机进入保护期 |

---

## ⚙️ 环境配置说明 (`.env`)

```ini
# Agent Key (网关生成的身份鉴权密钥)
AGENT_KEY=apk_live_209aaf0b44c4fbd955457368ab63a2a745ceea0ccd107ad2

# 网关地址
GATEWAY_URL=https://agentpay.aipmedia.cn

# 本地私钥（EIP-712 / EIP-3009 离线签名）
AGENT_PRIVATE_KEY=0x4f3edf983ac636a65a842ce7c78d9aa706d3b113bce9c46f30d7d21715b23b1d

# 网络与资产
PAYMENT_NETWORK=eip155:84532
PAYMENT_ASSET=0x036CbD53842c5426634e7929541eC2318f3dCF7e

# 金融防火墙默认策略 (1 USDC = 1,000,000)
MAX_PER_TX_BASE_UNITS=200000        # 单笔上限 $0.20 USDC
ROLLING_BUDGET_24H_BASE_UNITS=1000000 # 24h 预算 $1.00 USDC
CIRCUIT_MAX_RPM=20
```

---

## 🛡️ License
Apache-2.0 © [AgentPay](https://github.com/open-agentpay/AgentPay)
