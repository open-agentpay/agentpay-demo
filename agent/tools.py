import time
from typing import Any, Dict
from core.config import settings
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


async def execute_tool_call(tool_name: str, arguments: Dict[str, Any], lang: str = "zh") -> Dict[str, Any]:
    """
    Executes a paid tool call via AgentPayClient.
    The demo only invokes the AgentPay Python SDK client.
    Payment policy checks, budget limits, circuit breakers, and payment accounting
    are handled internally by the SDK.

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

    url = f"{gateway_base}{path}"

    try:
        response = await client.get(url, params=params)
        duration_ms = int((time.time() - start_time) * 1000)

        if response.status_code == 200:
            data = response.json()
            receipt = data.get("x402_receipt", {})

            event_bus.publish(
                "TOOL_EXECUTION_SUCCESS",
                {
                    "tool": tool_name,
                    "url": path,
                    "status_code": 200,
                    "duration_ms": duration_ms,
                    "receipt": receipt,
                },
            )
            return {"ok": True, "data": data}
        else:
            return {
                "ok": False,
                "status_code": response.status_code,
                "error": response.text,
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
