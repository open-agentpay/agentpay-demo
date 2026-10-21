// AgentPay Demo Frontend Logic with Bilingual i18n (Chinese & English)

const I18N = {
  zh: {
    page_title: "AgentPay 晨间简报验证 Demo - 金融防火墙与自主微支付",
    nav_title: "AgentPay Autonomous Micro-Payment Demo",
    nav_subtitle: "智能体自主微支付与 Zero-Trust 金融防火墙落地演示",
    sse_feed_label: "SSE 实时流:",
    sse_connected: "已连接",
    sse_live: "实时推流中",
    sse_reconnecting: "重连中...",
    btn_reset_policy: "重置默认策略",
    scenarios_bar_title: "⚡ 核心验证场景一键触发 (Click to Test)",
    scenarios_bar_subtitle: "零配置即刻体验",
    welcome_greeting: "你好！我是集成 AgentPay 金融防火墙的晨间简报智能体。",
    welcome_desc: "在接下来的交互中，我会自主调用后端受保护的付费 API（天气查询 /api/v1/simple-weather、星座运势 /api/v1/constellation）。每一次调用都会经历底层的 <span class='text-indigo-400 font-mono font-medium'>HTTP 402 → EIP-712/3009 离线签名 → 自动代付与放行</span>。",
    welcome_tip: "你可以直接在上方选择 <span class='text-amber-400 font-medium'>预设验证场景</span>，测试正常支付、单笔超限拦截、预算不足降级以及高频熔断保护！",
    chat_input_placeholder: "输入指令，例如: 帮我准备今天的简报，包含北京天气和摩羯座运势...",
    btn_send: "发送",
    thinking: "正在规划与执行 AgentPay 付费请求...",
    trace_heading: "🔧 智能体工具调用轨迹 (x402 Trace)",
    trace_settled: "✅ 支付放行",
    trace_blocked: "🛡️ 防火墙拦截",
    dashboard_title: "金融防火墙与微支付审计看板",
    metric_budget_label: "24H 滚动预算",
    metric_avail_label: "可用额度:",
    metric_breaker_label: "熔断与单笔限额",
    metric_cap_label: "单笔上限:",
    metric_rpm_label: "频率限制:",
    metric_fail_closed_label: "Fail-Closed 模式:",
    metric_fail_closed_val: "已激活 🔒",
    live_feed_heading: "实时微支付审计流 (Live x402 Feed)",
    records_count: "条记录",
    feed_empty_text: "等待支付请求发起...",
    matrix_heading: "Zero-Trust 策略白名单矩阵 (Read-Only)",
    mat_network: "WHITELIST_NETWORKS",
    mat_asset: "WHITELIST_ASSET",
    mat_payee: "PAYEE_WHITELIST",
    mat_engine: "ENGINE_TYPE",
    policy_reset_msg: "策略与账本已重置为系统默认值。",
    switch_scenario_prefix: "已切换为【",
    switch_scenario_middle: "】策略配置：",
    lang_switched_toast: "界面语言已切换为：简体中文",
    error_prefix: "错误: ",
    net_error_prefix: "网络请求异常: ",
  },
  en: {
    page_title: "AgentPay Morning Briefing Demo - Financial Firewall & Autonomous Micro-Payments",
    nav_title: "AgentPay Autonomous Micro-Payment Demo",
    nav_subtitle: "Zero-Trust Financial Firewall for Autonomous AI Agents",
    sse_feed_label: "SSE Feed:",
    sse_connected: "Connected",
    sse_live: "Live",
    sse_reconnecting: "Reconnecting...",
    btn_reset_policy: "Reset Default Policy",
    scenarios_bar_title: "⚡ Core Validation Scenarios (Click to Test)",
    scenarios_bar_subtitle: "Instant Zero-Config Experience",
    welcome_greeting: "Hello! I am the Morning Briefing Agent integrated with the AgentPay Financial Firewall.",
    welcome_desc: "During interactions, I autonomously invoke protected paid APIs (/api/v1/simple-weather, /api/v1/constellation). Each call goes through underlying <span class='text-indigo-400 font-mono font-medium'>HTTP 402 → EIP-712/3009 Offline Signing → Autonomous Settlement</span>.",
    welcome_tip: "You can click any of the <span class='text-amber-400 font-medium'>Preset Scenarios</span> above to test settled micro-payments, single-tx cap enforcement, daily budget limits, and circuit breaker protection!",
    chat_input_placeholder: "Type a prompt, e.g.: Prepare today's briefing with Beijing weather and Capricorn horoscope...",
    btn_send: "Send",
    thinking: "Planning & executing AgentPay micro-payment requests...",
    trace_heading: "🔧 Agent Tool Call Trace (x402 Trace)",
    trace_settled: "✅ Payment Settled",
    trace_blocked: "🛡️ Firewall Blocked",
    dashboard_title: "Financial Firewall & Micro-Payment Audit Dashboard",
    metric_budget_label: "24H Rolling Budget",
    metric_avail_label: "Available Budget:",
    metric_breaker_label: "Circuit Breaker & Cap",
    metric_cap_label: "Single-Tx Cap:",
    metric_rpm_label: "Rate Limit:",
    metric_fail_closed_label: "Fail-Closed Mode:",
    metric_fail_closed_val: "Active 🔒",
    live_feed_heading: "Live Micro-Payment Audit Feed (x402)",
    records_count: "records",
    feed_empty_text: "Waiting for payment requests...",
    matrix_heading: "Zero-Trust Policy Matrix (Read-Only)",
    mat_network: "WHITELIST_NETWORKS",
    mat_asset: "WHITELIST_ASSET",
    mat_payee: "PAYEE_WHITELIST",
    mat_engine: "ENGINE_TYPE",
    policy_reset_msg: "Policy and ledger have been reset to system defaults.",
    switch_scenario_prefix: "Switched to [",
    switch_scenario_middle: "] policy setup: ",
    lang_switched_toast: "Interface language switched to: English",
    error_prefix: "Error: ",
    net_error_prefix: "Network error: ",
  },
};

