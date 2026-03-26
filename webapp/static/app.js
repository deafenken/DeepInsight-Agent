const state = { companies: [], years: [], stats: {}, deepseekEnabled: false, history: [], lastWorkflowMarkdown: "", lastChatResult: null, chatContext: { companyName: "", reportYear: "", macro: false, compareCompanies: [] } };
const stages = ["正在理解问题并匹配企业、年份与上下文", "正在检索财务数据、年报原文和宏观指标", "正在生成结论并整理可追溯证据"];
const CHAT_HISTORY_KEY = "pharma_ai_web_history_v1";

function $(id) { return document.getElementById(id); }

function escapeHtml(value = "") {
  return value.replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;");
}

function escapeAttr(value = "") {
  return escapeHtml(String(value)).replaceAll("'", "&#39;");
}

function renderMarkdown(markdown = "") {
  const blocks = markdown.split(/\n\s*\n/).filter(Boolean);
  return blocks.map((block) => {
    if (block.startsWith("### ")) return `<h3>${escapeHtml(block.slice(4))}</h3>`;
    if (block.startsWith("## ")) return `<h2>${escapeHtml(block.slice(3))}</h2>`;
    const lines = block.split("\n");
    if (lines.every((line) => line.trim().startsWith("- "))) {
      return `<ul>${lines.map((line) => `<li>${escapeHtml(line.trim().slice(2))}</li>`).join("")}</ul>`;
    }
    return `<p>${escapeHtml(block).replaceAll("\n", "<br>")}</p>`;
  }).join("");
}

function extractSection(markdown, title) {
  const match = markdown.match(new RegExp(`### ${title}\\n([\\s\\S]+?)(?:\\n### |$)`));
  return match ? match[1].trim() : "";
}

function extractSummary(markdown) {
  const text = extractSection(markdown, "摘要判断") || extractSection(markdown, "快速结论");
  return text ? text.split("\n").slice(0, 3).join("；").replaceAll("- ", "") : "";
}

function extractMetricCards(markdown) {
  const text = extractSection(markdown, "关键指标");
  if (!text) return [];
  return text.split("\n").filter((line) => line.trim().startsWith("- ")).slice(0, 4).map((line) => {
    const content = line.trim().slice(2);
    const parts = content.split("：");
    return { label: parts[0] || "指标", value: parts.slice(1).join("：") || "已命中指标" };
  });
}

function buildChips(result, question) {
  const chips = [];
  const push = (value) => { if (value && !chips.includes(value)) chips.push(value); };
  [...question.matchAll(/20\d{2}/g)].slice(0, 2).forEach((item) => push(`${item[0]}年`));
  (result.sql_rows || []).forEach((row) => push(row.company_name));
  if ((result.macro_rows || []).length) push("宏观联动");
  if (result.route === "hybrid") push("双库协同");
  if (result.route === "sql") push("结构化检索");
  if (result.route === "vector") push("向量检索");
  return chips.slice(0, 6);
}

function inferChatContext(question, result) {
  const context = { ...state.chatContext };
  const explicitCompany = $("companySelect").value || "";
  const explicitYear = $("yearSelect").value || "";
  const companyMatches = [...new Set((result.sql_rows || []).map((row) => row.company_name).filter(Boolean))];
  if (explicitCompany) context.companyName = explicitCompany;
  else if (companyMatches.length) context.companyName = companyMatches[0];
  if (explicitYear) context.reportYear = explicitYear;
  else {
    const matchedYear = question.match(/20\d{2}/);
    if (matchedYear) context.reportYear = matchedYear[0];
  }
  context.macro = Boolean((result.macro_rows || []).length) || /宏观|卫生|环境|影响/.test(question);
  context.compareCompanies = companyMatches.slice(0, 2);
  state.chatContext = context;
}

