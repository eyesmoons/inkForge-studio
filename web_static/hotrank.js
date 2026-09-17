/**
 * hotrank.js — 每日热搜前端逻辑
 */

const PLATFORMS = [
  { id: 'weibo',        name: '微博',     icon: '🔥' },
  { id: 'baidu',        name: '百度',     icon: '🔍' },
  { id: 'toutiao',      name: '今日头条', icon: '📰' },
  { id: 'bilibili',     name: '哔哩哔哩', icon: '📺' },
  { id: 'zhihu',        name: '知乎',     icon: '💡' },
  { id: 'douyin',       name: '抖音',     icon: '🎵' },
  { id: 'tencent_news', name: '腾讯新闻', icon: '📡' },
  { id: 'netease_news', name: '网易新闻', icon: '📣' },
  { id: 'pengpai',      name: '澎湃新闻', icon: '🌊' },
  { id: '36kr',         name: '36氪',     icon: '💼' },
  { id: 'juejin',       name: '稀土掘金', icon: '⛏️' },
  { id: 'ithome',       name: 'IT之家',   icon: '💻' },
  { id: 'sspai',        name: '少数派',   icon: '✨' },
  { id: 'douban',       name: '豆瓣',     icon: '📚' },
];

// 当前激活的 Tab，null = 全部展示
let activeTab = null;
// 缓存数据
const cache = {};

// ── 初始化 ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  renderTabs();
  renderGrid();
  loadAll();
});

// ── Tab 渲染 ──────────────────────────────────────────────
function renderTabs() {
  const container = document.getElementById('platform-tabs');
  if (!container) return;

  let html = `<button class="hr-tab active" data-id="all" onclick="switchTab('all', this)">
    <span>📊</span> 全部
  </button>`;

  for (const p of PLATFORMS) {
    html += `<button class="hr-tab" data-id="${p.id}" onclick="switchTab('${p.id}', this)">
      <span>${p.icon}</span> ${p.name}
    </button>`;
  }
  container.innerHTML = html;
}

function switchTab(id, el) {
  // 更新激活状态
  document.querySelectorAll('.hr-tab').forEach(t => t.classList.remove('active'));
  el.classList.add('active');
  activeTab = id === 'all' ? null : id;
  applyTabFilter();
}

function applyTabFilter() {
  const cards = document.querySelectorAll('.hr-card');
  cards.forEach(card => {
    const pid = card.dataset.platform;
    card.style.display = (!activeTab || pid === activeTab) ? '' : 'none';
  });
}

// ── 卡片渲染 ──────────────────────────────────────────────
function renderGrid() {
  const grid = document.getElementById('hotrank-grid');
  if (!grid) return;
  let html = '';
  for (const p of PLATFORMS) {
    html += `
      <div class="hr-card" data-platform="${p.id}" id="card-${p.id}">
        <div class="hr-card-header">
          <span class="hr-card-icon">${p.icon}</span>
          <span class="hr-card-name">${p.name}</span>
          <span class="hr-card-status" id="status-${p.id}">加载中...</span>
          <button class="hr-refresh-btn" title="刷新" onclick="refreshOne('${p.id}')">↻</button>
        </div>
        <div class="hr-card-body" id="body-${p.id}">
          <div class="hr-loading">
            <div class="hr-loading-dots"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>`;
  }
  grid.innerHTML = html;
}

function renderItems(platformId, items) {
  const body = document.getElementById(`body-${platformId}`);
  const status = document.getElementById(`status-${platformId}`);
  if (!body) return;

  if (!items || items.length === 0) {
    body.innerHTML = `<div class="hr-empty">暂无数据</div>`;
    if (status) { status.textContent = '无数据'; status.className = 'hr-card-status error'; }
    return;
  }

  if (status) { status.textContent = `${items.length} 条`; status.className = 'hr-card-status ok'; }

  const medalClass = ['gold', 'silver', 'bronze'];
  let html = '<ol class="hr-list">';
  for (const item of items) {
    const rank = item.rank || 0;
    const medal = rank <= 3 ? `<span class="hr-medal ${medalClass[rank-1]}">${rank}</span>` : `<span class="hr-rank">${rank}</span>`;
    const hotBadge = item.hot ? `<span class="hr-hot">${escHtml(String(item.hot))}</span>` : '';
    const link = item.url ? `href="${escHtml(item.url)}" target="_blank"` : '';
    html += `<li class="hr-item">
      ${medal}
      <a class="hr-title" ${link}>${escHtml(item.title)}</a>
      ${hotBadge}
    </li>`;
  }
  html += '</ol>';
  body.innerHTML = html;
}

function renderError(platformId, msg) {
  const body = document.getElementById(`body-${platformId}`);
  const status = document.getElementById(`status-${platformId}`);
  if (body) body.innerHTML = `<div class="hr-empty error">⚠️ ${escHtml(msg || '抓取失败')}</div>`;
  if (status) { status.textContent = '失败'; status.className = 'hr-card-status error'; }
}

function renderLoading(platformId) {
  const body = document.getElementById(`body-${platformId}`);
  const status = document.getElementById(`status-${platformId}`);
  if (body) body.innerHTML = `<div class="hr-loading"><div class="hr-loading-dots"><span></span><span></span><span></span></div></div>`;
  if (status) { status.textContent = '加载中...'; status.className = 'hr-card-status'; }
}

// ── 数据加载 ──────────────────────────────────────────────
async function loadPlatform(id) {
  renderLoading(id);
  try {
    const resp = await fetch(`/api/hotrank/${id}`);
    const data = await resp.json();
    if (data.ok) {
      cache[id] = data;
      renderItems(id, data.items);
    } else {
      renderError(id, data.error || '抓取失败');
    }
  } catch (e) {
    renderError(id, '网络错误');
  }
}

async function loadAll() {
  const btn = document.getElementById('refresh-all-btn');
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 加载中...'; }

  // 并发加载所有平台（分批，每批 4 个，避免并发太高）
  const batchSize = 4;
  for (let i = 0; i < PLATFORMS.length; i += batchSize) {
    const batch = PLATFORMS.slice(i, i + batchSize).map(p => loadPlatform(p.id));
    await Promise.allSettled(batch);
  }

  const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const el = document.getElementById('last-updated');
  if (el) el.textContent = `最近更新：${now}`;

  if (btn) { btn.disabled = false; btn.textContent = '🔄 全部刷新'; }
}

async function refreshOne(id) {
  await loadPlatform(id);
  const now = new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  const el = document.getElementById('last-updated');
  if (el) el.textContent = `最近更新：${now}`;
}

async function refreshAll() {
  await loadAll();
}

// ── 工具函数 ──────────────────────────────────────────────
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