let currentLang = localStorage.getItem("agentpay_demo_lang") || "zh";
let scenarios = [];
let feedItemsCount = 0;

document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
  applyTranslations();
  initSSE();
  fetchScenarios();
  fetchStats();
  setupEventListeners();
});

// Setup DOM Event Listeners
function setupEventListeners() {
  const form = document.getElementById("chat-form");
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const input = document.getElementById("chat-input");
    const msg = input.value.trim();
    if (!msg) return;
    input.value = "";
    await sendMessage(msg);
  });

  const btnReset = document.getElementById("btn-reset-policy");
  btnReset.addEventListener("click", async () => {
    try {
      const res = await fetch("/api/policy/reset", { method: "POST" });
      const data = await res.json();
      if (data.ok) {
        appendSystemMessage(I18N[currentLang].policy_reset_msg);
        updateDashboard(data.stats);
      }
    } catch (err) {
      console.error("Reset failed", err);
    }
  });

  // Segmented language switch buttons
  const btnZh = document.getElementById("lang-btn-zh");
  const btnEn = document.getElementById("lang-btn-en");
  if (btnZh) {
    btnZh.addEventListener("click", () => setLanguage("zh"));
  }
  if (btnEn) {
    btnEn.addEventListener("click", () => setLanguage("en"));
  }
}

// Set active language
function setLanguage(lang) {
  if (currentLang === lang) return;
  currentLang = lang;
  localStorage.setItem("agentpay_demo_lang", currentLang);
  applyTranslations();
  renderScenarioButtons();
  appendSystemMessage(I18N[currentLang].lang_switched_toast);
  if (window.lucide) {
    lucide.createIcons();
  }
}

