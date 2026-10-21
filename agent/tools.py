import json
import time
from typing import Any, Dict
from agentpay.policy import PolicyErrorCode, PolicyViolationError
from core.config import format_usdc, settings
from core.events import event_bus
from payment.manager import payment_manager

# Canonical Simplified Chinese mappings for interface parameters
CANONICAL_CITY_ZH = {
    "beijing": "北京",
    "shanghai": "上海",
    "shenzhen": "深圳",
    "guangzhou": "广州",
    "hangzhou": "杭州",
    "北京": "北京",
    "上海": "上海",
    "深圳": "深圳",
    "广州": "广州",
    "杭州": "杭州",
}

CANONICAL_ZODIAC_ZH = {
    "aries": "白羊座",
    "taurus": "金牛座",
    "gemini": "双子座",
    "cancer": "巨蟹座",
    "leo": "狮子座",
    "virgo": "处女座",
    "libra": "天秤座",
    "scorpio": "天蝎座",
    "scorpius": "天蝎座",
    "sagittarius": "射手座",
    "capricorn": "摩羯座",
    "aquarius": "水瓶座",
    "pisces": "双鱼座",
    "白羊座": "白羊座",
    "金牛座": "金牛座",
    "双子座": "双子座",
    "巨蟹座": "巨蟹座",
    "狮子座": "狮子座",
    "处女座": "处女座",
    "天秤座": "天秤座",
    "天蝎座": "天蝎座",
    "射手座": "射手座",
    "摩羯座": "摩羯座",
    "水瓶座": "水瓶座",
    "双鱼座": "双鱼座",
}

# Tool Schemas for LLM (compatible with Anthropic & OpenAI)
# Values for 'city' and 'consName' must strictly be passed in Simplified Chinese
TOOL_DEFINITIONS = [
    {
        "name": "get_weather",
        "description": "Query weather conditions for a specified city (paid micro-payment API). The parameter 'city' MUST be provided in Simplified Chinese (e.g. '北京', '上海', '深圳').",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {
                    "type": "string",
                    "description": "Simplified Chinese city name (e.g. '北京', '上海', '深圳', '广州', '杭州'). Do NOT pass English names.",
                }
            },
            "required": ["city"],
        },
    },
    {
        "name": "get_horoscope",
        "description": "Query today's horoscope for a specified zodiac sign (paid micro-payment API). The parameter 'consName' MUST be provided in Simplified Chinese (e.g. '摩羯座', '白羊座').",
        "parameters": {
            "type": "object",
            "properties": {
                "consName": {
                    "type": "string",
                    "description": "Simplified Chinese zodiac sign name (e.g. '摩羯座', '白羊座', '金牛座', '双子座', '巨蟹座', '狮子座', '处女座', '天秤座', '天蝎座', '射手座', '水瓶座', '双鱼座'). Do NOT pass English names.",
                }
            },
            "required": ["consName"],
        },
    },
]


def get_anthropic_tools():
    """Convert definitions to Anthropic Tool Use format."""
    return [
        {
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        }
        for t in TOOL_DEFINITIONS
    ]