function enrichFollowupQuestion(question) {
  const trimmed = question.trim();
  if (!trimmed) return trimmed;
  const context = state.chatContext;
  const shortFollowup = /^(继续|再|那|并且|同时|顺便)/.test(trimmed);
  let enriched = trimmed;
  if (shortFollowup && context.companyName && !enriched.includes(context.companyName)) {
    enriched = `基于${context.companyName}${context.reportYear ? `${context.reportYear}年` : ""}，${enriched}`;
  }
  if (context.compareCompanies.length >= 2 && /继续对比|再对比|差异|谁更|哪个更/.test(enriched) && !context.compareCompanies.some((name) => enriched.includes(name))) {
    enriched = `对比${context.compareCompanies.join("、")}，${enriched}`;
  }
  if (context.macro && /环境|影响|结合|那/.test(enriched) && !enriched.includes("宏观")) {
    enriched = `${enriched}，并结合宏观卫生数据`;
  }
  return enriched;
}

function buildFollowups(result) {
  const prompts = [];
  const company = state.chatContext.companyName || "该公司";
  if ((state.chatContext.compareCompanies || []).length >= 2) {
    prompts.push(`继续对比${state.chatContext.compareCompanies.join("、")}的经营差异`);
  }
  if ((result.macro_rows || []).length || state.chatContext.macro) {
    prompts.push(`把这些宏观变化和${company}的经营表现结合起来分析`);
  }
  if ((result.sql_rows || []).length) {
    prompts.push(`把${company}的关键财务指标按趋势重新总结一遍`);
  }
  if ((result.chunks || []).length) {
    prompts.push(`从年报原文里继续追问${company}的主要风险点`);
  }
  prompts.push(`请生成一份关于${company}的可追溯摘要`);
  return [...new Set(prompts)].slice(0, 4);
}

function renderFollowups(prompts = []) {
  const host = $("chatFollowups");
  if (!host) return;
  if (!prompts.length) {
    host.innerHTML = "";
    return;
  }
  host.innerHTML = prompts.map((prompt) => `<button class="followup-button" type="button" data-followup="${escapeAttr(prompt)}">${escapeHtml(prompt)}</button>`).join("");
  host.querySelectorAll("[data-followup]").forEach((button) => {
    button.addEventListener("click", async () => {
      $("chatInput").value = button.dataset.followup || "";
      await handleChatSubmit($("chatInput").value);
    });
  });
}

function renderMetricGrid(cards) {
  if (!cards.length) return "";
  return `<div class="metric-grid">${cards.map((card) => `<div class="metric-card"><div class="label">${escapeHtml(card.label)}</div><div class="value">${escapeHtml(card.value)}</div></div>`).join("")}</div>`;
}

function renderSourceList(sources = []) {
  if (!sources.length) return "";
  return `<div class="source-list">${sources.map((source, index) => `
    <details class="source-item">
      <summary><span class="source-index">${index + 1}</span><span>${escapeHtml(source.label || "未知来源")}</span><span style="margin-left:auto;color:#64748b;font-size:0.82rem;">点击展开</span></summary>
      <div class="source-snippet">${escapeHtml(source.snippet || "暂无原文片段")}</div>
    </details>`).join("")}</div>`;
}

function renderSqlBlock(sql, title) {
  return sql ? `<div class="detail-block"><strong>${title}</strong><pre>${escapeHtml(sql)}</pre></div>` : "";
}

function renderTable(rows, title) {
  if (!rows || !rows.length) return "";
  const columns = Object.keys(rows[0]);
  const header = columns.map((col) => `<th>${escapeHtml(col)}</th>`).join("");
  const body = rows.slice(0, 10).map((row) => `<tr>${columns.map((col) => `<td title="${escapeHtml(String(row[col] ?? ""))}">${escapeHtml(String(row[col] ?? ""))}</td>`).join("")}</tr>`).join("");
  return `<div class="table-box"><strong>${title}</strong><div style="overflow:auto;"><table><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div></div>`;
}

function renderChart(chartSpec) {
  if (!chartSpec || !chartSpec.rows || !chartSpec.rows.length) return "";
  return `
    <div class="chart-box">
      <strong>图表洞察</strong>
      <div class="chart-host" data-echart='${escapeAttr(JSON.stringify({ kind: "chart_spec", payload: chartSpec }))}'></div>
    </div>
  `;
}

