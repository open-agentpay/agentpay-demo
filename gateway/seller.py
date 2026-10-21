import time
import uuid
from typing import Dict, Optional
from fastapi import APIRouter, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from agentpay import decode_authorization, encode_challenge
from agentpay.core.models import PaymentChallenge
from core.config import settings, format_usdc
from core.events import event_bus

seller_router = APIRouter(tags=["x402-seller"])

# In-memory store for issued challenges and settled receipts
issued_challenges: Dict[str, dict] = {}
seller_receipts: list = []


def _create_challenge(
    resource_path: str,
    amount_base_units: int,
    description: str,
) -> PaymentChallenge:
    """Issue a standard x402 V2 payment challenge."""
    cid = f"ch_{uuid.uuid4().hex[:12]}"
    now = int(time.time())
    challenge = PaymentChallenge(
        challenge_id=cid,
        network=settings.PAYMENT_NETWORK,
        asset=settings.PAYMENT_ASSET,
        asset_symbol=settings.PAYMENT_ASSET_SYMBOL,
        decimals=6,
        amount=str(amount_base_units),
        payee=settings.SELLER_WALLET,
        scheme="EIP-3009",
        valid_after=now - 30,
        valid_before=now + 300,
        facilitator_url=f"http://{settings.GATEWAY_HOST}:{settings.GATEWAY_PORT}/facilitator",
        resource_uri=f"{settings.GATEWAY_URL}{resource_path}",
    )
    issued_challenges[cid] = {
        "challenge": challenge,
        "amount_base_units": amount_base_units,
        "resource_path": resource_path,
        "description": description,
        "created_at": now,
        "status": "PENDING",
    }

    event_bus.publish(
        "CHALLENGE_ISSUED",
        {
            "challenge_id": cid,
            "resource": resource_path,
            "amount_base_units": amount_base_units,
            "amount_formatted": format_usdc(amount_base_units),
            "payee": settings.SELLER_WALLET,
            "network": settings.PAYMENT_NETWORK,
        },
    )
    return challenge


def _verify_and_settle(
    payment_signature_header: Optional[str],
    resource_path: str,
    amount_base_units: int,
    description: str,
    agent_key: Optional[str] = None,
) -> dict:
    """
    Check if request includes a valid x402 payment signature.
    If missing or invalid, raises HTTPException(402) with PAYMENT-REQUIRED header.
    """
    if not payment_signature_header:
        chal = _create_challenge(resource_path, amount_base_units, description)
        encoded_chal = encode_challenge(chal)
        raise HTTPException(
            status_code=402,
            detail="Payment Required via x402 V2",
            headers={"PAYMENT-REQUIRED": encoded_chal},
        )

    try:
        auth = decode_authorization(payment_signature_header)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid x402 authorization payload: {str(e)}",
        )

    # Check expiration
    now = int(time.time())
    if auth.valid_before < now:
        raise HTTPException(status_code=400, detail="Payment authorization has expired")

    # Mark challenge as settled
    cid = auth.challenge_id
    if cid in issued_challenges:
        issued_challenges[cid]["status"] = "SETTLED"

    receipt = {
        "challenge_id": cid,
        "resource": resource_path,
        "payer": auth.payer,
        "agent_key": agent_key or "N/A",
        "payee": settings.SELLER_WALLET,
        "amount_base_units": amount_base_units,
        "amount_formatted": format_usdc(amount_base_units),
        "scheme": auth.scheme,
        "timestamp": now,
    }
    seller_receipts.append(receipt)

    event_bus.publish(
        "PAYMENT_SETTLED",
        {
            "challenge_id": cid,
            "resource": resource_path,
            "payer": auth.payer,
            "agent_key": agent_key,
            "amount_base_units": amount_base_units,
            "amount_formatted": format_usdc(amount_base_units),
            "status": "SETTLED",
        },
    )

    return receipt


@seller_router.get("/api/v1/simple-weather")
@seller_router.get("/weather")
async def get_weather(
    city: str = Query(default="北京", description="City name"),
    payment_signature: Optional[str] = Header(None, alias="PAYMENT-SIGNATURE"),
    agent_key: Optional[str] = Header(None, alias="X-Agent-Key"),
):
    """
    Weather Query API (Paid: 0.05 USDC / 50000 base units)
    """
    COST = 50_000
    receipt = _verify_and_settle(payment_signature, "/api/v1/simple-weather", COST, f"Weather for {city}", agent_key=agent_key)

    mock_db = {
        "北京": {"weather": "晴", "temp": "8", "humidity": "38", "direct": "西北风", "power": "4-5级", "aqi": "14"},
        "上海": {"weather": "多云", "temp": "16", "humidity": "55", "direct": "东风", "power": "2-3级", "aqi": "28"},
        "深圳": {"weather": "阵雨", "temp": "24", "humidity": "75", "direct": "微风", "power": "1-2级", "aqi": "20"},
        "广州": {"weather": "多云", "temp": "23", "humidity": "70", "direct": "微风", "power": "1-2级", "aqi": "22"},
        "杭州": {"weather": "晴间多云", "temp": "15", "humidity": "50", "direct": "北风", "power": "2级", "aqi": "30"},
    }
    c_info = mock_db.get(city, {"weather": "晴", "temp": "12", "humidity": "45", "direct": "微风", "power": "2级", "aqi": "25"})

    return {
        "reason": "查询成功!",
        "result": {
            "city": city,
            "realtime": {
                "temperature": c_info["temp"],
                "humidity": c_info["humidity"],
                "info": c_info["weather"],
                "direct": c_info["direct"],
                "power": c_info["power"],
                "aqi": c_info["aqi"],
            },
        },
        "error_code": 0,
        "x402_receipt": receipt,
    }


@seller_router.get("/api/v1/constellation")
@seller_router.get("/horoscope")
async def get_horoscope(
    consName: str = Query(default="摩羯座", description="Zodiac name, e.g. 摩羯座"),
    type: str = Query(default="today", description="Type: today"),
    payment_signature: Optional[str] = Header(None, alias="PAYMENT-SIGNATURE"),
    agent_key: Optional[str] = Header(None, alias="X-Agent-Key"),
):
    """
    Constellation Fortune API (Paid: 0.10 USDC / 100000 base units)
    """
    COST = 100_000
    receipt = _verify_and_settle(payment_signature, "/api/v1/constellation", COST, f"Horoscope for {consName}", agent_key=agent_key)

    return {
        "date": int(time.strftime("%Y%m%d")),
        "name": consName,
        "datetime": time.strftime("%Y年%m月%d日"),
        "all": "85",
        "color": "湖蓝",
        "health": "78",
        "love": "82",
        "money": "75",
        "work": "90",
        "number": 7,
        "summary": f"今日{consName}整体运势处于平稳偏上状态，人际互动能收获正向反馈，事务推进顺畅，保持良好心态即可顺遂过关。",
        "resultcode": "200",
        "error_code": 0,
        "x402_receipt": receipt,
    }


@seller_router.get("/stats")
async def get_seller_stats():
    """Retrieve seller payment receipts and statistics."""
    total_revenue_base_units = sum(r["amount_base_units"] for r in seller_receipts)
    return {
        "seller_wallet": settings.SELLER_WALLET,
        "network": settings.PAYMENT_NETWORK,
        "total_receipts_count": len(seller_receipts),
        "total_revenue_base_units": total_revenue_base_units,
        "total_revenue_formatted": format_usdc(total_revenue_base_units),
        "recent_receipts": seller_receipts[-10:],
    }
