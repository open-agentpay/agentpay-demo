from typing import Any, Dict, List, Optional
from payment.manager import payment_manager

SCENARIOS: List[Dict[str, Any]] = [
    {
        "id": "scenario_1",
        "title": "场景 1: 单次天气微支付",
        "title_zh": "场景 1: 单次天气微支付",
        "title_en": "Scenario 1: Weather Micro-Payment",
        "badge": "Happy Path",
        "badge_zh": "正常放行",
        "badge_en": "Happy Path",
        "badge_color": "emerald",
        "prompt": "今天北京天气怎么样？",
        "prompt_zh": "今天北京天气怎么样？",
        "prompt_en": "How is the weather in Beijing today?",
        "description": "验证 /api/v1/simple-weather 接口调用、402 协议握手、离线签名与放行全流程。",
        "description_zh": "验证 /api/v1/simple-weather 接口调用、402 协议握手、离线签名与放行全流程。",
        "description_en": "Verify /api/v1/simple-weather API call, x402 handshake, offline signing, and settlement.",
        "setup": {
            "max_per_tx": 200_000,
            "rolling_budget": 1_000_000,
            "circuit_rpm": 20,
            "clear_history": True,
        },
    },
    {
        "id": "scenario_2",
        "title": "场景 2: 天气与运势双接口协同",
        "title_zh": "场景 2: 天气与运势双接口协同",
        "title_en": "Scenario 2: Weather & Horoscope Coordination",
        "badge": "Multi-Tool",
        "badge_zh": "双接口协同",
        "badge_en": "Multi-Tool",
        "badge_color": "blue",
        "prompt": "早安，帮我准备今天的简报，包含北京天气和摩羯座今日运势。",
        "prompt_zh": "早安，帮我准备今天的简报，包含北京天气和摩羯座今日运势。",
        "prompt_en": "Good morning! Please prepare today's briefing with Beijing weather and Capricorn horoscope.",
        "description": "Agent 自主规划调用天气与星座运势两个付费接口，透明完成微支付并汇总。",
        "description_zh": "Agent 自主规划调用天气与星座运势两个付费接口，透明完成微支付并汇总。",
        "description_en": "Agent autonomously plans and invokes weather and horoscope paid APIs, settling micro-payments and synthesizing results.",
        "setup": {
            "max_per_tx": 200_000,
            "rolling_budget": 1_000_000,
            "circuit_rpm": 20,
            "clear_history": True,
        },
    },
    {
        "id": "scenario_3",
        "title": "场景 3: 预算拦截与优雅降级",
        "title_zh": "场景 3: 预算拦截与优雅降级",
        "title_en": "Scenario 3: Budget Cap & Graceful Degradation",
        "badge": "Fail-Closed",
        "badge_zh": "Fail-Closed",
        "badge_en": "Fail-Closed",
        "badge_color": "amber",
        "prompt": "帮我准备今天的简报（包含天气和摩羯座运势）。",
        "prompt_zh": "帮我准备今天的简报（包含天气和摩羯座运势）。",
        "prompt_en": "Please prepare today's briefing (including weather and Capricorn horoscope).",
        "description": "将 24h 预算缩减至 $0.07 USDC（70,000）。天气消耗 50,000 后，运势(100,000)被防火墙拦截，Agent 优雅降级。",
        "description_zh": "将 24h 预算缩减至 $0.07 USDC（70,000）。天气消耗 50,000 后，运势(100,000)被防火墙拦截，Agent 优雅降级。",
        "description_en": "24h budget reduced to $0.07 USDC. Weather consumes $0.05, horoscope ($0.10) is blocked by firewall, agent degrades gracefully.",
        "setup": {
            "max_per_tx": 200_000,
            "rolling_budget": 70_000,  # Only $0.07 USDC (Weather 50k succeeds, Horoscope 100k blocked)
            "circuit_rpm": 20,
            "clear_history": True,
        },
    },
    {
        "id": "scenario_4",
        "title": "场景 4: 单笔限额硬拦截",
        "title_zh": "场景 4: 单笔限额硬拦截",
        "title_en": "Scenario 4: Single-Tx Cap Hard Block",
        "badge": "Zero-Trust",
        "badge_zh": "Zero-Trust",
        "badge_en": "Zero-Trust",
        "badge_color": "rose",
        "prompt": "查询摩羯座今日运势。",
        "prompt_zh": "查询摩羯座今日运势。",
        "prompt_en": "Check today's horoscope for Capricorn.",
        "description": "单笔限额设为 $0.08 USDC (80,000)，而星座接口需 100,000。本地防火墙直接拒绝签名，LLM 无法越权。",
        "description_zh": "单笔限额设为 $0.08 USDC (80,000)，而星座接口需 100,000。本地防火墙直接拒绝签名，LLM 无法越权。",
        "description_en": "Single-tx limit set to $0.08 USDC while horoscope costs $0.10. Local firewall rejects signature; LLM cannot override.",
        "setup": {
            "max_per_tx": 80_000,  # $0.08 USDC limit (Horoscope costs 100,000)
            "rolling_budget": 1_000_000,
            "circuit_rpm": 20,
            "clear_history": True,
        },
    },
    {
        "id": "scenario_5",
        "title": "场景 5: 高频调用熔断保护",
        "title_zh": "场景 5: 高频调用熔断保护",
        "title_en": "Scenario 5: High-Frequency Circuit Breaker",
        "badge": "Circuit Breaker",
        "badge_zh": "熔断保护",
        "badge_en": "Circuit Breaker",
        "badge_color": "purple",
        "prompt": "请快速连续查询天气状况！",
        "prompt_zh": "请快速连续查询天气状况！",
        "prompt_en": "Please query the weather multiple times rapidly!",
        "description": "设置每分钟上限 3 次请求 (3 RPM)。连续快速调用在第 4 次触发熔断，整机进入保护期。",
        "description_zh": "设置每分钟上限 3 次请求 (3 RPM)。连续快速调用在第 4 次触发熔断，整机进入保护期。",
        "description_en": "Set rate limit to 3 RPM. Rapid calls trip circuit breaker on the 4th request, putting system into cooldown protection.",
        "setup": {
            "max_per_tx": 200_000,
            "rolling_budget": 1_000_000,
            "circuit_rpm": 3,  # Strict RPM
            "clear_history": True,
        },
    },
]