function renderVizBlocks(vizBlocks = []) {
  if (!vizBlocks.length) return "";
  const items = vizBlocks.map((block) => {
    return `
      <div class="viz-card">
        <h4>${escapeHtml(block.title || "分析图表")}</h4>
        <div class="viz-chart-host" data-echart='${escapeAttr(JSON.stringify({ kind: "viz_block", payload: block }))}'></div>
      </div>
    `;
  }).join("");
  return `<div class="viz-grid">${items}</div>`;
}

function buildChartOption(chartSpec) {
  const rows = (chartSpec.rows || []).slice(0, 12);
  const xKey = chartSpec.x;
  const yKey = chartSpec.y;
  const seriesKey = chartSpec.series;
  const uniqueX = [...new Set(rows.map((row) => String(row[xKey] ?? "-")))];
  if (seriesKey) {
    const uniqueSeries = [...new Set(rows.map((row) => String(row[seriesKey] ?? "系列")))];
    return {
      color: ["#2563eb", "#0ea5e9", "#14b8a6", "#f59e0b", "#ef4444"],
      tooltip: { trigger: "axis", confine: true },
      legend: { top: 0 },
      grid: { left: 44, right: 18, top: 40, bottom: 36, containLabel: true },
      xAxis: { type: "category", data: uniqueX, axisLabel: { color: "#475569" }, axisLine: { lineStyle: { color: "#cbd5e1" } } },
      yAxis: { type: "value", axisLabel: { color: "#475569" }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
      series: uniqueSeries.map((seriesName) => ({
        name: seriesName,
        type: chartSpec.chart_type === "line" ? "line" : "bar",
        smooth: chartSpec.chart_type === "line",
        data: uniqueX.map((xValue) => {
          const row = rows.find((item) => String(item[xKey] ?? "-") === xValue && String(item[seriesKey] ?? "系列") === seriesName);
          return Number(row?.[yKey]) || 0;
        }),
      })),
    };
  }
  return {
    color: ["#2563eb"],
    tooltip: { trigger: "axis", confine: true },
    grid: { left: 44, right: 18, top: 20, bottom: 36, containLabel: true },
    xAxis: { type: "category", data: uniqueX, axisLabel: { color: "#475569", interval: 0, rotate: uniqueX.some((value) => value.length > 8) ? 20 : 0 }, axisLine: { lineStyle: { color: "#cbd5e1" } } },
    yAxis: { type: "value", axisLabel: { color: "#475569" }, splitLine: { lineStyle: { color: "#e2e8f0" } } },
    series: [{
      type: chartSpec.chart_type === "line" ? "line" : "bar",
      smooth: chartSpec.chart_type === "line",
      barMaxWidth: 42,
      data: rows.map((row) => Number(row[yKey]) || 0),
    }],
  };
}

function initializeCharts(root = document) {
  if (!window.echarts) return;
  root.querySelectorAll("[data-echart]").forEach((node) => {
    if (node.dataset.chartReady === "true") return;
    const raw = node.getAttribute("data-echart");
    if (!raw) return;
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      return;
    }
    const chart = window.echarts.init(node, null, { renderer: "canvas" });
    const option = parsed.kind === "chart_spec" ? buildChartOption(parsed.payload || {}) : (parsed.payload?.option || {});
    chart.setOption(option);
    if (parsed.kind === "viz_block" && parsed.payload?.type === "graph") {
      chart.on("click", (params) => {
        const name = params?.data?.name || params?.name;
        const series = (((parsed.payload || {}).option || {}).series || [])[0] || {};
        const links = series.links || [];
        const related = links.filter((item) => item.source === name || item.target === name).slice(0, 8);
        $("advancedNodeDetail").innerHTML = `
          <div class="node-detail-card">
            <div class="node-detail-title">节点详情</div>
            <div class="summary-card" style="margin-top:0;">
              <div class="label">当前节点</div>
              <div class="value">${escapeHtml(String(name || "未知节点"))}</div>
            </div>
            <div class="kv-grid" style="margin-top:12px;">
              ${related.length ? related.map((item) => `<div class="kv-item"><strong>${escapeHtml(String(item.source))}</strong> → ${escapeHtml(String(item.target))}<div style="margin-top:6px;color:#64748b;">关联值：${escapeHtml(String(item.value ?? "-"))}</div></div>`).join("") : '<div class="kv-item">当前节点暂无更多关系信息。</div>'}
            </div>
          </div>
        `;
        scrollToBottom();
      });
    }
    node.dataset.chartReady = "true";
    window.addEventListener("resize", () => chart.resize(), { passive: true });
  });
}

