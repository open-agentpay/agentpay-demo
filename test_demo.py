import asyncio
import httpx
from app import app
from payment.manager import payment_manager
from scenarios.manager import apply_scenario_setup
from agent.runner import get_agent_runner


async def test_all_scenarios():
    print("==================================================")
    print("   Starting Automated AgentPay Verification Suite")
    print("   (Tools: Simple Weather & Constellation)")
    print("==================================================")

    # Attach in-memory ASGI transport so tests run self-contained
    transport = httpx.ASGITransport(app=app)
    payment_manager.set_custom_transport(transport)
    runner = get_agent_runner()

    # -----------------------------------------------------------------
    # Test 1: Scenario 1 - Single Weather Micro-Payment (Happy Path)
    # -----------------------------------------------------------------
    print("\n[TEST 1] Scenario 1: Single Weather Micro-Payment (/api/v1/simple-weather)")
    apply_scenario_setup("scenario_1")
    stats_before = payment_manager.get_stats()
    assert stats_before["spent_budget_base_units"] == 0

    res = await runner.chat("今天北京天气怎么样？")
    assert res is not None
    assert len(res["tool_calls"]) == 1
    call = res["tool_calls"][0]
    assert call["result"]["ok"] is True
    assert call["args"]["city"] == "北京"
    assert "晴" in res["response"] or "Sunny" in res["response"] or "8" in res["response"]

    stats_after = payment_manager.get_stats()
    assert stats_after["spent_budget_base_units"] == 50_000  # Weather costs 50,000 base units ($0.05)
    print("  ✅ Scenario 1 Passed: 402 Handshake -> Sign -> 200 OK -> $0.05 USDC Settled")

    # -----------------------------------------------------------------
    # Test 2: Scenario 2 - Weather + Constellation (Multi-Tool)
    # -----------------------------------------------------------------
    print("\n[TEST 2] Scenario 2: Weather + Constellation Multi-Tool")
    apply_scenario_setup("scenario_2")
    res = await runner.chat("早安，帮我准备今天的简报，包含北京天气和摩羯座今日运势。")
    assert len(res["tool_calls"]) == 2
    for tc in res["tool_calls"]:
        assert tc["result"]["ok"] is True
        if tc["tool"] == "get_weather":
            assert tc["args"]["city"] == "北京"
        elif tc["tool"] == "get_horoscope":
            assert tc["args"]["consName"] == "摩羯座"

    stats_after2 = payment_manager.get_stats()
    # 50,000 (weather) + 100,000 (horoscope) = 150,000 base units ($0.15)
    assert stats_after2["spent_budget_base_units"] == 150_000
    print("  ✅ Scenario 2 Passed: 2 Paid tools called, Total $0.15 USDC Settled")

    # -----------------------------------------------------------------
    # Test 3: Scenario 3 - Budget Exhaustion & Fallback (Budget = 70,000)
    # -----------------------------------------------------------------
    print("\n[TEST 3] Scenario 3: Budget Exhaustion (Budget = 70,000 base units)")
    apply_scenario_setup("scenario_3")
    res = await runner.chat("帮我准备今天的简报（包含天气和摩羯座运势）。")
    # Weather (50,000) -> OK. Horoscope (100,000) -> 50,000+100,000 > 70,000 -> Blocked!
    blocked_calls = [tc for tc in res["tool_calls"] if not tc["result"]["ok"]]
    assert len(blocked_calls) > 0
    assert "FINANCIAL_POLICY_BLOCKED" in [tc["result"].get("error_code") for tc in blocked_calls]
    assert "DAILY_BUDGET_EXCEEDED" in [tc["result"].get("rule") for tc in blocked_calls]
    assert "安全拦截报告" in res["response"] or "Fail-Closed" in res["response"]

    stats_after3 = payment_manager.get_stats()
    # Spend cannot exceed 70,000
    assert stats_after3["spent_budget_base_units"] <= 70_000
    print("  ✅ Scenario 3 Passed: Zero overrun, Fail-Closed strictly enforced")

    # -----------------------------------------------------------------
    # Test 4: Scenario 4 - Single-Tx Cap (Cap = 80,000 base units)
    # -----------------------------------------------------------------
    print("\n[TEST 4] Scenario 4: Single-Tx Cap (Cap = 80,000 base units)")
    apply_scenario_setup("scenario_4")
    res = await runner.chat("查询摩羯座今日运势。")
    # Horoscope costs 100,000 > 80,000 -> Blocked!
    call = res["tool_calls"][0]
    assert call["result"]["ok"] is False
    assert call["args"]["consName"] == "摩羯座"
    assert call["result"]["rule"] == "SINGLE_TX_CAP_EXCEEDED"
    print("  ✅ Scenario 4 Passed: Horoscope ($0.10) rejected by single-tx limit ($0.08)")

    # -----------------------------------------------------------------
    # Test 5: Scenario 5 - Circuit Breaker Protection (3 RPM)
    # -----------------------------------------------------------------
    print("\n[TEST 5] Scenario 5: Circuit Breaker Protection")
    apply_scenario_setup("scenario_5")
    res = await runner.chat("请快速连续查询天气状况！")
    breaker_blocks = [tc for tc in res["tool_calls"] if tc["result"].get("rule") == "CIRCUIT_BREAKER_OPEN"]
    assert len(breaker_blocks) > 0
    assert breaker_blocks[0]["args"]["city"] == "北京"
    print("  ✅ Scenario 5 Passed: Rapid loop tripped circuit breaker, wallet protected")

    # -----------------------------------------------------------------
    # Test 6: API Endpoints Verification
    # -----------------------------------------------------------------
    print("\n[TEST 6] Testing FastAPI REST Endpoints")
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # Scenarios endpoint
        resp = await client.get("/api/scenarios")
        assert resp.status_code == 200
        assert len(resp.json()["scenarios"]) == 5

        # Stats endpoint
        resp = await client.get("/api/stats")
        assert resp.status_code == 200
        assert "wallet_address" in resp.json()

        # Reset endpoint
        resp = await client.post("/api/policy/reset")
        assert resp.status_code == 200
        assert resp.json()["stats"]["spent_budget_base_units"] == 0

        # Chat endpoint (Chinese)
        resp = await client.post("/api/chat", json={"message": "今天北京天气怎么样？"})
        assert resp.status_code == 200
        assert resp.json()["ok"] is True
    print("  ✅ Test 6 Passed: All REST APIs operational")

    # -----------------------------------------------------------------
    # Test 7: Internationalization (i18n) Bilingual Suite
    # -----------------------------------------------------------------
    print("\n[TEST 7] Testing Internationalization (i18n) Features & Simplified Chinese Tool Args")
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. English Scenarios Endpoint
        en_sc_resp = await client.get("/api/scenarios?lang=en")
        assert en_sc_resp.status_code == 200
        en_scenarios = en_sc_resp.json()["scenarios"]
        assert len(en_scenarios) == 5
        assert "Weather" in en_scenarios[0]["title"]
        assert "Scenario 1" in en_scenarios[0]["title"]
        assert "How is the weather" in en_scenarios[0]["prompt"]
        assert "Happy Path" in en_scenarios[0]["badge"]

        # 2. English Chat Endpoint (Happy Path): Verify tool arg is Simplified Chinese
        apply_scenario_setup("scenario_1")
        en_chat_resp = await client.post(
            "/api/chat",
            json={"message": "How is the weather in Beijing today?", "lang": "en"},
        )
        assert en_chat_resp.status_code == 200
        chat_data = en_chat_resp.json()
        assert chat_data["ok"] is True
        assert chat_data["lang"] == "en"
        # Tool call parameter MUST be Simplified Chinese ("北京")
        assert len(chat_data["tool_calls"]) == 1
        assert chat_data["tool_calls"][0]["args"]["city"] == "北京"
        # Synthesized response in English
        assert "Today's Morning Briefing is Ready" in chat_data["response"]
        assert "Beijing" in chat_data["response"]

        # 3. English Multi-Tool: Verify both city and consName are Simplified Chinese
        apply_scenario_setup("scenario_2")
        en_multi_resp = await client.post(
            "/api/chat",
            json={
                "message": "Prepare today's morning briefing with Shanghai weather and Leo horoscope.",
                "lang": "en",
            },
        )
        assert en_multi_resp.status_code == 200
        multi_data = en_multi_resp.json()
        assert multi_data["ok"] is True
        for tc in multi_data["tool_calls"]:
            if tc["tool"] == "get_weather":
                assert tc["args"]["city"] == "上海"
            elif tc["tool"] == "get_horoscope":
                assert tc["args"]["consName"] == "狮子座"

        # 4. English Budget Interception: Fail-closed verification
        apply_scenario_setup("scenario_3")
        en_budget_resp = await client.post(
            "/api/chat",
            json={
                "message": "Prepare today's morning briefing with Beijing weather and Capricorn horoscope.",
                "lang": "en",
            },
        )
        assert en_budget_resp.status_code == 200
        budget_data = en_budget_resp.json()
        assert budget_data["ok"] is True
        assert "Financial Firewall Security Interception Report" in budget_data["response"]
        assert "Fail-Closed" in budget_data["response"]

    print("  ✅ Test 7 Passed: Tool parameters strictly use Simplified Chinese, UI in English")

    print("\n" + "=" * 50)
    print("🎉 ALL 7 VERIFICATION TEST SUITES PASSED PERFECTLY!")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(test_all_scenarios())