// Apply text translations across the document
function applyTranslations() {
  const t = I18N[currentLang] || I18N.zh;
  document.documentElement.lang = currentLang === "zh" ? "zh-CN" : "en";
  document.title = t.page_title;

  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (t[key] !== undefined) {
      el.innerHTML = t[key];
    }
  });

  document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const key = el.getAttribute("data-i18n-placeholder");
    if (t[key] !== undefined) {
      el.placeholder = t[key];
    }
  });

  // Update segmented control buttons state
  const btnZh = document.getElementById("lang-btn-zh");
  const btnEn = document.getElementById("lang-btn-en");
  if (btnZh && btnEn) {
    if (currentLang === "zh") {
      btnZh.className = "px-2.5 py-1 rounded-md transition font-medium text-white bg-indigo-600 shadow-sm flex items-center gap-1";
      btnEn.className = "px-2.5 py-1 rounded-md transition font-medium text-slate-400 hover:text-slate-200 flex items-center gap-1";
    } else {
      btnZh.className = "px-2.5 py-1 rounded-md transition font-medium text-slate-400 hover:text-slate-200 flex items-center gap-1";
      btnEn.className = "px-2.5 py-1 rounded-md transition font-medium text-white bg-indigo-600 shadow-sm flex items-center gap-1";
    }
  }

  // Welcome message content
  const welcomeContent = document.getElementById("welcome-content");
  if (welcomeContent) {
    welcomeContent.innerHTML = `
      <p class="font-semibold text-slate-200">${t.welcome_greeting}</p>
      <p class="text-slate-300">${t.welcome_desc}</p>
      <p class="text-slate-400 text-xs">${t.welcome_tip}</p>
    `;
  }

  // Feed count label
  const feedCount = document.getElementById("feed-count");
  if (feedCount) {
    feedCount.innerText = `${feedItemsCount} ${t.records_count}`;
  }

  // Empty state in live feed if empty
  const emptyState = document.getElementById("feed-empty-item");
  if (emptyState) {
    emptyState.innerText = t.feed_empty_text;
  }
}

// Fetch Scenario Presets from backend
async function fetchScenarios() {
  try {
    const res = await fetch("/api/scenarios");
    const data = await res.json();
    scenarios = data.scenarios || [];
    renderScenarioButtons();
  } catch (err) {
    console.error("Failed to fetch scenarios", err);
  }
}

// Render Scenario Buttons in the Top Bar based on active language
function renderScenarioButtons() {
  const container = document.getElementById("scenarios-container");
  if (!container) return;
  container.innerHTML = "";

  const isEn = currentLang === "en";

  scenarios.forEach((sc, idx) => {
    const title = isEn ? (sc.title_en || sc.title) : (sc.title_zh || sc.title);
    const badge = isEn ? (sc.badge_en || sc.badge) : (sc.badge_zh || sc.badge);
    const desc = isEn ? (sc.description_en || sc.description) : (sc.description_zh || sc.description);

    const titleMain = title.includes(":") ? title.split(":")[0] : title;
    const titleSub = title.includes(":") ? title.split(":")[1] : desc;

    const btn = document.createElement("button");
    btn.className = `text-left p-2 rounded-lg border transition text-xs flex flex-col justify-between 
      ${idx === 0 ? "border-emerald-500/40 bg-emerald-500/10 hover:bg-emerald-500/20" : 
        idx === 1 ? "border-blue-500/40 bg-blue-500/10 hover:bg-blue-500/20" : 
        idx === 2 ? "border-amber-500/40 bg-amber-500/10 hover:bg-amber-500/20" : 
        idx === 3 ? "border-rose-500/40 bg-rose-500/10 hover:bg-rose-500/20" : 
        "border-purple-500/40 bg-purple-500/10 hover:bg-purple-500/20"}`;

    btn.title = desc;

    btn.innerHTML = `
      <div class="flex items-center justify-between w-full mb-1">
        <span class="font-bold text-slate-200 truncate">${escapeHtml(titleMain)}</span>
        <span class="text-[9px] px-1 py-0.2 rounded font-mono font-semibold 
          ${idx === 0 ? "bg-emerald-500/30 text-emerald-300" : 
            idx === 1 ? "bg-blue-500/30 text-blue-300" : 
            idx === 2 ? "bg-amber-500/30 text-amber-300" : 
            idx === 3 ? "bg-rose-500/30 text-rose-300" : 
            "bg-purple-500/30 text-purple-300"}">${escapeHtml(badge)}</span>
      </div>
      <span class="text-[10px] text-slate-400 line-clamp-1">${escapeHtml(titleSub)}</span>
    `;

    btn.addEventListener("click", async () => {
      await triggerScenario(sc);
    });

    container.appendChild(btn);
  });
}

