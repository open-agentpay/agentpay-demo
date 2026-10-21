import json
import logging
from typing import Any, AsyncGenerator, Dict, List, Optional

from agent.prompts import get_system_prompt
from agent.tools import (
    execute_tool_call,
    get_anthropic_tools,
    get_openai_tools,
)
from core.config import settings
from core.events import event_bus

logger = logging.getLogger(__name__)

# Zodiac mapping between English and Chinese
ZODIAC_EN_MAP = {
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
}

ZODIAC_ZH_TO_EN = {v: k.capitalize() for k, v in ZODIAC_EN_MAP.items()}

# City mapping
CITY_EN_MAP = {
    "beijing": "北京",
    "shanghai": "上海",
    "shenzhen": "深圳",
    "guangzhou": "广州",
    "hangzhou": "杭州",
}
CITY_ZH_TO_EN = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "深圳": "Shenzhen",
    "广州": "Guangzhou",
    "杭州": "Hangzhou",
}

# Weather conditions translation
WEATHER_ZH_TO_EN = {
    "晴": "Sunny",
    "多云": "Partly Cloudy",
    "阴": "Overcast",
    "阵雨": "Showers",
    "雷阵雨": "Thundershowers",
    "小雨": "Light Rain",
    "中雨": "Moderate Rain",
    "大雨": "Heavy Rain",
    "雨夹雪": "Sleet",
    "小雪": "Light Snow",
    "中雪": "Moderate Snow",
    "大雪": "Heavy Snow",
    "雾": "Foggy",
    "霾": "Hazy",
}


def detect_language(text: str, default: str = "zh") -> str:
    """Detect language from text based on Chinese character presence."""
    if not text:
        return default
    if any("\u4e00" <= char <= "\u9fff" for char in text):
        return "zh"
    return "en"