def get_localized_scenarios(lang: str = "zh") -> List[Dict[str, Any]]:
    """Return scenarios with localized titles, descriptions, and prompts."""
    is_en = (lang or "").lower().startswith("en")
    localized = []
    for sc in SCENARIOS:
        item = dict(sc)
        if is_en:
            item["title"] = sc.get("title_en", sc["title"])
            item["badge"] = sc.get("badge_en", sc["badge"])
            item["prompt"] = sc.get("prompt_en", sc["prompt"])
            item["description"] = sc.get("description_en", sc["description"])
        else:
            item["title"] = sc.get("title_zh", sc["title"])
            item["badge"] = sc.get("badge_zh", sc["badge"])
            item["prompt"] = sc.get("prompt_zh", sc["prompt"])
            item["description"] = sc.get("description_zh", sc["description"])
        localized.append(item)
    return localized


def apply_scenario_setup(scenario_id: str) -> Dict[str, Any]:
    matched = next((s for s in SCENARIOS if s["id"] == scenario_id), None)
    if not matched:
        return {"ok": False, "error": f"Scenario {scenario_id} not found"}

    setup = matched["setup"]
    payment_manager.update_policy(
        max_per_tx=setup.get("max_per_tx"),
        rolling_budget=setup.get("rolling_budget"),
        circuit_rpm=setup.get("circuit_rpm"),
        clear_budget_history=setup.get("clear_history", False),
    )

    return {
        "ok": True,
        "scenario": matched,
        "current_stats": payment_manager.get_stats(),
    }
