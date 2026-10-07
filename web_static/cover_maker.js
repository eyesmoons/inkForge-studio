/**
 * cover_maker.js — 封面制作前端逻辑
 */

// ── 风格预设数据 ──────────────────────────────────────────
const STYLES = {
  minimal:  { name: "极简商务", emoji: "◼️" },
  tech:     { name: "科技感",   emoji: "🚀" },
  warm:     { name: "温暖人文", emoji: "☕" },
  nature:   { name: "自然风景", emoji: "🏔️" },
  abstract: { name: "抽象艺术", emoji: "🎨" },
  news:     { name: "新闻资讯", emoji: "📰" },
  food:     { name: "美食生活", emoji: "🍽️" },
  city:     { name: "城市建筑", emoji: "🏙️" },
};

// ── 状态 ──────────────────────────────────────────────────
let currentStyle = "minimal";
let currentSize = "wide";
let lastResult = null;
let isGenerating = false;

// ── 初始化 ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  renderStyleGrid();
  loadHistory();
});

// ── 渲染风格网格 ──────────────────────────────────────────
function renderStyleGrid() {
  const grid = document.getElementById("style-grid");
  grid.innerHTML = "";

  Object.entries(STYLES).forEach(([key, val]) => {
    const card = document.createElement("div");
    card.className = `style-card${key === currentStyle ? " active" : ""}`;
    card.dataset.style = key;
    card.onclick = () => selectStyle(key);
    card.innerHTML = `
      <span class="style-emoji">${val.emoji}</span>
      <span class="style-name">${val.name}</span>
    `;
    grid.appendChild(card);
  });
}

function selectStyle(style) {
  currentStyle = style;
  document.querySelectorAll(".style-card").forEach((el) => {
    el.classList.toggle("active", el.dataset.style === style);
  });
}

function selectSize(btn) {
  currentSize = btn.dataset.size;
  document.querySelectorAll(".size-btn").forEach((el) => {
    el.classList.toggle("active", el.dataset.size === currentSize);
  });
}

// ── 生成封面 ──────────────────────────────────────────────────
async function generateCover() {
  if (isGenerating) return;

  const title = document.getElementById("cover-title").value.trim();
  const content = document.getElementById("cover-content").value.trim();
  const customPrompt = document.getElementById("cover-custom-prompt").value.trim();

  if (!title && !customPrompt) {
    showToast("请输入文章标题或自定义描述", "error");
    document.getElementById("cover-title").focus();
    return;
  }

  isGenerating = true;
  const btn = document.getElementById("generate-btn");
  btn.disabled = true;
  btn.textContent = "⏳ 生成中...";

  // 显示加载
  showPreviewState("loading");

  try {
    const resp = await fetch("/api/cover_maker/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        content,
        style: currentStyle,
        size: currentSize,
        custom_prompt: customPrompt,
      }),
    });

    const data = await resp.json();

    if (data.ok) {
      lastResult = data;
      showPreviewState("result");
      document.getElementById("preview-image").src = data.image_url + "?t=" + Date.now();

      // 显示 prompt
      if (data.revised_prompt || data.prompt) {
        const promptInfo = document.getElementById("prompt-info");
        promptInfo.style.display = "block";
        document.getElementById("prompt-content").textContent =
          data.revised_prompt || data.prompt;
      }

      showToast("封面生成成功！", "success");
      // 刷新历史
      loadHistory();
    } else {
      showPreviewState("empty");
      showToast(data.error || "生成失败，请重试", "error");
    }
  } catch (e) {
    showPreviewState("empty");
    showToast("网络错误，请检查连接", "error");
  } finally {
    isGenerating = false;
    btn.disabled = false;
    btn.textContent = "🎨 生成封面";
  }
}

function regenerateCover() {
  generateCover();
}

// ── 预览状态切换 ──────────────────────────────────────────
function showPreviewState(state) {
  const states = ["empty", "loading", "result"];
  states.forEach((s) => {
    const el = document.getElementById(`preview-${s}`);
    if (el) el.style.display = s === state ? "" : "none";
  });
}

// ── Prompt 展开/收起 ──────────────────────────────────────────
function togglePrompt() {
  const content = document.getElementById("prompt-content");
  const arrow = document.getElementById("prompt-arrow");
  content.classList.toggle("show");
  arrow.classList.toggle("open");
}