class BaseAgentRunner:
    async def chat(self, user_message: str, lang: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError


class MockAgentRunner(BaseAgentRunner):
    """
    Built-in Intelligent Mock Agent for zero-cost, zero-API-key testing.
    Determines tool calls based on user intent and executes them against the real AgentPay client.
    Supports English & Chinese bilingual execution and responses.
    """

    async def chat(self, user_message: str, lang: Optional[str] = None) -> Dict[str, Any]:
        msg_lower = user_message.lower()
        active_lang = lang or detect_language(user_message, default="zh")
        is_en = active_lang.lower().startswith("en")
        tool_results: List[Dict[str, Any]] = []

        event_bus.publish(
            "AGENT_THINKING",
            {
                "message": (
                    "Analyzing user intent and planning tool calls..."
                    if is_en
                    else "正在解析用户意图并制定工具调用计划..."
                ),
                "provider": "Built-in Mock Agent",
            },
        )

        planned_calls = []

        # Intent Analysis
        # 1. Circuit breaker test intent
        is_circuit_test = any(k in msg_lower for k in ["熔断", "快速", "刷", "circuit", "rapid", "burst", "frequency", "loop"])
        
        # 2. Single-tx cap test intent
        is_cap_test = any(k in msg_lower for k in ["单笔", "超限", "cap", "single-tx", "single tx", "limit"]) and (
            "运势" in user_message or "horoscope" in msg_lower or "constellation" in msg_lower or "capricorn" in msg_lower or "zodiac" in msg_lower
        )

        # 3. Weather intent
        has_weather = "天气" in user_message or "weather" in msg_lower
        
        # 4. Horoscope intent
        has_horoscope = any(
            k in msg_lower
            for k in [
                "运势",
                "星座",
                "horoscope",
                "constellation",
                "zodiac",
                "aries",
                "taurus",
                "gemini",
                "cancer",
                "leo",
                "virgo",
                "libra",
                "scorpio",
                "sagittarius",
                "capricorn",
                "aquarius",
                "pisces",
            ]
        ) or any(s in user_message for s in ["白羊", "金牛", "双子", "巨蟹", "狮子", "处女", "天秤", "天蝎", "射手", "摩羯", "水瓶", "双鱼"])

        # 5. Briefing combo intent
        is_briefing = any(k in msg_lower for k in ["简报", "早报", "早安", "briefing", "summary", "morning"])

        if is_circuit_test:
            # Trigger rapid loop to demonstrate circuit breaker
            for _ in range(5):
                planned_calls.append(("get_weather", {"city": "北京"}))
        elif is_cap_test:
            # Single-tx cap test: invoke horoscope which costs more (e.g. 100,000 base units)
            planned_calls.append(("get_horoscope", {"consName": "摩羯座"}))
        elif has_weather and not has_horoscope and not is_briefing:
            # Single tool: weather
            city = self._extract_city(user_message, msg_lower)
            planned_calls.append(("get_weather", {"city": city}))
        elif has_horoscope and not has_weather and not is_briefing:
            # Single tool: horoscope
            sign = self._extract_zodiac(user_message, msg_lower)
            planned_calls.append(("get_horoscope", {"consName": sign}))
        else:
            # Comprehensive briefing: Weather + Horoscope
            city = self._extract_city(user_message, msg_lower)
            sign = self._extract_zodiac(user_message, msg_lower)
            planned_calls.append(("get_weather", {"city": city}))
            planned_calls.append(("get_horoscope", {"consName": sign}))

        # Execute planned calls through real AgentPay client
        for tool_name, args in planned_calls:
            out = await execute_tool_call(tool_name, args, lang=active_lang)
            tool_results.append({"tool": tool_name, "args": args, "result": out})

        # Synthesize conversational response
        response_text = self._synthesize_response(user_message, tool_results, lang=active_lang)

        return {
            "response": response_text,
            "tool_calls": tool_results,
            "provider": "mock",
            "lang": active_lang,
        }

    def _extract_city(self, text: str, text_lower: str) -> str:
        for en_name, zh_name in CITY_EN_MAP.items():
            if en_name in text_lower or zh_name in text:
                return zh_name
        return "北京"

    def _extract_zodiac(self, text: str, text_lower: str) -> str:
        for en_name, zh_name in ZODIAC_EN_MAP.items():
            if en_name in text_lower or zh_name in text or zh_name.replace("座", "") in text:
                return zh_name
        return "摩羯座"

    def _synthesize_response(self, user_msg: str, tool_results: List[Dict[str, Any]], lang: str = "zh") -> str:
        is_en = (lang or "").lower().startswith("en")

        if is_en:
            return self._synthesize_response_en(tool_results)
        else:
            return self._synthesize_response_zh(tool_results)

    def _synthesize_response_zh(self, tool_results: List[Dict[str, Any]]) -> str:
        parts = ["☀️ **今日简报为您准备完毕：**\n"]
        expenses = []
        blocked_items = []

        for item in tool_results:
            tool = item["tool"]
            res = item["result"]
            if res.get("ok"):
                data = res.get("data", {})
                receipt = data.get("x402_receipt", {})
                cost_str = receipt.get("amount_formatted", "已授权放行")
                expenses.append(f"• `{tool}`: 接口调用成功 ({cost_str})")

                if tool == "get_weather":
                    res_obj = data.get("result", {})
                    city_name = res_obj.get("city") or data.get("city", "北京")
                    realtime = res_obj.get("realtime", {})
                    cond = realtime.get("info") or data.get("condition", "晴")
                    temp = realtime.get("temperature") or data.get("temperature", "")
                    humidity = realtime.get("humidity") or data.get("humidity", "")
                    direct = realtime.get("direct") or data.get("wind", "")
                    power = realtime.get("power", "")
                    aqi = realtime.get("aqi") or data.get("air_quality", "")

                    parts.append(
                        f"📍 **城市天气 [{city_name}]**：{cond}，气温 {temp}℃，湿度 {humidity}%，"
                        f"风向 {direct} {power}，空气质量 AQI {aqi}。"
                    )
                elif tool == "get_horoscope":
                    name = data.get("name") or data.get("sign") or "摩羯座"
                    score = data.get("all") or data.get("overall_score") or "85"
                    summary = data.get("summary") or "今日运势平稳"
                    color = data.get("color") or data.get("lucky_color") or "金色"
                    number = data.get("number") or data.get("lucky_number") or 7
                    work = data.get("work") or data.get("career") or ""
                    love = data.get("love") or ""

                    parts.append(
                        f"🔮 **星座今日运势 [{name}]**：综合指数 {score} 分。\n"
                        f"  - 整体小结：{summary}\n"
                        f"  - 职场/学业：{work} | 爱情指数：{love}\n"
                        f"  - 幸运色/幸运数：{color} / {number}"
                    )
            else:
                rule = res.get("rule", "BLOCKED")
                msg = res.get("message", "支付被策略拒绝")
                blocked_items.append(f"• `{tool}`: **拦截拒绝** ({rule}) - {msg}")

        if blocked_items:
            parts.append("\n⚠️ **【金融防火墙安全拦截报告】**：")
            for b in blocked_items:
                parts.append(b)
            parts.append("🛡️ *系统实行严格的 Fail-Closed 机制，受阻接口已保障零资金扣减。*")

        parts.append("\n---\n💳 **【本次交互账单审计】**：")
        if expenses:
            parts.extend(expenses)
        else:
            parts.append("• 本次未产生任何扣费。")

        return "\n\n".join(parts)

    def _synthesize_response_en(self, tool_results: List[Dict[str, Any]]) -> str:
        parts = ["☀️ **Today's Morning Briefing is Ready:**\n"]
        expenses = []
        blocked_items = []

        for item in tool_results:
            tool = item["tool"]
            res = item["result"]
            if res.get("ok"):
                data = res.get("data", {})
                receipt = data.get("x402_receipt", {})
                cost_str = receipt.get("amount_formatted", "Settled")
                expenses.append(f"• `{tool}`: API settled successfully ({cost_str})")

                if tool == "get_weather":
                    res_obj = data.get("result", {})
                    city_zh = res_obj.get("city") or data.get("city", "北京")
                    city_en = CITY_ZH_TO_EN.get(city_zh, city_zh)
                    realtime = res_obj.get("realtime", {})
                    cond_zh = realtime.get("info") or data.get("condition", "晴")
                    cond_en = WEATHER_ZH_TO_EN.get(cond_zh, cond_zh)
                    temp = realtime.get("temperature") or data.get("temperature", "")
                    humidity = realtime.get("humidity") or data.get("humidity", "")
                    direct = realtime.get("direct") or data.get("wind", "")
                    power = realtime.get("power", "")
                    aqi = realtime.get("aqi") or data.get("air_quality", "")

                    parts.append(
                        f"📍 **City Weather [{city_en}]**: {cond_en}, Temperature {temp}°C, "
                        f"Humidity {humidity}%, Wind {direct} {power}, Air Quality AQI {aqi}."
                    )
                elif tool == "get_horoscope":
                    name_zh = data.get("name") or data.get("sign") or "摩羯座"
                    name_en = ZODIAC_ZH_TO_EN.get(name_zh, name_zh)
                    score = data.get("all") or data.get("overall_score") or "85"
                    summary = (
                        f"Today's overall horoscope for {name_en} is steady and favorable. "
                        f"Positive interactions and smooth workflow are expected."
                    )
                    color = data.get("color") or data.get("lucky_color") or "Lake Blue"
                    number = data.get("number") or data.get("lucky_number") or 7
                    work = data.get("work") or data.get("career") or "90"
                    love = data.get("love") or "82"

                    parts.append(
                        f"🔮 **Daily Horoscope [{name_en}]**: Overall Score {score}/100.\n"
                        f"  - Summary: {summary}\n"
                        f"  - Career Index: {work} | Love Index: {love}\n"
                        f"  - Lucky Color / Number: {color} / {number}"
                    )
            else:
                rule = res.get("rule", "BLOCKED")
                msg = res.get("message", "Payment rejected by policy")
                blocked_items.append(f"• `{tool}`: **Blocked** ({rule}) - {msg}")

        if blocked_items:
            parts.append("\n⚠️ **[Financial Firewall Security Interception Report]**:")
            for b in blocked_items:
                parts.append(b)
            parts.append("🛡️ *The system strictly enforces Fail-Closed; zero funds were deducted for blocked services.*")

        parts.append("\n---\n💳 **[Billing & Audit Summary]**:")
        if expenses:
            parts.extend(expenses)
        else:
            parts.append("• No fees incurred for this session.")

        return "\n\n".join(parts)


class ClaudeAgentRunner(BaseAgentRunner):
    """
    Anthropic Claude runner using native Tool Use.
    """

    def __init__(self):
        import anthropic

        self.client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = settings.ANTHROPIC_MODEL

    async def chat(self, user_message: str, lang: Optional[str] = None) -> Dict[str, Any]:
        tools = get_anthropic_tools()
        active_lang = lang or detect_language(user_message, default="zh")
        sys_prompt = get_system_prompt(active_lang)

        messages = [{"role": "user", "content": user_message}]
        executed_calls = []

        while True:
            resp = await self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=sys_prompt,
                tools=tools,
                messages=messages,
            )

            messages.append({"role": "assistant", "content": resp.content})

            if resp.stop_reason != "tool_use":
                text_content = ""
                for block in resp.content:
                    if hasattr(block, "text"):
                        text_content += block.text
                return {
                    "response": text_content,
                    "tool_calls": executed_calls,
                    "provider": "anthropic",
                    "lang": active_lang,
                }

            tool_results = []
            for block in resp.content:
                if block.type == "tool_use":
                    t_name = block.name
                    t_input = block.input
                    out = await execute_tool_call(t_name, t_input, lang=active_lang)
                    executed_calls.append({"tool": t_name, "args": t_input, "result": out})
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(out, ensure_ascii=False),
                        }
                    )

            messages.append({"role": "user", "content": tool_results})


