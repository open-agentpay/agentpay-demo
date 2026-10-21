import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.runner import get_agent_runner
from core.config import settings
from core.events import event_bus
from gateway.seller import seller_router
from payment.manager import payment_manager
from scenarios.manager import SCENARIOS, apply_scenario_setup, get_localized_scenarios

# Initialize FastAPI App
app = FastAPI(
    title="AgentPay Demo API",
    description="AgentPay x402 Micro-Payment and Financial Firewall Demo",
    version="0.2.0",
)

# CORS setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Mount x402 Seller Gateway (support both direct /api/v1 and /gateway prefixes)
app.include_router(seller_router)
app.include_router(seller_router, prefix="/gateway")

# 2. Mount Static Files & Frontend
WEB_DIR = Path(__file__).parent / "web"
STATIC_DIR = WEB_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def serve_index():
    index_file = WEB_DIR / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="index.html not found")
    response = FileResponse(index_file)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


# 3. API Endpoints
class ChatRequest(BaseModel):
    message: str
    lang: Optional[str] = None  # "zh" | "en" | None (auto-detect)


@app.post("/api/chat")
async def handle_chat(req: ChatRequest):
    """Process user message through agent and financial firewall."""
    if not req.message.strip():
        raise HTTPException(status_code=400, detail="Empty message")

    runner = get_agent_runner()
    try:
        result = await runner.chat(req.message, lang=req.lang)
        return {
            "ok": True,
            "response": result["response"],
            "tool_calls": result.get("tool_calls", []),
            "provider": result.get("provider", "mock"),
            "lang": result.get("lang", req.lang or "zh"),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/api/scenarios")
async def list_scenarios(lang: Optional[str] = Query(default=None)):
    """List all pre-configured test scenarios with optional localization."""
    if lang:
        return {"ok": True, "scenarios": get_localized_scenarios(lang)}
    return {"ok": True, "scenarios": SCENARIOS}


@app.post("/api/scenarios/{scenario_id}/apply")
async def apply_scenario(scenario_id: str):
    """Apply policy parameters corresponding to a specific scenario."""
    res = apply_scenario_setup(scenario_id)
    if not res.get("ok"):
        raise HTTPException(status_code=404, detail=res.get("error"))
    return res


@app.get("/api/stats")
async def get_policy_stats():
    """Retrieve current financial firewall stats and budget."""
    return payment_manager.get_stats()


@app.post("/api/policy/reset")
async def reset_policy():
    """Reset financial policy and budget ledger to defaults."""
    payment_manager.reset_to_default()
    return {"ok": True, "stats": payment_manager.get_stats()}


@app.get("/api/events")
async def stream_events():
    """SSE endpoint streaming live AgentPay events to web frontend."""
    return StreamingResponse(
        event_bus.subscribe(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# CLI Demonstration Mode
async def run_cli_demo(lang: str = "zh"):
    is_en = (lang or "").lower().startswith("en")
    print("=" * 70)
    print("  🚀 AgentPay Financial Firewall Demo (CLI Mode)")
    print("  Protocol: x402 V2 | Network: Arbitrum Sepolia")
    print(f"  Language: {'English' if is_en else '简体中文'}")
    print("=" * 70)

    # Use in-memory transport so CLI doesn't even need a separate web server
    import httpx

    payment_manager.set_custom_transport(httpx.ASGITransport(app=app))
    runner = get_agent_runner()
    scenarios_list = get_localized_scenarios(lang)

    while True:
        if is_en:
            print("\nPreset Demonstration Scenarios:")
            for idx, sc in enumerate(scenarios_list, 1):
                print(f"  [{idx}] {sc['title']} - [{sc['badge']}]")
            print("  [L] Switch Language (中/EN)")
            print("  [0] Exit")
            choice = input("\nSelect scenario number (0-5), 'L' to switch language, or enter natural language question: ").strip()
        else:
            print("\n预设演示场景:")
            for idx, sc in enumerate(scenarios_list, 1):
                print(f"  [{idx}] {sc['title']} - [{sc['badge']}]")
            print("  [L] 切换语言 (中/EN)")
            print("  [0] 退出")
            choice = input("\n请选择场景编号 (0-5)、'L' 切换语言，或直接输入自然语言提问: ").strip()

        if not choice:
            continue
        if choice == "0":
            print("Exiting demo." if is_en else "退出演示。")
            break
        if choice.upper() == "L":
            is_en = not is_en
            lang = "en" if is_en else "zh"
            scenarios_list = get_localized_scenarios(lang)
            print(f"---> Switched language to: {'English' if is_en else '简体中文'}")
            continue

        if choice in [str(i) for i in range(1, len(scenarios_list) + 1)]:
            sc = scenarios_list[int(choice) - 1]
            print(f"\n---> {'Applying policy setup' if is_en else '正在应用场景策略'}: {sc['title']}")
            apply_scenario_setup(sc["id"])
            query = sc["prompt"]
            print(f"---> {'User Query' if is_en else '用户提问'}: {query}")
        else:
            query = choice

        print(f"\n[{'Agent is thinking & executing...' if is_en else 'Agent 思考与执行中...'}]")
        res = await runner.chat(query, lang=lang)

        print("\n" + "=" * 50)
        print(f"🤖 {'Agent Response' if is_en else 'Agent 回复'}:\n")
        print(res["response"])
        print("=" * 50)

        stats = payment_manager.get_stats()
        if is_en:
            print(
                f"\n📊 [Current Firewall Status] 24h Spent: {stats['spent_budget_formatted']} / "
                f"{stats['rolling_budget_24h_formatted']} | Breaker: {stats['breaker_state']}"
            )
        else:
            print(
                f"\n📊 [当前防火墙状态] 24h 已花费: {stats['spent_budget_formatted']} / "
                f"{stats['rolling_budget_24h_formatted']} | 熔断状态: {stats['breaker_state']}"
            )


def main():
    parser = argparse.ArgumentParser(description="AgentPay Demo Server & CLI")
    parser.add_argument("--cli", action="store_true", help="Run interactive CLI demo mode")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="Language for CLI demo (zh or en)")
    parser.add_argument("--host", default=settings.GATEWAY_HOST, help="Server host")
    parser.add_argument("--port", type=int, default=settings.GATEWAY_PORT, help="Server port")
    args = parser.parse_args()

    if args.cli:
        asyncio.run(run_cli_demo(lang=args.lang))
    else:
        print(f"🌟 Starting AgentPay Demo Web Server on http://{args.host}:{args.port}")
        uvicorn.run("app:app", host=args.host, port=args.port, reload=True)


if __name__ == "__main__":
    main()