// Trigger Scenario Execution
async function triggerScenario(scenario) {
  const t = I18N[currentLang] || I18N.zh;
  const isEn = currentLang === "en";
  const title = isEn ? (scenario.title_en || scenario.title) : (scenario.title_zh || scenario.title);
  const desc = isEn ? (scenario.description_en || scenario.description) : (scenario.description_zh || scenario.description);
  const prompt = isEn ? (scenario.prompt_en || scenario.prompt) : (scenario.prompt_zh || scenario.prompt);

  try {
    // 1. Apply scenario policy setup
    const setupRes = await fetch(`/api/scenarios/${scenario.id}/apply`, { method: "POST" });
    const setupData = await setupRes.json();
    if (setupData.ok) {
      updateDashboard(setupData.current_stats);
      appendSystemMessage(`${t.switch_scenario_prefix}${title}${t.switch_scenario_middle}${desc}`);
    }

    // 2. Autofill and send message
    document.getElementById("chat-input").value = prompt;
    await sendMessage(prompt);
  } catch (err) {
    console.error("Failed to trigger scenario", err);
  }
}

// Send Message to Agent
async function sendMessage(text) {
  const t = I18N[currentLang] || I18N.zh;
  appendUserMessage(text);
  const sendBtn = document.getElementById("btn-send");
  sendBtn.disabled = true;
  sendBtn.classList.add("opacity-50");

  const loaderId = appendThinkingIndicator();

  try {
    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text, lang: currentLang }),
    });
    const data = await res.json();
    removeThinkingIndicator(loaderId);

    if (data.ok) {
      appendAgentResponse(data.response, data.tool_calls);
    } else {
      appendSystemMessage(`${t.error_prefix}${data.error || "Unknown error"}`);
    }
    // Refresh stats after conversation
    await fetchStats();
  } catch (err) {
    removeThinkingIndicator(loaderId);
    appendSystemMessage(`${t.net_error_prefix}${err.message}`);
  } finally {
    sendBtn.disabled = false;
    sendBtn.classList.remove("opacity-50");
  }
}

// Fetch Policy Stats
async function fetchStats() {
  try {
    const res = await fetch("/api/stats");
    const data = await res.json();
    updateDashboard(data);
  } catch (err) {
    console.error("Failed to fetch stats", err);
  }
}

// Update Financial Dashboard UI
function updateDashboard(stats) {
  if (!stats) return;

  // Wallet & Agent Key
  const w = stats.wallet_address || "0x90f8...c1";
  document.getElementById("wallet-display").innerText = `${w.slice(0, 6)}...${w.slice(-4)}`;

  const ak = stats.agent_key || "";
  const akEl = document.getElementById("agent-key-display");
  if (akEl && ak) {
    akEl.innerText = `${ak.slice(0, 8)}...${ak.slice(-4)}`;
    akEl.title = `Agent Key: ${ak}`;
  }

  // Budget
  document.getElementById("metric-spent-budget").innerText = stats.spent_budget_formatted || "$0.0000";
  document.getElementById("metric-total-budget").innerText = `/ ${stats.rolling_budget_24h_formatted || "$0.1000"}`;
  document.getElementById("metric-avail-budget").innerText = stats.available_budget_formatted || "$0.1000 USDC";

  const percent = stats.spent_percentage || 0;
  document.getElementById("metric-budget-percent").innerText = `${percent}%`;
  const bar = document.getElementById("budget-progress-bar");
  bar.style.width = `${Math.min(100, percent)}%`;

  if (percent > 90) {
    bar.className = "bg-gradient-to-r from-rose-500 to-amber-500 h-full transition-all duration-500";
  } else {
    bar.className = "bg-gradient-to-r from-emerald-500 to-indigo-500 h-full transition-all duration-500";
  }

  // Cap & Breaker
  document.getElementById("metric-max-per-tx").innerText = stats.max_per_tx_formatted || "$0.0100 USDC";
  document.getElementById("metric-circuit-rpm").innerText = `${stats.circuit_max_rpm || 20} RPM`;

  const badge = document.getElementById("breaker-badge");
  const state = stats.breaker_state || "CLOSED";
  badge.innerText = state;
  if (state === "OPEN") {
    badge.className = "text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-400 border border-rose-500/30";
  } else if (state === "HALF_OPEN") {
    badge.className = "text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30";
  } else {
    badge.className = "text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30";
  }
}