def get_openai_tools():
    """Convert definitions to OpenAI Function format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["parameters"],
            },
        }
        for t in TOOL_DEFINITIONS
    ]


def get_policy_explanation(code_name: str, lang: str = "zh") -> str:
    """Return localized explanation for a financial firewall policy violation."""
    is_en = (lang or "").lower().startswith("en")
    cap_str = format_usdc(payment_manager.current_config.max_per_tx_base_units)
    avail_str = format_usdc(payment_manager.get_available_budget())
    rpm_val = payment_manager.current_config.circuit_max_rpm

    if is_en:
        explanations_en = {
            PolicyErrorCode.SINGLE_TX_CAP_EXCEEDED.value: (
                f"Single-Tx Cap Blocked: The API price exceeds the agent's single-tx limit ({cap_str}). Zero funds lost."
            ),
            PolicyErrorCode.DAILY_BUDGET_EXCEEDED.value: (
                f"24H Budget Exceeded: Remaining budget is insufficient for this call (Available: {avail_str}). Zero funds lost."
            ),
            PolicyErrorCode.CIRCUIT_BREAKER_OPEN.value: (
                f"Circuit Breaker Open: Request frequency exceeded the protection threshold ({rpm_val} RPM). System entered cooldown."
            ),
            PolicyErrorCode.NETWORK_NOT_WHITELISTED.value: "Network Whitelist Blocked: Payment network is not in the trusted whitelist.",
            PolicyErrorCode.ASSET_NOT_WHITELISTED.value: "Asset Whitelist Blocked: Payment token asset is not in the whitelist.",
            PolicyErrorCode.PAYEE_NOT_WHITELISTED.value: "Payee Whitelist Blocked: Payee address is not in the whitelist.",
            PolicyErrorCode.DOMAIN_NOT_WHITELISTED.value: "Domain Whitelist Blocked: Target domain is not in the whitelist.",
            PolicyErrorCode.POLICY_FROZEN.value: "Policy Frozen: Agent is administratively frozen, all outgoing payments are disabled.",
        }
        return explanations_en.get(code_name, f"Financial firewall rejected payment ({code_name})")
    else:
        explanations_zh = {
            PolicyErrorCode.SINGLE_TX_CAP_EXCEEDED.value: (
                f"单笔支付超限拦截：接口要价超过了本智能体单笔上限 ({cap_str})。资金零损失。"
            ),
            PolicyErrorCode.DAILY_BUDGET_EXCEEDED.value: (
                f"24小时累计预算不足拦截：当前剩余预算不足以支付该接口费用 (当前剩余 {avail_str})。资金零损失。"
            ),
            PolicyErrorCode.CIRCUIT_BREAKER_OPEN.value: (
                f"高频调用熔断拦截：请求频率超过了熔断保护阈值 ({rpm_val} RPM)。系统进入冷却保护。"
            ),
            PolicyErrorCode.NETWORK_NOT_WHITELISTED.value: "网络白名单拦截：该支付网络不在受信任白名单中。",
            PolicyErrorCode.ASSET_NOT_WHITELISTED.value: "资产白名单拦截：该支付代币不在白名单中。",
            PolicyErrorCode.PAYEE_NOT_WHITELISTED.value: "收款商户白名单拦截：该收款地址不在白名单中。",
            PolicyErrorCode.DOMAIN_NOT_WHITELISTED.value: "域名白名单拦截：请求的目标域名不在安全白名单中。",
            PolicyErrorCode.POLICY_FROZEN.value: "智能体处于管理冻结状态，禁止一切对外支付。",
        }
        return explanations_zh.get(code_name, f"金融防火墙策略拒绝支付 ({code_name})")


async def execute_tool_call(tool_name: str, arguments: Dict[str, Any], lang: str = "zh") -> Dict[str, Any]:
    """
    Executes a paid tool call via AgentPayClient.
    Zero-Trust Boundary:
    The LLM proposes the call; AgentPayClient intercepts 402, evaluates local SQLite policy,
    and either signs or throws PolicyViolationError without LLM intervention.

    Constraint: All tool parameter values (city, consName) are strictly converted to Simplified Chinese.
    """
    client = payment_manager.get_client()
    gateway_base = settings.GATEWAY_URL.rstrip("/")
    start_time = time.time()

    path = ""
    params = {}

    if tool_name == "get_weather":
        raw_city = str(arguments.get("city", "北京")).strip()
        # Strictly normalize city parameter value to Simplified Chinese
        city_zh = CANONICAL_CITY_ZH.get(raw_city.lower(), raw_city)
        arguments["city"] = city_zh
        path = "/api/v1/simple-weather"
        params = {"city": city_zh}
    elif tool_name == "get_horoscope":
        raw_sign = str(arguments.get("consName", "摩羯座")).strip()
        # Strictly normalize consName parameter value to Simplified Chinese
        sign_zh = CANONICAL_ZODIAC_ZH.get(raw_sign.lower(), raw_sign)
        if not sign_zh.endswith("座"):
            sign_zh += "座"
        arguments["consName"] = sign_zh
        path = "/api/v1/constellation"
        params = {"consName": sign_zh, "type": "today"}
    else:
        return {"ok": False, "error": f"Unknown tool: {tool_name}"}

    event_bus.publish(
        "TOOL_EXECUTION_START",
        {
            "tool": tool_name,
            "args": arguments,
        },
    )

    expected_cost = 50_000 if tool_name == "get_weather" else 100_000
    url = f"{gateway_base}{path}"

    try:
        # 1. Proactive Zero-Trust Financial Firewall Evaluation (Client-Side Gatekeeper)
        payment_manager.check_guardrails_before_call(expected_cost, tool_name)

        ledger_count_before = payment_manager.conn.execute(
            "SELECT count(*) FROM ap_budget_ledger WHERE policy_id = ?;",
            (payment_manager.current_config.id,),
        ).fetchone()[0]

        response = await client.get(url, params=params)
        duration_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200:
            ledger_count_after = payment_manager.conn.execute(
                "SELECT count(*) FROM ap_budget_ledger WHERE policy_id = ?;",
                (payment_manager.current_config.id,),
            ).fetchone()[0]

            # If AgentPayTransport did not intercept 402 (e.g. server returned direct 200), record spend locally:
            if ledger_count_after == ledger_count_before:
                payment_manager.record_committed_spend(expected_cost, tool_name)

            data = response.json()
            receipt = data.get("x402_receipt", {})
            cost = receipt.get("amount_base_units", expected_cost)

            event_bus.publish(
                "TOOL_EXECUTION_SUCCESS",
                {
                    "tool": tool_name,
                    "url": path,
                    "status_code": 200,
                    "duration_ms": duration_ms,
                    "cost_formatted": format_usdc(cost),
                    "receipt": receipt,
                    "available_budget": format_usdc(payment_manager.get_available_budget()),
                },
            )
            return {"ok": True, "data": data}
        else:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": response.text,
            }

    except PolicyViolationError as e:
        duration_ms = int((time.time() - start_time) * 1000)
        code_name = e.code.value if hasattr(e.code, "value") else str(e.code)

        explanation_zh = get_policy_explanation(code_name, "zh")
        explanation_en = get_policy_explanation(code_name, "en")
        human_explanation = explanation_en if (lang or "").lower().startswith("en") else explanation_zh

        event_bus.publish(
            "POLICY_BLOCKED",
            {
                "tool": tool_name,
                "url": path,
                "rule_violated": code_name,
                "duration_ms": duration_ms,
                "explanation": human_explanation,
                "explanation_zh": explanation_zh,
                "explanation_en": explanation_en,
                "available_budget": format_usdc(payment_manager.get_available_budget()),
            },
        )

        return {
            "ok": False,
            "error_code": "FINANCIAL_POLICY_BLOCKED",
            "rule": code_name,
            "message": human_explanation,
            "funds_lost": "0 USDC (Fail-Closed)",
        }

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        event_bus.publish(
            "TOOL_EXECUTION_ERROR",
            {
                "tool": tool_name,
                "url": path,
                "error": str(e),
                "duration_ms": duration_ms,
            },
        )
        return {"ok": False, "error": type(e).__name__, "detail": str(e)}