function persistChatHistory() {
  try {
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(state.history.slice(-30)));
  } catch {}
}

function restoreChatHistory() {
  try {
    const raw = localStorage.getItem(CHAT_HISTORY_KEY);
    state.history = raw ? JSON.parse(raw) : [];
  } catch {
    state.history = [];
  }
  if (!state.history.length) {
    $("chatMessages").innerHTML = '<div class="empty-history">历史对话会保存在当前浏览器中，刷新页面后仍可继续。</div>';
    return false;
  }
  $("chatMessages").innerHTML = "";
  state.history.forEach((item) => {
    const wrapper = document.createElement("div");
    wrapper.className = `message ${item.role}`;
    wrapper.innerHTML = `<div class="message-card">${item.html}</div>`;
    $("chatMessages").appendChild(wrapper);
  });
  initializeCharts($("chatMessages"));
  return true;
}

function clearChatHistory() {
  state.history = [];
  state.lastChatResult = null;
  persistChatHistory();
  $("chatMessages").innerHTML = '<div class="empty-history">聊天记录已清空，你可以重新开始新的分析会话。</div>';
  renderFollowups([]);
}

function scrollToBottom() { window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" }); }

function appendMessage(role, html) {
  const wrapper = document.createElement("div");
  wrapper.className = `message ${role}`;
  wrapper.innerHTML = `<div class="message-card">${html}</div>`;
  $("chatMessages").appendChild(wrapper);
  state.history.push({ role, html });
  persistChatHistory();
  initializeCharts(wrapper);
  scrollToBottom();
  return wrapper;
}

function renderThinkingMessage() {
  const node = $("thinkingTemplate").content.firstElementChild.cloneNode(true);
  $("chatMessages").appendChild(node);
  let index = 0;
  node.querySelector("[data-stage]").textContent = stages[index];
  const timer = window.setInterval(() => {
    index = (index + 1) % stages.length;
    node.querySelector("[data-stage]").textContent = stages[index];
  }, 1200);
  scrollToBottom();
  return { destroy() { window.clearInterval(timer); node.remove(); } };
}

async function requestJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(await response.text() || `请求失败：${response.status}`);
  return response.json();
}