// Server-Sent Events (SSE) Stream
function initSSE() {
  const evtSource = new EventSource("/api/events");
  const sseStatus = document.getElementById("sse-status");

  evtSource.onopen = () => {
    const t = I18N[currentLang] || I18N.zh;
    sseStatus.innerText = t.sse_live;
    sseStatus.className = "text-emerald-400 font-mono";
  };

  evtSource.onerror = () => {
    const t = I18N[currentLang] || I18N.zh;
    sseStatus.innerText = t.sse_reconnecting;
    sseStatus.className = "text-amber-400 font-mono";
  };

  evtSource.onmessage = (event) => {
    try {
      const parsed = JSON.parse(event.data);
      handleLiveEvent(parsed);
    } catch (e) {
      console.error("SSE parse error", e);
    }
  };
}

// Handle Realtime Events from EventBus
function handleLiveEvent(evt) {
  const type = evt.type;
  const data = evt.data || {};
  const time = evt.time_str || new Date().toLocaleTimeString();
  const isEn = currentLang === "en";

  if (type === "TOOL_EXECUTION_SUCCESS" || type === "PAYMENT_SETTLED") {
    addFeedItem({
      time: time,
      title: data.url || data.resource || "Payment Settled",
      cost: data.cost_formatted || data.amount_formatted || "$0.0010 USDC",
      status: "200 OK",
      statusClass: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
      detail: `Challenge ID: ${data.receipt ? data.receipt.challenge_id : (data.challenge_id || 'ch_settled')} • Latency: ${data.duration_ms || 42}ms`,
    });
    fetchStats();
  } else if (type === "POLICY_BLOCKED") {
    const explanation = isEn 
      ? (data.explanation_en || data.explanation || "Financial firewall rejected payment") 
      : (data.explanation_zh || data.explanation || "金融防火墙拒绝支付");

    addFeedItem({
      time: time,
      title: data.url || "Firewall Blocked",
      cost: "$0.0000",
      status: `BLOCKED: ${data.rule_violated}`,
      statusClass: "text-rose-400 bg-rose-500/10 border-rose-500/20",
      detail: explanation,
    });
    fetchStats();
  } else if (type === "POLICY_CONFIG_UPDATED") {
    fetchStats();
  }
}

function addFeedItem(item) {
  const feed = document.getElementById("live-feed");
  const t = I18N[currentLang] || I18N.zh;
  if (feedItemsCount === 0) {
    feed.innerHTML = "";
  }
  feedItemsCount++;
  document.getElementById("feed-count").innerText = `${feedItemsCount} ${t.records_count}`;

  const div = document.createElement("div");
  div.className = "bg-slate-950/80 border border-slate-800/90 rounded-lg p-2.5 text-xs space-y-1 animate-fadeIn";
  div.innerHTML = `
    <div class="flex items-center justify-between font-mono">
      <div class="flex items-center gap-1.5">
        <span class="text-slate-500 text-[10px]">${item.time}</span>
        <span class="font-semibold text-slate-200">${item.title}</span>
      </div>
      <span class="px-1.5 py-0.5 rounded text-[10px] border font-semibold ${item.statusClass}">${item.status}</span>
    </div>
    <div class="flex items-center justify-between text-[11px] text-slate-400">
      <span class="truncate max-w-[240px] text-slate-400" title="${escapeHtml(item.detail)}">${escapeHtml(item.detail)}</span>
      <span class="font-mono text-indigo-300 font-medium">${item.cost}</span>
    </div>
  `;

  feed.prepend(div);
}