// ── 收藏到素材库 ──────────────────────────────────────────────
async function collectToLibrary() {
  if (!lastResult) return;

  const title = document.getElementById("cover-title").value.trim();
  const style = currentStyle;

  try {
    const resp = await fetch("/api/material_library", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title || "未命名封面",
        tags: style ? STYLES[style]?.name || style : "",
        source_type: "cover",
        source_id: lastResult.id || null,
        filename: lastResult.filename,
        image_url: lastResult.image_url,
        prompt: lastResult.revised_prompt || lastResult.prompt || "",
      }),
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("已收藏到素材库", "success");
    } else {
      showToast(data.error || "收藏失败", "error");
    }
  } catch (e) {
    showToast("收藏失败，请检查网络", "error");
  }
}

// ── 下载封面 ──────────────────────────────────────────────────
function downloadCover() {
  if (!lastResult) return;

  const link = document.createElement("a");
  link.href = lastResult.image_url;
  link.download = lastResult.filename || "cover.png";
  link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ── 历史记录 ──────────────────────────────────────────────────
async function loadHistory() {
  try {
    const resp = await fetch("/api/cover_maker/history");
    const data = await resp.json();

    const grid = document.getElementById("history-grid");
    const empty = document.getElementById("history-empty");

    if (!data.ok || !data.data || data.data.length === 0) {
      grid.innerHTML = "";
      empty.style.display = "";
      return;
    }

    empty.style.display = "none";
    grid.innerHTML = data.data
      .map(
        (item) => `
      <div class="history-card">
        <img class="history-card-img" src="${item.image_url}?t=${Date.now()}" alt="${item.title || "封面"}" loading="lazy">
        ${item.is_collected ? '<span class="history-card-collected">已收藏</span>' : ''}
        <div class="history-card-info">
          <div class="history-card-title">${escapeHtml(item.title || "无标题")}</div>
          <div class="history-card-meta">
            <span>${item.style_name || item.style || ""}</span>
            <span>${item.created_at || ""}</span>
          </div>
          <div class="history-card-actions">
            <button class="btn btn-sm" onclick="downloadHistoryCover('${item.image_url}', '${item.filename}')">⬇️ 下载</button>
            ${item.is_collected
              ? '<button class="btn btn-sm" disabled style="opacity:0.5;">✅ 已收藏</button>'
              : `<button class="btn btn-sm btn-accent" onclick="collectHistoryToLibrary(${item.id}, '${escapeHtml(item.title || "")}', '${item.style || ""}', '${item.filename}', '${item.image_url}')">📁 收藏</button>`
            }
            <button class="btn btn-sm" onclick="deleteHistoryCover('${item.filename}')">🗑️ 删除</button>
          </div>
        </div>
      </div>
    `
      )
      .join("");
  } catch (e) {
    console.error("加载历史失败:", e);
  }
}

function downloadHistoryCover(url, filename) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "cover.png";
  link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

async function deleteHistoryCover(filename) {
  if (!confirm("确定删除这张封面？")) return;

  try {
    const resp = await fetch("/api/cover_maker/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename }),
    });
    const data = await resp.json();
    if (data.ok) {
      showToast("已删除", "success");
      loadHistory();
    } else {
      showToast(data.error || "删除失败", "error");
    }
  } catch (e) {
    showToast("删除失败", "error");
  }
}

// ── 从历史记录收藏到素材库 ──────────────────────────────────
async function collectHistoryToLibrary(sourceId, title, style, filename, imageUrl) {
  try {
    const resp = await fetch("/api/material_library", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title: title || "未命名封面",
        tags: style ? STYLES[style]?.name || style : "",
        source_type: "cover",
        source_id: sourceId || null,
        filename: filename,
        image_url: imageUrl,
      }),
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("已收藏到素材库", "success");
      loadHistory(); // 刷新历史列表，更新"已收藏"状态
    } else {
      showToast(data.error || "收藏失败", "error");
    }
  } catch (e) {
    showToast("收藏失败，请检查网络", "error");
  }
}

// ── 工具函数 ──────────────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function showToast(msg, type = "info") {
  // 复用 common.js 的 toast，如果没有则用简单 alert
  if (window.showToastGlobal) {
    window.showToastGlobal(msg, type);
    return;
  }
  // 简单 toast
  const toast = document.createElement("div");
  toast.style.cssText = `
    position: fixed; top: 20px; right: 20px; z-index: 9999;
    padding: 12px 20px; border-radius: 8px; font-size: 14px;
    color: #fff; max-width: 400px;
    background: ${type === "error" ? "#e74c3c" : type === "success" ? "#07c160" : "#333"};
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    animation: fadeIn 0.3s;
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