function buildAssistantHtml(result, question) {
  const chips = buildChips(result, question);
  const markdown = result.answer_markdown || result.report_markdown || "";
  const summary = extractSummary(markdown);
  const metrics = extractMetricCards(markdown);
  return `
    <div class="message-role">系统</div>
    ${chips.length ? `<div class="chip-row">${chips.map((chip) => `<span class="chip">${escapeHtml(chip)}</span>`).join("")}</div>` : ""}
    ${summary ? `<div class="summary-card"><div class="label">核心判断</div><div class="value">${escapeHtml(summary)}</div></div>` : ""}
    ${renderMetricGrid(metrics)}
    <div class="markdown">${renderMarkdown(markdown)}</div>
    ${renderChart(result.chart_spec)}
    ${renderVizBlocks(result.viz_blocks)}
    ${renderSourceList(result.sources)}
    ${renderSqlBlock(result.sql, "企业 SQL")}
    ${renderSqlBlock(result.macro_sql, "宏观 SQL")}
    ${renderTable(result.sql_rows, "结构化结果")}
    ${renderTable(result.macro_rows, "宏观结果")}
    ${result.warnings && result.warnings.length ? `<div class="detail-block"><strong>提示</strong><ul>${result.warnings.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}
  `;
}

function renderWhiteboxHtml(result) {
  const chunks = (result.chunks || []).map((chunk, index) => `
    <details class="source-item" open>
      <summary><span class="source-index">${index + 1}</span><span>${escapeHtml(chunk.metadata?.source || "未知来源")} / 第 ${escapeHtml(String(chunk.metadata?.page ?? "?"))} 页</span></summary>
      <div class="source-snippet">${escapeHtml(chunk.text || "")}</div>
    </details>
  `).join("");
  return `
    <div class="report-card" style="padding:18px 20px;">
      <div class="message-role">白盒示例</div>
      <div class="summary-card">
        <div class="label">透明解释</div>
        <div class="value">把答案、SQL、原文切片和 reasoning 分层展开，适合比赛答辩演示可追溯能力。</div>
      </div>
      <div class="markdown">${renderMarkdown(result.answer_markdown || "")}</div>
      <div class="detail-block">
        <div class="detail-title">
          <strong>执行 SQL</strong>
          <span class="detail-tag">结构化证据</span>
        </div>
        <pre>${escapeHtml(result.sql || "")}</pre>
      </div>
      <div class="whitebox-columns">
        <div>
          <div class="detail-block" style="border-top:0;padding-top:0;">
            <div class="detail-title">
              <strong>RAG 原文切片</strong>
              <span class="detail-tag">非结构化证据</span>
            </div>
          </div>
          <div class="source-list">${chunks}</div>
        </div>
        <div>
          <div class="detail-block" style="border-top:0;padding-top:0;">
            <div class="detail-title">
              <strong>推理说明</strong>
              <span class="detail-tag">解释层</span>
            </div>
          </div>
          <div class="summary-card" style="margin-top:10px;"><div class="value">${renderMarkdown(result.reasoning_markdown || "")}</div></div>
        </div>
      </div>
    </div>
  `;
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === tabName));
  document.querySelectorAll(".tab-panel").forEach((panel) => panel.classList.toggle("active", panel.id === `${tabName}Tab`));
}

async function bootstrap() {
  const response = await fetch("/api/bootstrap");
  const data = await response.json();
  state.deepseekEnabled = Boolean(data.deepseek_enabled);
  $("modePill").textContent = state.deepseekEnabled ? "DeepSeek 增强模式" : "本地检索模式";
  $("companySelect").insertAdjacentHTML("beforeend", (data.companies || []).map((name) => `<option value="${escapeHtml(name)}">${escapeHtml(name)}</option>`).join(""));
  $("yearSelect").insertAdjacentHTML("beforeend", (data.years || []).map((year) => `<option value="${year}">${year}</option>`).join(""));
  $("stats").innerHTML = [["企业数", data.stats.companies], ["文档数", data.stats.documents], ["财务事实", data.stats.financial_facts], ["宏观事实", data.stats.macro_facts]].map(([label, value]) => `<div class="stat"><div class="label">${label}</div><div class="value">${value ?? "-"}</div></div>`).join("");
}

async function handleChatSubmit(question) {
  const trimmed = enrichFollowupQuestion(question);
  if (!trimmed) return;
  appendMessage("user", `<div class="message-role">你</div><div class="markdown"><p>${escapeHtml(trimmed)}</p></div>`);
  $("chatInput").value = "";
  const thinking = renderThinkingMessage();
  try {
    const result = await requestJson("/api/chat", {
      question: trimmed,
      company_name: $("companySelect").value || null,
      report_year: $("yearSelect").value ? Number($("yearSelect").value) : null,
      top_k: Number($("topKInput").value),
    });
    thinking.destroy();
    inferChatContext(trimmed, result);
    state.lastChatResult = result;
    appendMessage("assistant", buildAssistantHtml(result, trimmed));
    renderFollowups(buildFollowups(result));
  } catch (error) {
    thinking.destroy();
    appendMessage("assistant", `<div class="message-role">系统</div><div class="markdown"><p>${escapeHtml(error.message)}</p></div>`);
    renderFollowups([]);
  }
}

async function handleWorkflowSubmit() {
  const topic = $("workflowInput").value.trim();
  if (!topic) return;
  $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><div class="thinking-title">正在生成自动化报告</div><div class="thinking-stage">系统正在执行真实 SQL 检索、向量检索并整理最终研报。</div><div class="thinking-bar"><span></span></div></div>`;
  scrollToBottom();
  try {
    const result = await requestJson("/api/workflow", {
      topic,
      company_name: $("companySelect").value || null,
      report_year: $("yearSelect").value ? Number($("yearSelect").value) : null,
      top_k: Number($("topKInput").value),
    });
    state.lastWorkflowMarkdown = result.report_markdown || "";
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;">${buildAssistantHtml(result, topic)}</div>`;
    initializeCharts($("workflowResult"));
    scrollToBottom();
  } catch (error) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

async function handleAdvancedSubmit() {
  const question = $("advancedInput").value.trim();
  const companyName = $("companySelect").value;
  if (!question || !companyName) {
    $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>请先在左侧选择企业，再发起高级分析。</p></div>`;
    return;
  }
  $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><div class="thinking-title">正在生成高级分析</div><div class="thinking-stage">系统正在整理股权图谱、风险雷达和创新指数。</div><div class="thinking-bar"><span></span></div></div>`;
  try {
    const result = await requestJson("/api/advanced", {
      question,
      company_name: companyName,
    });
    $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;">${buildAssistantHtml(result, question)}</div>`;
    initializeCharts($("advancedResult"));
    scrollToBottom();
  } catch (error) {
    $("advancedResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>${escapeHtml(error.message)}</p></div>`;
  }
}

function downloadWorkflowMarkdown() {
  if (!state.lastWorkflowMarkdown) {
    $("workflowResult").innerHTML = `<div class="report-card" style="padding:18px 20px;"><p>请先生成一次自动化报告，再下载 Markdown。</p></div>`;
    return;
  }
  const blob = new Blob([state.lastWorkflowMarkdown], { type: "text/markdown;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = "deep_diagnostic_report.md";
  anchor.click();
  URL.revokeObjectURL(url);
}

async function loadWhitebox() {
  const response = await fetch("/api/whitebox");
  const result = await response.json();
  $("whiteboxResult").innerHTML = renderWhiteboxHtml(result);
}

document.addEventListener("DOMContentLoaded", async () => {
  await bootstrap();
  restoreChatHistory();
  $("topKInput").addEventListener("input", (event) => { $("topKValue").textContent = event.target.value; });
  document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => setActiveTab(tab.dataset.tab)));
  document.querySelectorAll(".quick-question").forEach((button) => button.addEventListener("click", () => {
    setActiveTab("chat");
    $("chatInput").value = button.dataset.question;
    $("chatInput").focus();
  }));
  $("clearHistoryButton").addEventListener("click", clearChatHistory);
  $("chatForm").addEventListener("submit", async (event) => { event.preventDefault(); await handleChatSubmit($("chatInput").value); });
  $("chatInput").addEventListener("keydown", async (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      await handleChatSubmit($("chatInput").value);
    }
  });
  $("workflowButton").addEventListener("click", handleWorkflowSubmit);
  $("workflowDownloadButton").addEventListener("click", downloadWorkflowMarkdown);
  $("advancedButton").addEventListener("click", handleAdvancedSubmit);
  if (!state.history.length) {
    appendMessage("assistant", `<div class="message-role">系统</div><div class="summary-card"><div class="label">欢迎使用</div><div class="value">现在已经切到自建网页版本。你可以直接提企业诊断、双公司对比或宏观联动问题。</div></div>`);
  }
  await loadWhitebox();
  initializeCharts(document);
  renderFollowups([]);
});