// UI Chat Helpers
function appendUserMessage(text) {
  const container = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "flex items-start justify-end gap-3";
  div.innerHTML = `
    <div class="bg-indigo-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[80%] text-sm shadow-md">
      ${escapeHtml(text)}
    </div>
    <div class="w-7 h-7 rounded-full bg-slate-700 flex items-center justify-center shrink-0 text-white font-bold text-xs">
      👤
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendThinkingIndicator() {
  const t = I18N[currentLang] || I18N.zh;
  const container = document.getElementById("chat-messages");
  const id = `loader-${Date.now()}`;
  const div = document.createElement("div");
  div.id = id;
  div.className = "flex items-start gap-3";
  div.innerHTML = `
    <div class="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 text-white font-bold text-xs">
      🤖
    </div>
    <div class="bg-slate-900 border border-slate-800 rounded-2xl px-4 py-3 text-sm text-slate-400 flex items-center gap-2">
      <span class="w-2 h-2 rounded-full bg-indigo-400 pulse-dot"></span>
      <span>${t.thinking}</span>
    </div>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return id;
}

function removeThinkingIndicator(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function appendAgentResponse(markdownText, toolCalls) {
  const t = I18N[currentLang] || I18N.zh;
  const container = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "flex items-start gap-3";

  let toolCallsHtml = "";
  if (toolCalls && toolCalls.length > 0) {
    const cards = toolCalls.map(tc => {
      const ok = tc.result && tc.result.ok;
      const toolName = tc.tool;
      const statusBadge = ok 
        ? `<span class="text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.2 rounded text-[10px]">${t.trace_settled}</span>`
        : `<span class="text-rose-400 bg-rose-500/10 border border-rose-500/20 px-1.5 py-0.2 rounded text-[10px]">${t.trace_blocked}</span>`;
      return `
        <div class="bg-slate-950/70 border border-slate-800 rounded-lg p-2 text-xs flex items-center justify-between">
          <span class="font-mono text-slate-300">Tool: <strong class="text-indigo-400">${toolName}</strong></span>
          ${statusBadge}
        </div>
      `;
    }).join("");

    toolCallsHtml = `
      <div class="mb-3 space-y-1.5 border-b border-slate-800/80 pb-2.5">
        <span class="text-[11px] text-slate-400 font-semibold uppercase tracking-wider block mb-1">${t.trace_heading}</span>
        ${cards}
      </div>
    `;
  }

  div.innerHTML = `
    <div class="w-7 h-7 rounded-full bg-indigo-600 flex items-center justify-center shrink-0 text-white font-bold text-xs">
      🤖
    </div>
    <div class="bg-slate-900 border border-slate-800 rounded-2xl p-4 max-w-[85%] text-sm space-y-2 leading-relaxed">
      ${toolCallsHtml}
      <div class="text-slate-200 whitespace-pre-wrap">${escapeHtml(markdownText)}</div>
    </div>
  `;

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function appendSystemMessage(text) {
  const container = document.getElementById("chat-messages");
  const div = document.createElement("div");
  div.className = "flex justify-center my-2";
  div.innerHTML = `
    <span class="text-[11px] bg-slate-800/80 text-slate-400 border border-slate-700/60 rounded-full px-3 py-1">
      ${escapeHtml(text)}
    </span>
  `;
  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(string) {
  if (string === null || string === undefined) return "";
  const entityMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
    "/": "&#x2F;"
  };
  return String(string).replace(/[&<>"'\/]/g, s => entityMap[s]);
}