class OpenAIAgentRunner(BaseAgentRunner):
    """
    OpenAI runner compatible with OpenAI / DeepSeek / Ollama / OpenRouter.
    """

    def __init__(self):
        import openai

        self.client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
        self.model = settings.OPENAI_MODEL

    async def chat(self, user_message: str, lang: Optional[str] = None) -> Dict[str, Any]:
        tools = get_openai_tools()
        active_lang = lang or detect_language(user_message, default="zh")
        sys_prompt = get_system_prompt(active_lang)

        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_message},
        ]
        executed_calls = []

        while True:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=tools,
                max_tokens=2000,
                extra_body={"reasoning": {"enabled": True}},
            )
            msg = resp.choices[0].message

            msg_dict = msg.model_dump(exclude_none=True)

            if hasattr(msg, "model_extra") and msg.model_extra and "reasoning_details" in msg.model_extra:
                msg_dict["reasoning_details"] = msg.model_extra["reasoning_details"]

            messages.append(msg_dict)

            if not msg.tool_calls:
                return {
                    "response": msg.content or "",
                    "tool_calls": executed_calls,
                    "provider": "openai",
                    "lang": active_lang,
                }

            for tc in msg.tool_calls:
                t_name = tc.function.name
                t_args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                out = await execute_tool_call(t_name, t_args, lang=active_lang)
                executed_calls.append({"tool": t_name, "args": t_args, "result": out})

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": json.dumps(out, ensure_ascii=False),
                    }
                )


def get_agent_runner() -> BaseAgentRunner:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "anthropic" and settings.ANTHROPIC_API_KEY:
        return ClaudeAgentRunner()
    elif provider == "openai" and settings.OPENAI_API_KEY:
        return OpenAIAgentRunner()
    else:
        return MockAgentRunner()
