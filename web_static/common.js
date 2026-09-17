
// ═══════════════════════════════════════════════════
// 状态
// ═══════════════════════════════════════════════════
const state = {
  selectedTopic: null,
  currentArticlePath: null,
  currentArticleFilename: null,
  previewDebounceTimer: null,
  domains: [],  // 领域分类列表
  _currentModalMd: null,  // 模态框中的 Markdown 内容
  _currentArticleServerPath: null,  // 文章在服务器上的实际路径
};

// 用户菜单管理
let currentUser = null;

function toggleUserMenu() {
  const dropdown = document.getElementById('user-dropdown');
  dropdown.classList.toggle('show');
}

// 点击其他地方关闭下拉菜单
document.addEventListener('click', (e) => {
  const menu = document.getElementById('user-menu');
  const dropdown = document.getElementById('user-dropdown');
  if (menu && !menu.contains(e.target)) {
    dropdown.classList.remove('show');
  }
});

// 「协同创作」导航项：直接进入全新创作（创建新项目并跳转工作台），不带历史
document.addEventListener('click', (e) => {
  const nav = e.target.closest('a.nav-item[href="/collaborative"]');
  if (nav) {
    e.preventDefault();
    createCollaborativeProject();
  }
});

// 创建一个新的协同创作项目并进入其工作台
async function createCollaborativeProject() {
  try {
    const res = await fetch('/api/collaborative/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title: '未命名创作' })
    });
    const data = await res.json();
    if (data && data.id) {
      window.location.href = '/collaborative/' + data.id;
    } else if (data && data.error) {
      toast(data.error, 'error');
    } else {
      toast('创建失败，请重试', 'error');
    }
  } catch (e) {
    console.error('创建项目失败:', e);
    toast('创建失败，请重试', 'error');
  }
}

async function loadCurrentUser() {
  try {
    const res = await fetch('/api/user/current');
    const data = await res.json();
    if (data.success) {
      currentUser = data.user;
      updateUserInfo();
    } else if (data.error && (data.error.includes('未登录') || data.error.includes('请先登录'))) {
      // 未登录时跳转到登录页
      window.location.href = '/login.html';
    }
  } catch(e) {
    console.error('加载用户信息失败:', e);
  }
}

function updateUserInfo() {
  if (!currentUser) return;
  const avatar = document.getElementById('user-avatar');
  const name = document.getElementById('user-name');
  if (avatar) avatar.textContent = (currentUser.username || 'U').charAt(0).toUpperCase();
  if (name) name.textContent = currentUser.username || '用户';
}

function showUserProfile() {
  if (!currentUser) {
    toast('用户信息加载失败', 'error');
    return;
  }
  const modal = document.createElement('div');
  modal.className = 'modal-overlay show';
  modal.id = 'profile-modal';
  modal.innerHTML = `
    <div class="modal" style="max-width:400px;">
      <div class="modal-header">
        <div class="modal-title">👤 个人中心</div>
        <button class="modal-close" onclick="document.getElementById('profile-modal').remove()">✕</button>
      </div>
      <div style="padding:20px 0;">
        <div style="text-align:center;margin-bottom:20px;">
          <div class="user-avatar" style="width:60px;height:60px;font-size:24px;margin:0 auto 12px;">
            ${(currentUser.username || 'U').charAt(0).toUpperCase()}
          </div>
          <div style="font-size:18px;font-weight:600;color:var(--text);">${currentUser.username || '用户'}</div>
          <div style="font-size:13px;color:var(--text2);margin-top:4px;">${currentUser.email || '未设置邮箱'}</div>
        </div>
        <div class="card" style="margin-bottom:0;">
          <div style="font-size:12px;color:var(--text2);margin-bottom:8px;">账号信息</div>
          <div style="font-size:13px;color:var(--text);">
            <div style="margin-bottom:8px;">
              <span style="color:var(--text2);">用户 ID：</span>${currentUser.id}
            </div>
            <div style="margin-bottom:8px;">
              <span style="color:var(--text2);">角色：</span>${currentUser.role === 'admin' ? '管理员' : '普通用户'}
            </div>
            <div style="margin-bottom:8px;">
              <span style="color:var(--text2);">注册时间：</span>${formatLocalTime(currentUser.created_at)}
            </div>
          </div>
        </div>
      </div>
      <div style="display:flex;justify-content:flex-end;margin-top:20px;">
        <button class="btn btn-secondary" onclick="document.getElementById('profile-modal').remove()">关闭</button>
      </div>
    </div>
  `;
  document.body.appendChild(modal);
}

// 退出登录（确认弹窗）
function logout() {
  if (confirm('确定要退出登录吗？')) {
    doLogout();
  }
}

// 执行退出登录
async function doLogout() {
  try {
    const res = await fetch('/api/auth/logout', { method: 'POST' });
    const data = await res.json();
    if (data.success) {
      toast('已退出登录', 'success');
      // 清除本地存储的 session_id
      localStorage.removeItem('session_id');
      // 立即跳转到登录页
      window.location.href = data.redirect || '/login.html';
    } else {
      toast(data.error || '退出失败', 'error');
    }
  } catch(e) {
    toast('退出失败：' + e.message, 'error');
  }
}

// ═══════════════════════════════════════════════════
// 个人中心
// ═══════════════════════════════════════════════════
function loadProfile() {
  const container = document.getElementById('profile-info');
  if (!currentUser) {
    container.innerHTML = `
      <div style="text-align:center;padding:40px 0;">
        <div style="font-size:36px;margin-bottom:16px;">❌</div>
        <div style="color:var(--text2);">用户信息加载失败</div>
      </div>`;
    return;
  }

  container.innerHTML = `
    <div style="display:flex;align-items:center;gap:20px;padding:20px;">
      <div class="user-avatar" style="width:80px;height:80px;font-size:32px;flex-shrink:0;">
        ${(currentUser.username || 'U').charAt(0).toUpperCase()}
      </div>
      <div style="flex:1;">
        <div style="font-size:20px;font-weight:600;margin-bottom:8px;">${currentUser.username || '用户'}</div>
        <div style="color:var(--text2);font-size:14px;margin-bottom:4px;">
          <span style="display:inline-block;width:70px;">用户 ID：</span>${currentUser.id}
        </div>
        <div style="color:var(--text2);font-size:14px;margin-bottom:4px;">
          <span style="display:inline-block;width:70px;">邮箱：</span>${currentUser.email || '未设置'}
        </div>
        <div style="color:var(--text2);font-size:14px;margin-bottom:4px;">
          <span style="display:inline-block;width:70px;">角色：</span>
          <span style="${currentUser.role === 'admin' ? 'color:var(--accent);' : ''}">${currentUser.role === 'admin' ? '管理员' : '普通用户'}</span>
        </div>
        <div style="color:var(--text2);font-size:14px;margin-bottom:4px;">
          <span style="display:inline-block;width:70px;">注册时间：</span>${formatLocalTime(currentUser.created_at)}
        </div>
      </div>
    </div>
  `;
}

async function changePassword() {
  const oldPwd = document.getElementById('old-password').value;
  const newPwd = document.getElementById('new-password').value;
  const confirmPwd = document.getElementById('confirm-password').value;

  if (!oldPwd || !newPwd || !confirmPwd) {
    return toast('请填写完整密码信息', 'error');
  }

  if (newPwd.length < 6) {
    return toast('新密码至少需要 6 位', 'error');
  }

  if (newPwd !== confirmPwd) {
    return toast('两次输入的新密码不一致', 'error');
  }

  const btn = document.querySelector('[onclick="changePassword()"]');
  btn.disabled = true;
  btn.textContent = '⏳ 修改中...';

  try {
    const res = await fetch('/api/user/change_password', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ old_password: oldPwd, new_password: newPwd }),
    });
    const data = await res.json();

    if (data.success || data.ok) {
      toast('密码修改成功！请重新登录', 'success');
      // 清空表单
      document.getElementById('old-password').value = '';
      document.getElementById('new-password').value = '';
      document.getElementById('confirm-password').value = '';
      // 退出登录
      setTimeout(() => {
        window.location.href = '/login.html';
      }, 1500);
    } else {
      toast(data.error || '密码修改失败', 'error');
    }
  } catch(e) {
    toast('修改失败：' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '🔑 修改密码';
  }
}

// ═══════════════════════════════════════════════════
// 工具
// ═══════════════════════════════════════════════════
function uuid() {
  return 'task_' + Math.random().toString(36).slice(2, 10);
}

// ========== 账号管理 ==========
let accounts = {};
let currentAccountId = '';

async function loadAccounts() {
  try {
    const res = await fetch('/api/accounts');
    const data = await res.json();
    // accounts 从对象改为数组，需要转换格式以便兼容
    const accountArray = data.accounts || [];
    accounts = {};
    accountArray.forEach(acc => {
      accounts[acc.account_id] = {
        id: acc.id,
        account_id: acc.account_id,
        name: acc.name,
        app_id: acc.app_id,
        app_secret: acc.app_secret,
        author: acc.author,
        topic_prompt: acc.topic_prompt,
        article_style: acc.article_style,
        word_count: acc.word_count,
        theme: acc.theme,
        writing_prompt: acc.writing_prompt,
        ending_text: acc.ending_text || '感谢阅读，我们下期见。',
        domain: acc.domain || '科技',
        is_default: acc.is_default,
      };
    });
    currentAccountId = data.default_account_id || '';

    // 填充顶部账号选择器
    const selector = document.getElementById('account-selector');
    if (selector) {
      selector.innerHTML = '<option value="">-- 选择账号 --</option>';
      Object.entries(accounts).forEach(([id, acc]) => {
        const opt = document.createElement('option');
        opt.value = id;
        opt.textContent = acc.name || id;
        if (id === currentAccountId) opt.selected = true;
        selector.appendChild(opt);
      });
    }

    // 如果有默认账号且页面选择器当前为空，自动选中
    if (currentAccountId && selector && selector.value === '') {
      selector.value = currentAccountId;
    }
  } catch(e) {
    console.error('加载账号失败:', e);
    toast('加载账号失败，请刷新页面重试', 'error');
  }
}

async function onAccountChange() {
  const select = document.getElementById('account-selector');
  if (!select) return;
  currentAccountId = select.value || '';
  const acc = accounts[currentAccountId];
  const name = acc?.name || '未选择';

  // 自动设为默认账号（跨页面保持选择）
  if (acc?.id) {
    try {
      await fetch(`/api/accounts/${acc.id}/set_default`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      toast(`已切换并设为默认：${name}`, 'success');
    } catch(e) {
      toast(`已切换到：${name}`, 'info');
    }
  } else {
    toast(`已切换到账号：${name}`, 'info');
  }

  // 同步写稿页的写作偏好（风格、字数、主题）
  if (acc) {
    const styleEl = document.getElementById('write-style');
    if (styleEl && acc.article_style) styleEl.value = acc.article_style;
    const wordsEl = document.getElementById('write-words');
    if (wordsEl && acc.word_count) wordsEl.value = acc.word_count;
    const themeEl = document.getElementById('write-theme');
    if (themeEl && acc.theme) themeEl.value = acc.theme;
  }

  // 重新加载配置以更新写作偏好
  if (document.getElementById('page-config') && document.getElementById('page-config').classList.contains('active')) {
    loadConfig();
  }
  // 刷新历史文章列表（应用筛选）
  // 兼容 SPA（page-history 元素）和多页面（history.html 路径判断）
  const isHistoryPage = document.getElementById('page-history')
    ? document.getElementById('page-history').classList.contains('active')
    : window.location.pathname.includes('history.html');
  if (isHistoryPage) {
    loadHistory();
  }
}

function toast(msg, type='info') {
  const el = document.getElementById('toast');
  if (!el) return;  // 避免页面没有 toast 元素时报错
  el.textContent = msg;
  el.className = `toast show ${type}`;
  setTimeout(() => { el.className = 'toast'; }, 3000);
}

function setStatus(text, dotClass='dot-green') {
  document.getElementById('status-text').textContent = text;
  const dot = document.getElementById('status-dot');
  dot.className = 'dot ' + dotClass;
}

function switchPage(name, navEl) {
  const page = document.getElementById('page-' + name);
  if (!page) {
    console.error('页面不存在: page-' + name);
    return;
  }
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  page.classList.add('active');
  if (navEl) navEl.classList.add('active');
  const titles = {
    dashboard: '🏠 工作台',
    topics: '🔍 自动选题',
    write: '✍️ 一键写稿',
    history: '📂 历史文章',
    config: '⚙️ 系统配置',
    profile: '👤 个人中心',
  };
  document.getElementById('topbar-title').textContent = titles[name] || name;
  if (name === 'config') {
    loadConfig();
    loadDomains();
    loadAIModels();
  }
  if (name === 'history') loadHistory();
  if (name === 'profile') loadProfile();
}

function appendLog(logEl, msg, level='info') {
  if (!logEl) return;
  const isEmpty = logEl.querySelector('.log-empty');
  if (isEmpty) isEmpty.remove();
  const line = document.createElement('div');
  const cls = {error:'log-error', warn:'log-warn', ping:'log-ping', result:'log-info', done:'log-step', info:'log-info'}[level] || 'log-info';
  line.className = cls;
  // 过滤掉ping
  if (level === 'ping') return;
  line.textContent = msg.startsWith('{') ? '' : msg;  // result 行不显示原始JSON
  if (msg && !msg.startsWith('{')) logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

// SSE 订阅
function subscribeSSE(taskId, logEl, onResult, onDone) {
  const es = new EventSource(`/api/logs/${taskId}`);
  es.onmessage = (e) => {
    let data;
    try { data = JSON.parse(e.data); } catch { return; }
    if (data.level === 'ping') return;
    if (data.level === 'done') {
      es.close();
      if (onDone) onDone();
      return;
    }
    if (data.level === 'result') {
      try {
        const result = JSON.parse(data.msg);
        if (onResult) onResult(result);
      } catch {}
      return;
    }
    appendLog(logEl, data.msg, data.level);
  };
  es.onerror = () => { es.close(); };
  return es;
}

// 全局 SSE 初始化
function startSSE() {
  // 实时的 SSE 订阅在各个操作函数中通过 subscribeSSE() 创建
  // 这里只做初始化准备，可以在这里添加全局日志监听逻辑
  const logBox = document.getElementById('sse-log-box');
  if (logBox && logBox.children.length === 0) {
    appendLog(logBox, '等待操作...', 'info');
  }
}

// 清空 SSE 日志
function clearSSELog() {
  const logBox = document.getElementById('sse-log-box');
  if (logBox) {
    logBox.innerHTML = '<div class="log-entry log-info">等待操作...</div>';
  }
}

function openModal(id) {
  document.getElementById(id).classList.add('show');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('show');
}

// ═══════════════════════════════════════════════════
// 工作台
// ═══════════════════════════════════════════════════
// 数字动态增长动画
function animateNumber(element, targetValue, duration = 1000) {
  if (!element) return;
  const startValue = parseInt(element.textContent) || 0;
  const target = parseInt(targetValue) || 0;
  if (startValue === target) return;

  // 添加变化动画类
  element.classList.add('changing');

  const startTime = performance.now();
  const easeOutQuart = (t) => 1 - Math.pow(1 - t, 4);

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const eased = easeOutQuart(progress);
    const current = Math.round(startValue + (target - startValue) * eased);
    element.textContent = current;

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      element.textContent = target;
      // 动画结束后移除类
      setTimeout(() => element.classList.remove('changing'), 300);
    }
  }
  requestAnimationFrame(update);
}

async function loadDashStats() {
  try {
    const res  = await fetch('/api/stats');
    const data = await res.json();

    // 更新统计卡片（带数字增长动画）
    animateNumber(document.getElementById('stat-total-articles'), data.total_articles ?? 0, 800);
    animateNumber(document.getElementById('stat-draft-articles'), data.draft_articles ?? 0, 800);
    animateNumber(document.getElementById('stat-published-articles'), data.published_articles ?? 0, 800);
    animateNumber(document.getElementById('stat-today-articles'), data.today_articles ?? 0, 800);

    // 绘制近7天文章趋势图（含每账号明细）
    drawWeeklyChart(data.weekly_data || [], data.weekly_account_data || []);

    // 绘制账号分布图
    drawAccountChart(data.account_stats || []);

    // 绘制近7天标题关键词 Top10（横条图）
    drawKeywordChart(data.keyword_top10 || []);

    // 绘制文章状态漏斗图
    drawStatusFunnel(data.status_funnel || []);

    // 绘制各账号7天发文量对比（横条图）
    drawAccount7dChart(data.account_7d_stats || []);

    // ── 新增图表 ──
    drawStatusPieChart(data.status_distribution || []);
    drawHeatmapChart(data.hourly_data || []);
    drawMonthlyChart(data.monthly_data || []);
    drawAccountRankChart(data.account_rank || []);
    drawKeywordCloud(data.keyword_cloud || []);

  } catch (e) {
    console.error('加载统计数据失败:', e);
  }
}

// 堆叠柱状图颜色板（最多支持 10 个账号）
const WEEKLY_CHART_COLORS = [
  ['#4CAF50', '#81C784'],
  ['#2196F3', '#64B5F6'],
  ['#FF9800', '#FFB74D'],
  ['#9C27B0', '#CE93D8'],
  ['#F44336', '#EF9A9A'],
  ['#00BCD4', '#80DEEA'],
  ['#FF5722', '#FFAB91'],
  ['#607D8B', '#B0BEC5'],
  ['#795548', '#BCAAA4'],
  ['#E91E63', '#F48FB1'],
];

// 绘制近7天文章趋势图（堆叠柱状图，Canvas）
function drawWeeklyChart(weeklyData, weeklyAccountData) {
  const container = document.getElementById('weekly-chart');
  if (!container) return;

  container.innerHTML = '';

  // ── 提取所有账号并分配颜色 ──
  const accountMap = {}; // account_id -> { name, colorIdx }
  (weeklyAccountData || []).forEach(d => {
    if (!(d.account_id in accountMap)) {
      const idx = Object.keys(accountMap).length % WEEKLY_CHART_COLORS.length;
      accountMap[d.account_id] = { name: d.account_name || d.account_id || '未知', colorIdx: idx };
    }
  });
  const accountIds = Object.keys(accountMap);
  const hasMultiAccount = accountIds.length > 1;

  // ── 生成近7天日期 ──
  const dates = [];
  const today = new Date();
  for (let i = 6; i >= 0; i--) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    dates.push(d.toISOString().split('T')[0]);
  }

  // ── 每天总数（用于 fallback） ──
  const totalByDate = {};
  (weeklyData || []).forEach(d => { totalByDate[d.date] = d.count; });

  // ── 每天每账号数 ──
  // dayAccountCounts[date][account_id] = count
  const dayAccountCounts = {};
  dates.forEach(d => { dayAccountCounts[d] = {}; });
  (weeklyAccountData || []).forEach(d => {
    if (dayAccountCounts[d.date] !== undefined) {
      dayAccountCounts[d.date][d.account_id] = d.count;
    }
  });

  // ── 计算每天总数（优先用 weeklyAccountData 加总，保持一致）──
  const counts = dates.map(date => {
    if (accountIds.length > 0) {
      return Object.values(dayAccountCounts[date]).reduce((s, v) => s + v, 0);
    }
    return totalByDate[date] || 0;
  });

  // ── Canvas 尺寸 ──
  // 有多账号时底部留图例区域
  const legendH = hasMultiAccount ? Math.ceil(accountIds.length / 3) * 24 + 16 : 0;
  const canvas = document.createElement('canvas');
  const dpr = window.devicePixelRatio || 1;
  const cssW = container.offsetWidth || 600;
  const cssH = container.offsetHeight || 220;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const width = cssW;
  const height = cssH;
  const padding = { top: 36, right: 20, bottom: 40 + legendH, left: 46 };
  const chartWidth = width - padding.left - padding.right;
  const chartHeight = height - padding.top - padding.bottom;

  const maxCount = Math.max(...counts, 5);
  const gridLines = 4;

  // ── 辅助：绘制网格 ──
  function drawGrid() {
    ctx.strokeStyle = 'rgba(255,255,255,0.12)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= gridLines; i++) {
      const y = padding.top + (chartHeight / gridLines) * i;
      ctx.beginPath();
      ctx.moveTo(padding.left, y);
      ctx.lineTo(width - padding.right, y);
      ctx.stroke();
      const value = Math.round(maxCount * (1 - i / gridLines));
      ctx.fillStyle = 'rgba(255,255,255,0.6)';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(value, padding.left - 6, y + 4);
    }
  }

  // ── 辅助：绘制所有柱子 ──
  // bars[i] = { x, totalY, width, date, count, segments:[{y,h,accountId}] }
  const barWidth = chartWidth / 7 * 0.58;
  const barSpacing = chartWidth / 7;
  const bars = [];

  function buildBars() {
    bars.length = 0;
    dates.forEach((date, index) => {
      const x = padding.left + barSpacing * index + (barSpacing - barWidth) / 2;
      const total = counts[index];
      const totalBarH = (total / maxCount) * chartHeight;
      const totalY = padding.top + chartHeight - totalBarH;

      const segments = [];
      let curY = padding.top + chartHeight; // 从底部往上堆叠

      if (hasMultiAccount) {
        accountIds.forEach(aid => {
          const cnt = dayAccountCounts[date][aid] || 0;
          const segH = (cnt / maxCount) * chartHeight;
          if (segH > 0) {
            segments.push({ y: curY - segH, h: segH, accountId: aid, count: cnt });
            curY -= segH;
          }
        });
      } else {
        // 单账号或无账号数据：单色柱
        segments.push({ y: totalY, h: totalBarH, accountId: null, count: total });
      }

      bars.push({ x, totalY, width: barWidth, date, count: total, segments });
    });
  }

  function drawBars(hoveredIdx, progress) {
    if (progress === undefined) progress = 1;
    const ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
    bars.forEach((bar, bi) => {
      const isHovered = bi === hoveredIdx;

      bar.segments.forEach(seg => {
        if (seg.h <= 0) return;
        const aid = seg.accountId;
        const [c1, c2] = aid !== null
          ? WEEKLY_CHART_COLORS[accountMap[aid].colorIdx]
          : ['#4CAF50', '#81C784'];

        ctx.globalAlpha = (hoveredIdx !== null && !isHovered) ? 0.45 : 1.0;

        // 逐柱延迟入场
        const delay = bi * 0.07;
        const barEase = 1 - Math.pow(1 - Math.max(0, Math.min((ease - delay) / (1 - delay), 1)), 3);
        const animH = seg.h * barEase;
        const animY = seg.y + (seg.h - animH);

        const grad = ctx.createLinearGradient(bar.x, animY, bar.x, animY + animH);
        grad.addColorStop(0, isHovered ? lightenColor(c1, 20) : c1);
        grad.addColorStop(1, isHovered ? lightenColor(c2, 20) : c2);
        ctx.fillStyle = grad;

        // 顶层 segment 加圆角
        const isTop = seg === bar.segments[bar.segments.length - 1];
        if (isTop && animH > 4) {
          const r = Math.min(4, animH / 2, bar.width / 2);
          ctx.beginPath();
          ctx.moveTo(bar.x + r, animY);
          ctx.lineTo(bar.x + bar.width - r, animY);
          ctx.quadraticCurveTo(bar.x + bar.width, animY, bar.x + bar.width, animY + r);
          ctx.lineTo(bar.x + bar.width, animY + animH);
          ctx.lineTo(bar.x, animY + animH);
          ctx.lineTo(bar.x, animY + r);
          ctx.quadraticCurveTo(bar.x, animY, bar.x + r, animY);
          ctx.closePath();
          ctx.fill();
        } else if (animH > 0) {
          ctx.fillRect(bar.x, animY, bar.width, animH);
        }

        // 高亮时加光晕
        if (isHovered) {
          ctx.shadowColor = c1 + '88';
          ctx.shadowBlur = 14;
          ctx.fillRect(bar.x, animY, bar.width, animH);
          ctx.shadowColor = 'transparent';
          ctx.shadowBlur = 0;
        }

        ctx.globalAlpha = 1.0;

        // 分段数量标签（段高足够时）
        if (hasMultiAccount && animH >= 16 && seg.count > 0 && barEase > 0.8) {
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.font = '10px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(seg.count, bar.x + bar.width / 2, animY + animH / 2 + 4);
        }
      });

      // 顶部总数标签
      if (bar.count > 0 && ease > 0.8) {
        const delay = bi * 0.07;
        const barEase = 1 - Math.pow(1 - Math.max(0, Math.min((ease - delay) / (1 - delay), 1)), 3);
        if (barEase > 0.8) {
          const topSeg = bar.segments[bar.segments.length - 1];
          const animY = topSeg.y + (topSeg.h - topSeg.h * barEase);
          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.font = 'bold 12px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(bar.count, bar.x + bar.width / 2, animY - 6);
        }
      }

      // X轴日期
      ctx.fillStyle = 'rgba(255,255,255,0.6)';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(bar.date.slice(5), bar.x + bar.width / 2, height - padding.bottom + 16);
    });
  }

  // ── 辅助：绘制图例 ──
  function drawLegend() {
    if (!hasMultiAccount) return;
    const startY = height - legendH + 8;
    const colW = Math.floor(width / 3);
    accountIds.forEach((aid, i) => {
      const col = i % 3;
      const row = Math.floor(i / 3);
      const lx = padding.left + col * colW;
      const ly = startY + row * 22;
      const [c1] = WEEKLY_CHART_COLORS[accountMap[aid].colorIdx];
      ctx.fillStyle = c1;
      ctx.fillRect(lx, ly + 2, 12, 12);
      ctx.fillStyle = 'rgba(255,255,255,0.7)';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'left';
      const name = accountMap[aid].name;
      ctx.fillText(name.length > 8 ? name.slice(0, 7) + '…' : name, lx + 16, ly + 12);
    });
  }

  // ── 辅助：颜色加亮 ──
  function lightenColor(hex, amount) {
    const num = parseInt(hex.replace('#', ''), 16);
    const r = Math.min(255, (num >> 16) + amount);
    const g = Math.min(255, ((num >> 8) & 0xff) + amount);
    const b = Math.min(255, (num & 0xff) + amount);
    return '#' + [r, g, b].map(v => v.toString(16).padStart(2, '0')).join('');
  }

  // ── 初始绘制（带入场动画） ──
  buildBars();

  let animProgress = 0;
  const animStart = performance.now();

  function drawFrame(timestamp) {
    animProgress = Math.min((timestamp - animStart) / 900, 1);
    redraw(null, animProgress);
    if (animProgress < 1) requestAnimationFrame(drawFrame);
  }
  requestAnimationFrame(drawFrame);

  function redraw(hoveredIdx, progress) {
    ctx.clearRect(0, 0, width, height);
    drawGrid();
    drawBars(hoveredIdx, progress || animProgress);
    drawLegend();
  }

  // ── 无数据提示 ──
  if (counts.every(c => c === 0)) {
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', width / 2, height / 2);
  }

  // ── 鼠标交互 ──
  let tooltip = null;

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    let hoveredIdx = null;
    bars.forEach((bar, bi) => {
      // 判断鼠标是否在整根柱子范围内（从顶部到底部）
      const barTop = Math.min(...bar.segments.map(s => s.y), bar.totalY);
      const barBottom = padding.top + chartHeight;
      if (mouseX >= bar.x && mouseX <= bar.x + bar.width &&
          mouseY >= barTop && mouseY <= barBottom && bar.count > 0) {
        hoveredIdx = bi;
      }
    });

    if (tooltip) { tooltip.remove(); tooltip = null; }

    if (hoveredIdx !== null) {
      canvas.style.cursor = 'pointer';
      const bar = bars[hoveredIdx];

      // 构造 tooltip 内容
      let innerHtml = `<div style="font-weight:700;margin-bottom:6px;border-bottom:1px solid rgba(255,255,255,0.2);padding-bottom:4px;">${bar.date}</div>`;
      if (hasMultiAccount) {
        bar.segments.slice().reverse().forEach(seg => {
          if (seg.count <= 0) return;
          const aid = seg.accountId;
          const [c1] = WEEKLY_CHART_COLORS[accountMap[aid].colorIdx];
          const name = accountMap[aid].name;
          innerHtml += `<div style="display:flex;align-items:center;gap:6px;margin-top:3px;">
            <span style="display:inline-block;width:10px;height:10px;border-radius:2px;background:${c1};flex-shrink:0;"></span>
            <span style="flex:1;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${name}</span>
            <span style="font-weight:600;color:${c1};">${seg.count}</span>
          </div>`;
        });
        innerHtml += `<div style="margin-top:5px;padding-top:4px;border-top:1px solid rgba(255,255,255,0.2);font-weight:700;">合计：${bar.count}</div>`;
      } else {
        innerHtml += `<div>文章数：<span style="color:#4CAF50;font-weight:700;">${bar.count}</span></div>`;
      }

      tooltip = document.createElement('div');
      tooltip.style.cssText = `
        position: fixed;
        background: rgba(30, 30, 30, 0.92);
        color: white;
        padding: 10px 14px;
        border-radius: 8px;
        font-size: 12px;
        pointer-events: none;
        z-index: 9999;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        min-width: 140px;
        transform: translate(-50%, -100%);
      `;
      tooltip.innerHTML = innerHtml;
      document.body.appendChild(tooltip);

      // 定位：柱顶正中央上方 10px
      let tx = rect.left + bar.x + bar.width / 2;
      let ty = rect.top + bar.totalY - 10;
      if (ty - tooltip.offsetHeight < 4) {
        tooltip.style.transform = 'translate(-50%, 0)';
        ty = rect.top + bar.totalY + (bar.segments[bar.segments.length - 1]?.h || 0) + 10;
      }
      // 左右防溢出
      const tw = tooltip.offsetWidth;
      if (tx - tw / 2 < 4) tx = tw / 2 + 4;
      if (tx + tw / 2 > window.innerWidth - 4) tx = window.innerWidth - tw / 2 - 4;
      tooltip.style.left = tx + 'px';
      tooltip.style.top = ty + 'px';

      redraw(hoveredIdx);
    } else {
      canvas.style.cursor = 'default';
      redraw(null);
    }
  });

  canvas.addEventListener('mouseleave', () => {
    if (tooltip) { tooltip.remove(); tooltip = null; }
    canvas.style.cursor = 'default';
    redraw(null);
  });
}

// 绘制账号分布图（饼图）


// 绘制账号分布图（饼图）
function drawAccountChart(accountStats) {
  const container = document.getElementById('account-chart');
  if (!container) return;

  container.innerHTML = '';

  const canvas = document.createElement('canvas');
  const dpr = window.devicePixelRatio || 1;
  const cssW = container.offsetWidth;
  const cssH = container.offsetHeight;
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  container.appendChild(canvas);

  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  const width = cssW;
  const height = cssH;
  const centerX = width / 2;
  const centerY = height / 2;
  const radius = Math.min(width, height) / 3;

  // 清空画布
  ctx.clearRect(0, 0, width, height);

  // 如果没有数据
  if (!accountStats || accountStats.length === 0) {
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', width / 2, height / 2);
    return;
  }

  // 计算总数
  const totalCount = accountStats.reduce((sum, item) => sum + item.count, 0);

  // 颜色数组
  const colors = ['#4CAF50', '#2196F3', '#FFC107', '#FF5722', '#9C27B0', '#00BCD4', '#E91E63'];

  // 存储扇形信息用于鼠标交互
  const slices = [];

  // 绘制饼图
  let startAngle = -Math.PI / 2;
  accountStats.forEach((item, index) => {
    const sliceAngle = (item.count / totalCount) * 2 * Math.PI;
    const endAngle = startAngle + sliceAngle;
    const color = colors[index % colors.length];

    // 存储扇形信息
    slices.push({
      startAngle: startAngle,
      endAngle: endAngle,
      color: color,
      count: item.count,
      accountName: item.account_name || '未命名',
      percent: ((item.count / totalCount) * 100).toFixed(1)
    });

    // 扇形
    ctx.beginPath();
    ctx.moveTo(centerX, centerY);
    ctx.arc(centerX, centerY, radius, startAngle, endAngle);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
    ctx.strokeStyle = '#fff';
    ctx.lineWidth = 2;
    ctx.stroke();

    // 标签（只有占比大于5%才显示）
    if (item.count / totalCount > 0.05) {
      const midAngle = startAngle + sliceAngle / 2;
      const labelRadius = radius * 1.4;
      const labelX = centerX + Math.cos(midAngle) * labelRadius;
      const labelY = centerY + Math.sin(midAngle) * labelRadius;

      // 百分比
      const percent = ((item.count / totalCount) * 100).toFixed(1);
      ctx.fillStyle = 'rgba(255,255,255,0.9)';
      ctx.font = '12px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(`${percent}%`, labelX, labelY);

      // 账号名称
      ctx.fillStyle = 'rgba(255,255,255,0.6)';
      ctx.font = '11px sans-serif';
      const name = item.account_name || '未命名';
      const displayName = name.length > 6 ? name.slice(0, 6) + '...' : name;
      ctx.fillText(displayName, labelX, labelY + 14);
    }

    startAngle = endAngle;
  });

  // 鼠标悬停交互
  let tooltip = null;
  let hoveredSliceIndex = -1;

  canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const mouseX = e.clientX - rect.left;
    const mouseY = e.clientY - rect.top;

    // 计算鼠标到圆心的距离和角度
    const dx = mouseX - centerX;
    const dy = mouseY - centerY;
    const distance = Math.sqrt(dx * dx + dy * dy);
    let angle = Math.atan2(dy, dx);

    // 规范化角度到 [0, 2π]
    if (angle < 0) {
      angle += 2 * Math.PI;
    }

    // 检查鼠标是否在某个扇形上
    let newHoveredIndex = -1;
    if (distance <= radius) {
      for (let i = 0; i < slices.length; i++) {
        const slice = slices[i];
        let start = slice.startAngle;
        let end = slice.endAngle;

        // 规范化起始和结束角度
        if (start < 0) start += 2 * Math.PI;
        if (end < 0) end += 2 * Math.PI;

        // 处理跨越 0° 的情况
        if (start > end) {
          if (angle >= start || angle < end) {
            newHoveredIndex = i;
            break;
          }
        } else {
          if (angle >= start && angle < end) {
            newHoveredIndex = i;
            break;
          }
        }
      }
    }

    // 如果悬停状态改变
    if (newHoveredIndex !== hoveredSliceIndex) {
      hoveredSliceIndex = newHoveredIndex;

      // 重绘饼图
      ctx.clearRect(0, 0, width, height);

      slices.forEach((slice, index) => {
        const isHovered = index === hoveredSliceIndex;

        if (isHovered) {
          // 高亮当前扇形：稍微放大
          const hoverRadius = radius * 1.05;
          ctx.beginPath();
          ctx.moveTo(centerX, centerY);
          ctx.arc(centerX, centerY, hoverRadius, slice.startAngle, slice.endAngle);
          ctx.closePath();
          ctx.fillStyle = slice.color;
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.stroke();

          // 添加阴影
          ctx.shadowColor = 'rgba(0, 0, 0, 0.3)';
          ctx.shadowBlur = 10;
          ctx.shadowOffsetX = 0;
          ctx.shadowOffsetY = 0;
          ctx.fill();
          ctx.shadowColor = 'transparent';

          // 高亮标签
          const midAngle = slice.startAngle + (slice.endAngle - slice.startAngle) / 2;
          const labelRadius = radius * 1.4;
          const labelX = centerX + Math.cos(midAngle) * labelRadius;
          const labelY = centerY + Math.sin(midAngle) * labelRadius;

          ctx.fillStyle = 'rgba(255,255,255,0.9)';
          ctx.font = 'bold 12px sans-serif';
          ctx.textAlign = 'center';
          ctx.fillText(`${slice.percent}%`, labelX, labelY);

          ctx.fillStyle = 'rgba(255,255,255,0.7)';
          ctx.font = 'bold 11px sans-serif';
          const displayName = slice.accountName.length > 6 ? slice.accountName.slice(0, 6) + '...' : slice.accountName;
          ctx.fillText(displayName, labelX, labelY + 14);
        } else {
          // 其他扇形稍微变暗
          ctx.globalAlpha = 0.7;
          ctx.beginPath();
          ctx.moveTo(centerX, centerY);
          ctx.arc(centerX, centerY, radius, slice.startAngle, slice.endAngle);
          ctx.closePath();
          ctx.fillStyle = slice.color;
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.stroke();
          ctx.globalAlpha = 1.0;

          // 标签
          const midAngle = slice.startAngle + (slice.endAngle - slice.startAngle) / 2;
          const labelRadius = radius * 1.4;
          const labelX = centerX + Math.cos(midAngle) * labelRadius;
          const labelY = centerY + Math.sin(midAngle) * labelRadius;

          if (slice.count / totalCount > 0.05) {
            ctx.fillStyle = '#666';
            ctx.font = '12px sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText(`${slice.percent}%`, labelX, labelY);

            ctx.fillStyle = '#999';
            ctx.font = '11px sans-serif';
            const displayName = slice.accountName.length > 6 ? slice.accountName.slice(0, 6) + '...' : slice.accountName;
            ctx.fillText(displayName, labelX, labelY + 14);
          }
        }
      });
    }

    // 更新 tooltip
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }

    if (hoveredSliceIndex >= 0) {
      canvas.style.cursor = 'pointer';
      const slice = slices[hoveredSliceIndex];

      tooltip = document.createElement('div');
      tooltip.style.cssText = `
        position: fixed;
        background: rgba(0, 0, 0, 0.85);
        color: white;
        padding: 8px 12px;
        border-radius: 6px;
        font-size: 13px;
        pointer-events: none;
        z-index: 9999;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2);
        white-space: nowrap;
      `;
      tooltip.innerHTML = `<div style="font-weight:600;margin-bottom:4px;">${slice.accountName}</div>
                         <div>文章数: <span style="color:${slice.color};font-weight:600;">${slice.count}</span></div>
                         <div>占比: <span style="color:${slice.color};font-weight:600;">${slice.percent}%</span></div>`;
      document.body.appendChild(tooltip);

      const rect = canvas.getBoundingClientRect();
      // tooltip 显示在鼠标右下方，接近鼠标
      let tx = rect.left + mouseX + 12;
      let ty = rect.top + mouseY + 12;
      // 右边超出屏幕时显示在鼠标左侧
      if (tx + tooltip.offsetWidth > window.innerWidth - 8) {
        tx = rect.left + mouseX - tooltip.offsetWidth - 12;
      }
      // 下边超出屏幕时显示在鼠标上方
      if (ty + tooltip.offsetHeight > window.innerHeight - 8) {
        ty = rect.top + mouseY - tooltip.offsetHeight - 12;
      }
      tooltip.style.left = tx + 'px';
      tooltip.style.top = ty + 'px';
    } else {
      canvas.style.cursor = 'default';
    }
  });

  canvas.addEventListener('mouseleave', () => {
    // 恢复原始状态
    hoveredSliceIndex = -1;
    if (tooltip) {
      tooltip.remove();
      tooltip = null;
    }
    canvas.style.cursor = 'default';

    ctx.clearRect(0, 0, width, height);

    // 重绘饼图
    let startAngle = -Math.PI / 2;
    accountStats.forEach((item, index) => {
      const sliceAngle = (item.count / totalCount) * 2 * Math.PI;
      const endAngle = startAngle + sliceAngle;
      const color = colors[index % colors.length];

      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, radius, startAngle, endAngle);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.lineWidth = 2;
      ctx.stroke();

      if (item.count / totalCount > 0.05) {
        const midAngle = startAngle + sliceAngle / 2;
        const labelRadius = radius * 1.4;
        const labelX = centerX + Math.cos(midAngle) * labelRadius;
        const labelY = centerY + Math.sin(midAngle) * labelRadius;

        const percent = ((item.count / totalCount) * 100).toFixed(1);
        ctx.fillStyle = '#333';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${percent}%`, labelX, labelY);

        ctx.fillStyle = '#666';
        ctx.font = '11px sans-serif';
        const name = item.account_name || '未命名';
        const displayName = name.length > 6 ? name.slice(0, 6) + '...' : name;
        ctx.fillText(displayName, labelX, labelY + 14);
      }

      startAngle = endAngle;
    });
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 近7天标题关键词 Top10（水平横条图）
// ─────────────────────────────────────────────────────────────────────────────
function drawKeywordChart(keywordData) {
  const container = document.getElementById('keyword-chart');
  if (!container) return;
  container.innerHTML = '';

  if (!keywordData || keywordData.length === 0) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:13px;">近7天暂无文章数据</div>';
    return;
  }

  // 取最多 10 条，按数量降序排列
  const items = [...keywordData].sort((a, b) => b.count - a.count).slice(0, 10);
  const maxCount = items[0].count;

  // 用 DOM 渲染（比 Canvas 更清晰，且支持 dark mode）
  const wrap = document.createElement('div');
  wrap.style.cssText = 'padding:4px 8px;display:flex;flex-direction:column;gap:6px;height:100%;overflow:auto;box-sizing:border-box;';

  // 科技感蓝绿渐变色阶
  const baseColors = ['#4CAF50','#66BB6A','#2196F3','#42A5F5','#00BCD4','#26C6DA','#FF9800','#FFA726','#78909C','#90A4AE'];

  items.forEach((item, i) => {
    const pct = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
    const color = baseColors[Math.min(i, baseColors.length - 1)];

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px;flex-shrink:0;';

    // 关键词标签
    const label = document.createElement('div');
    label.textContent = item.word;
    label.style.cssText = 'width:64px;font-size:12px;color:var(--text);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0;';

    // 进度条容器（带科技感边框）
    const barWrap = document.createElement('div');
    barWrap.style.cssText = 'flex:1;background:rgba(46,50,72,0.6);border-radius:6px;height:18px;overflow:hidden;position:relative;border:1px solid rgba(255,255,255,0.04);';

    const bar = document.createElement('div');
    bar.style.cssText = `width:0;height:100%;background:linear-gradient(90deg,${color}88,${color});border-radius:5px;transition:width 0.6s cubic-bezier(0.22,0.61,0.36,1);position:relative;`;

    // 光泽层
    const shine = document.createElement('div');
    shine.style.cssText = 'position:absolute;top:0;left:0;right:0;height:50%;background:linear-gradient(180deg,rgba(255,255,255,0.12),transparent);border-radius:5px 5px 0 0;pointer-events:none;';
    bar.appendChild(shine);

    barWrap.appendChild(bar);

    // 数值
    const val = document.createElement('div');
    val.textContent = item.count;
    val.style.cssText = 'width:24px;font-size:12px;font-weight:600;color:var(--text2);text-align:right;flex-shrink:0;';

    row.appendChild(label);
    row.appendChild(barWrap);
    row.appendChild(val);
    wrap.appendChild(row);

    // hover 交互
    row.style.cursor = 'default';
    row.style.transition = 'background 0.2s';
    row.addEventListener('mouseenter', () => {
      row.style.background = 'rgba(7,193,96,0.04)';
      label.style.color = color;
      label.style.fontWeight = '600';
      bar.style.boxShadow = `0 0 12px ${color}44`;
      val.style.color = color;
    });
    row.addEventListener('mouseleave', () => {
      row.style.background = 'transparent';
      label.style.color = 'var(--text)';
      label.style.fontWeight = 'normal';
      bar.style.boxShadow = 'none';
      val.style.color = 'var(--text2)';
    });
  });

  container.appendChild(wrap);

  // 入场动画：延迟展开条形
  requestAnimationFrame(() => {
    const bars = wrap.querySelectorAll('div > div > div');
    const barEls = wrap.querySelectorAll(':scope > div > div:nth-child(2) > div:first-child');
    let idx = 0;
    function expandNext() {
      if (idx >= items.length) return;
      const pct = maxCount > 0 ? (items[idx].count / maxCount) * 100 : 0;
      const barEl = wrap.children[idx].querySelector('div:nth-child(2) > div');
      if (barEl) barEl.style.width = pct + '%';
      idx++;
      setTimeout(expandNext, 50);
    }
    expandNext();
  });
}

// ─────────────────────────────────────────────────────────────────────────────
// 文章状态漏斗图
// ─────────────────────────────────────────────────────────────────────────────
function drawStatusFunnel(funnelData) {
  const container = document.getElementById('status-funnel');
  if (!container) return;
  container.innerHTML = '';

  if (!funnelData || funnelData.length === 0) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:13px;">暂无数据</div>';
    return;
  }

  const n = funnelData.length;
  const maxCount = funnelData[0].count || 1;
  const colors = ['#2563eb', '#f59e0b', '#10b981', '#8b5cf6', '#ef4444'];

  // SVG 画布尺寸
  const W = 320, H = 240;
  const padX = 8, padTop = 10, padBot = 10;
  const gap = 4; // 梯形间隔
  const labelW = 56; // 左侧标签区宽度
  const valW = 44;   // 右侧数值区宽度
  const funnelX = padX + labelW;
  const funnelW = W - funnelX - valW - padX;
  const totalH = H - padTop - padBot;
  const segH = (totalH - gap * (n - 1)) / n; // 每段高度

  // 最宽宽度 → 最窄宽度（形成漏斗感）
  const maxW = funnelW;
  const minW = funnelW * 0.38;

  const svgEl = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svgEl.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svgEl.setAttribute('width', '100%');
  svgEl.setAttribute('height', '100%');
  svgEl.style.cssText = 'display:block;';

  // 定义渐变和滤镜
  const defs = document.createElementNS('http://www.w3.org/2000/svg', 'defs');
  // 发光滤镜
  const filterEl = document.createElementNS('http://www.w3.org/2000/svg', 'filter');
  filterEl.setAttribute('id', 'funnel-glow');
  filterEl.setAttribute('x', '-20%');
  filterEl.setAttribute('y', '-20%');
  filterEl.setAttribute('width', '140%');
  filterEl.setAttribute('height', '140%');
  const blur = document.createElementNS('http://www.w3.org/2000/svg', 'feGaussianBlur');
  blur.setAttribute('stdDeviation', '4');
  blur.setAttribute('result', 'blur');
  filterEl.appendChild(blur);
  const merge = document.createElementNS('http://www.w3.org/2000/svg', 'feMerge');
  const mn1 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
  mn1.setAttribute('in', 'blur');
  const mn2 = document.createElementNS('http://www.w3.org/2000/svg', 'feMergeNode');
  mn2.setAttribute('in', 'SourceGraphic');
  merge.appendChild(mn1);
  merge.appendChild(mn2);
  filterEl.appendChild(merge);
  defs.appendChild(filterEl);
  svgEl.appendChild(defs);

  funnelData.forEach((item, i) => {
    const ratio = maxCount > 0 ? item.count / maxCount : 0;

    // 按比例计算本段宽度（最小保持 minW 的 40%，保证可见）
    const topRatio = i === 0 ? 1 : (funnelData[i - 1].count / maxCount);
    const botRatio = ratio;

    const topW = maxW * Math.max(topRatio, 0.1);
    const botW = maxW * Math.max(botRatio, 0.1);

    const y = padTop + i * (segH + gap);
    const cx = funnelX + funnelW / 2;

    // 梯形四个顶点（居中对齐）
    const x1 = cx - topW / 2, x2 = cx + topW / 2; // 上边
    const x3 = cx + botW / 2, x4 = cx - botW / 2; // 下边

    const color = colors[i % colors.length];

    // 梯形填充（带渐变）
    const grad = document.createElementNS('http://www.w3.org/2000/svg', 'linearGradient');
    grad.setAttribute('id', `funnel-grad-${i}`);
    grad.setAttribute('x1', '0'); grad.setAttribute('y1', '0');
    grad.setAttribute('x2', '1'); grad.setAttribute('y2', '0');
    const stop1 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop1.setAttribute('offset', '0%');
    stop1.setAttribute('stop-color', color);
    stop1.setAttribute('stop-opacity', '0.6');
    const stop2 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop2.setAttribute('offset', '50%');
    stop2.setAttribute('stop-color', color);
    stop2.setAttribute('stop-opacity', '0.9');
    const stop3 = document.createElementNS('http://www.w3.org/2000/svg', 'stop');
    stop3.setAttribute('offset', '100%');
    stop3.setAttribute('stop-color', color);
    stop3.setAttribute('stop-opacity', '0.6');
    grad.appendChild(stop1);
    grad.appendChild(stop2);
    grad.appendChild(stop3);
    defs.appendChild(grad);

    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    poly.setAttribute('points', `${x1},${y} ${x2},${y} ${x3},${y + segH} ${x4},${y + segH}`);
    poly.setAttribute('fill', `url(#funnel-grad-${i})`);
    poly.setAttribute('opacity', String(0.85 - i * 0.06));
    poly.style.cursor = 'pointer';
    poly.style.transition = 'opacity 0.2s, filter 0.2s';

    // hover 交互
    poly.addEventListener('mouseenter', () => {
      poly.setAttribute('opacity', '1');
      poly.setAttribute('filter', 'url(#funnel-glow)');
    });
    poly.addEventListener('mouseleave', () => {
      poly.setAttribute('opacity', String(0.85 - i * 0.06));
      poly.removeAttribute('filter');
    });

    // 入场动画：从左侧滑入
    const initialPoints = `${x1 - funnelW},${y} ${x1 - funnelW},${y} ${x1 - funnelW},${y + segH} ${x1 - funnelW},${y + segH}`;
    poly.setAttribute('points', initialPoints);
    poly.style.transition = 'opacity 0.2s, filter 0.2s';

    svgEl.appendChild(poly);

    // 梯形内文字（标签 + 数量）
    const midY = y + segH / 2;
    const txt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
    txt.setAttribute('x', cx);
    txt.setAttribute('y', midY + 1);
    txt.setAttribute('text-anchor', 'middle');
    txt.setAttribute('dominant-baseline', 'middle');
    txt.setAttribute('fill', '#fff');
    txt.setAttribute('font-size', '12');
    txt.setAttribute('font-weight', '600');
    txt.setAttribute('opacity', '0');
    txt.textContent = `${item.label}  ${item.count}`;
    txt.style.transition = 'opacity 0.3s';
    svgEl.appendChild(txt);

    // 右侧转化率
    if (i > 0 && funnelData[i - 1].count > 0) {
      const convRate = ((item.count / funnelData[i - 1].count) * 100).toFixed(0);
      const rateX = funnelX + funnelW + valW / 2 + padX / 2;
      const rateTxt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      rateTxt.setAttribute('x', rateX);
      rateTxt.setAttribute('y', midY);
      rateTxt.setAttribute('text-anchor', 'middle');
      rateTxt.setAttribute('dominant-baseline', 'middle');
      rateTxt.setAttribute('fill', color);
      rateTxt.setAttribute('font-size', '11');
      rateTxt.setAttribute('font-weight', '700');
      rateTxt.setAttribute('opacity', '0');
      rateTxt.textContent = `${convRate}%`;
      rateTxt.style.transition = 'opacity 0.3s';
      svgEl.appendChild(rateTxt);

      // 转化率小标注
      const rateLabelTxt = document.createElementNS('http://www.w3.org/2000/svg', 'text');
      rateLabelTxt.setAttribute('x', rateX);
      rateLabelTxt.setAttribute('y', midY + 13);
      rateLabelTxt.setAttribute('text-anchor', 'middle');
      rateLabelTxt.setAttribute('dominant-baseline', 'middle');
      rateLabelTxt.setAttribute('fill', '#999');
      rateLabelTxt.setAttribute('font-size', '9');
      rateLabelTxt.setAttribute('opacity', '0');
      rateLabelTxt.textContent = '转化率';
      rateLabelTxt.style.transition = 'opacity 0.3s';
      svgEl.appendChild(rateLabelTxt);

      // 延迟显示
      setTimeout(() => { rateTxt.setAttribute('opacity', '1'); rateLabelTxt.setAttribute('opacity', '1'); }, 400 + i * 120);
    }

    // 入场动画：梯形展开
    setTimeout(() => {
      poly.setAttribute('points', `${x1},${y} ${x2},${y} ${x3},${y + segH} ${x4},${y + segH}`);
      txt.setAttribute('opacity', '1');
    }, 100 + i * 120);
  });

  container.appendChild(svgEl);
}

// ─────────────────────────────────────────────────────────────────────────────
// 各账号近7天发文量对比（水平横条图）
// ─────────────────────────────────────────────────────────────────────────────
function drawAccount7dChart(accountData) {
  const container = document.getElementById('account-7d-chart');
  if (!container) return;
  container.innerHTML = '';

  if (!accountData || accountData.length === 0) {
    container.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#aaa;font-size:13px;">近7天暂无发文数据</div>';
    return;
  }

  const items = [...accountData].sort((a, b) => b.count - a.count);
  const maxCount = items[0].count;

  const wrap = document.createElement('div');
  wrap.style.cssText = 'padding:4px 8px;display:flex;flex-direction:column;gap:6px;height:100%;overflow:auto;box-sizing:border-box;justify-content:center;';

  // 多账号颜色
  const colors = ['#2563eb','#f59e0b','#10b981','#8b5cf6','#ef4444','#06b6d4','#f97316'];

  items.forEach((item, i) => {
    const pct = maxCount > 0 ? (item.count / maxCount) * 100 : 0;
    const color = colors[i % colors.length];

    const row = document.createElement('div');
    row.style.cssText = 'display:flex;align-items:center;gap:8px;flex-shrink:0;';

    // 账号名
    const label = document.createElement('div');
    const name = item.account_name || '未知';
    label.textContent = name.length > 6 ? name.slice(0, 6) + '…' : name;
    label.title = name;
    label.style.cssText = 'width:64px;font-size:12px;color:var(--text);text-align:right;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;flex-shrink:0;';

    // 进度条
    const barWrap = document.createElement('div');
    barWrap.style.cssText = 'flex:1;background:var(--border);border-radius:4px;height:22px;overflow:hidden;position:relative;';

    const bar = document.createElement('div');
    bar.style.cssText = `width:${pct}%;height:100%;background:${color};border-radius:4px;transition:width 0.4s ease;`;

    barWrap.appendChild(bar);

    // 数值
    const val = document.createElement('div');
    val.textContent = item.count + ' 篇';
    val.style.cssText = 'width:38px;font-size:12px;font-weight:600;color:var(--text2);text-align:right;flex-shrink:0;';

    row.appendChild(label);
    row.appendChild(barWrap);
    row.appendChild(val);
    wrap.appendChild(row);
  });

  container.appendChild(wrap);
}

async function autoRunPipeline(noCache=true) {
  const logEl = document.getElementById('dash-log');
  const progress = document.getElementById('dash-progress');
  logEl.innerHTML = '';
  progress.className = 'progress-fill running';
  setStatus('全自动运行中...', 'dot-yellow');
  const autoBtn = document.getElementById('dash-auto-btn');
  if (autoBtn) autoBtn.disabled = true;

  const taskId = uuid();
  const wordCountEl = document.getElementById('write-words');
  const res = await fetch('/api/auto', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({
      task_id: taskId,
      no_cache: noCache,
      account_id: currentAccountId,
      word_count: wordCountEl ? parseInt(wordCountEl.value) : 2000,
    }),
  });

  subscribeSSE(taskId, logEl, (result) => {
    if (result.preview_path || result.success) {
      // 处理多篇文章的情况
      if (result.articles && Array.isArray(result.articles)) {
        // 多篇文章模式
        const total = result.total_articles || result.articles.length;
        const successful = result.successful_articles || 0;
        const line = document.createElement('div');
        line.className = 'log-step';
        line.textContent = `✅ 完成！成功生成 ${successful}/${total} 篇文章`;
        logEl.appendChild(line);

        // 显示每篇文章的详情
        result.articles.forEach((article, idx) => {
          const articleLine = document.createElement('div');
          articleLine.className = 'log-detail';
          const topic = article.topic || {};
          const title = topic.title || `文章 ${idx + 1}`;
          const score = topic.ai_score ? `(${topic.ai_score.toFixed(1)}分)` : '';
          const success = article.result?.success ? '✅' : '❌';
          articleLine.textContent = `  ${success} ${title} ${score}`;
          logEl.appendChild(articleLine);

          // 如果成功且有保存路径，加载第一篇到编辑器
          if (idx === 0 && article.result?.success && article.result.saved_path) {
            state.currentArticlePath = article.result.saved_path;
          }
        });

        // 加载第一篇文章到编辑器
        const firstArticle = result.articles.find(a => a.result?.success);
        if (firstArticle && firstArticle.result?.saved_path) {
          const writeNav = document.querySelector('[data-page=write]');
          if (writeNav) {
            switchPage('write', writeNav);
          }
          if (firstArticle.result.saved_path.endsWith('.md')) {
            loadArticleToEditorByPath(firstArticle.result.saved_path);
          }
        }
      } else {
        // 单篇文章模式（向后兼容）
        const line = document.createElement('div');
        line.className = 'log-step';
        line.textContent = result.success
          ? `✅ 完成！${result.title || ''}`
          : `⚠️ ${result.msg || '未知结果'}`;
        logEl.appendChild(line);
        if (result.saved_path || result.success) {
          // 保存文章路径
          state.currentArticlePath = result.saved_path || null;
          // 自动跳转到写稿&预览页面
          const writeNav = document.querySelector('[data-page=write]');
          if (writeNav) {
            switchPage('write', writeNav);
          }
          // 加载文章内容到编辑器（如果是 Markdown 文件）
          if (result.saved_path && result.saved_path.endsWith('.md')) {
            loadArticleToEditorByPath(result.saved_path);
          }
        }
      }
    }
  }, () => {
    progress.className = 'progress-fill';
    progress.style.width = '100%';
    setStatus('就绪', 'dot-green');
    document.getElementById('dash-auto-btn').disabled = false;
    toast('全自动流水线完成！', 'success');
    loadDashStats();
  });
}

// 辅助函数：根据路径加载文章到编辑器
async function loadArticleToEditorByPath(filePath) {
  try {
    // 从路径提取文件名
    const filename = filePath.split('/').pop();
    const res = await fetch(`/api/articles/${filename}`);
    const data = await res.json();
    if (data.md_text) {
      document.getElementById('md-editor').value = data.md_text;
      state._currentModalMd = data.md_text;
      state._currentArticleServerPath = data.server_path || filePath;
      // 触发预览
      previewMarkdown();
      syncPublishBtn();
      toast('文章已加载，可在编辑器查看和修改', 'success');
    }
  } catch (e) {
    console.error('加载文章失败:', e);
  }
}

// ═══════════════════════════════════════════════════
// 自动选题
// ═══════════════════════════════════════════════════
async function startTopics(noCache=true) {
  const prompt  = document.getElementById('topic-prompt').value.trim();
  // search_queries 已移除，不再需要读取

  const logCard = document.getElementById('topics-log-card');
  const logEl   = document.getElementById('topics-log');
  const resultEl = document.getElementById('topics-result');
  const topicsBtn = document.querySelector('[onclick="startTopics()"]');
  if (topicsBtn) { topicsBtn.disabled = true; topicsBtn.textContent = '⏳ 获取中...'; }

  logCard.style.display = 'block';
  resultEl.style.display = 'none';
  logEl.innerHTML = '';
  setStatus('正在使用 AI 生成选题...', 'dot-yellow');

  const taskId = uuid();

  // 先发送 POST 请求，等待返回后再订阅 SSE
  try {
    const res = await fetch('/api/topics', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ task_id: taskId, account_id: currentAccountId, topic_prompt: prompt, no_cache: noCache }),
    });
    const data = await res.json();

    if (!data.ok) {
      toast('启动任务失败', 'error');
      document.getElementById('topics-progress').className = 'progress-fill';
      setStatus('就绪', 'dot-green');
      if (topicsBtn) { topicsBtn.disabled = false; topicsBtn.textContent = '🔍 获取选题'; }
      return;
    }

    // POST 请求成功后，再订阅 SSE
    subscribeSSE(taskId, logEl, (result) => {
      if (result.topics) renderTopics(result.topics);
    }, () => {
      document.getElementById('topics-progress').className = 'progress-fill';
      setStatus('就绪', 'dot-green');
      if (topicsBtn) { topicsBtn.disabled = false; topicsBtn.textContent = '🔍 获取选题'; }
    });
  } catch (err) {
    toast('启动任务失败：' + err.message, 'error');
    document.getElementById('topics-progress').className = 'progress-fill';
    setStatus('就绪', 'dot-green');
    if (topicsBtn) { topicsBtn.disabled = false; topicsBtn.textContent = '🔍 获取选题'; }
  }
}

function renderTopics(topics) {
  const listEl  = document.getElementById('topics-list');
  const countEl = document.getElementById('topics-count-badge');
  const resultEl = document.getElementById('topics-result');
  listEl.innerHTML = '';
  countEl.textContent = topics.length + ' 条';
  resultEl.style.display = 'block';
  topics.forEach(t => {
    const div = document.createElement('div');
    div.className = 'topic-item' + (t.is_hot ? ' hot' : '');
    div.dataset.topic = JSON.stringify(t);
    const score = t.ai_score > 0 ? `<span class="tag tag-score">AI ${t.ai_score.toFixed(1)}分</span>` : '';
    const hot   = t.is_hot ? `<span class="tag tag-hot">🔥 热点</span>` : '';
    div.innerHTML = `
      <div class="topic-rank">${t.rank || '·'}</div>
      <div class="topic-body">
        <div class="topic-title">${t.title}</div>
        <div class="topic-summary">${t.summary || ''}</div>
        <div class="topic-meta">${hot}${score}</div>
      </div>`;
    div.onclick = () => selectTopic(div, t);
    listEl.appendChild(div);
  });
}

function selectTopic(el, topic) {
  document.querySelectorAll('.topic-item').forEach(t => t.classList.remove('selected'));
  el.classList.add('selected');
  state.selectedTopic = topic;
  document.getElementById('write-selected-btn').disabled = false;
  document.getElementById('selected-topic-hint').textContent = `已选：${topic.title.slice(0,30)}...`;
}

function writeSelectedTopic() {
  if (!state.selectedTopic) {
    alert('请先选择一个选题');
    return;
  }
  const navEl = document.querySelector('[data-page=write]');
  if (!navEl) {
    console.error('未找到写稿页面导航元素');
    alert('页面加载错误，请刷新后重试');
    return;
  }
  const writePage = document.getElementById('page-write');
  if (!writePage) {
    console.error('未找到写稿页面容器');
    alert('页面加载错误，请刷新后重试');
    return;
  }
  switchPage('write', navEl);
  generateArticle(state.selectedTopic);
}

// ═══════════════════════════════════════════════════
// 写稿 & 生成
// ═══════════════════════════════════════════════════

async function loadWriteSkills() {
  var selectEl = document.getElementById('write-skill');
  if (!selectEl) return;
  try {
    var res = await fetch('/api/skills?active_only=1');
    var data = await res.json();
    if (data.ok && data.skills) {
      // 保留"不使用技能"选项
      selectEl.innerHTML = '<option value="">不使用技能</option>';
      data.skills.forEach(function(s) {
        var opt = document.createElement('option');
        opt.value = s.id;
        opt.textContent = s.name + (s.category ? ' (' + s.category + ')' : '');
        selectEl.appendChild(opt);
      });
    }
  } catch (e) {
    console.error('加载写作技能失败:', e);
  }
}

async function generateArticle(topicOverride=null) {
  // 优先使用自定义选题输入框
  const customTopicEl = document.getElementById('custom-topic');
  const customTopicText = customTopicEl && customTopicEl.value.trim();

  if (customTopicText) {
    // 使用自定义选题
    var topic = {
      title: customTopicText,
      summary: customTopicText,
      detail: customTopicText,
      source_url: '',
      is_hot: false,
    };
  } else {
    // 使用 topicOverride 或 state.selectedTopic 或默认选题
    var topic = topicOverride || state.selectedTopic || {
      title: '手机行业最新动态',
      summary: '请在编辑器中查看并完善内容',
      detail: '',
      source_url: '',
      is_hot: false,
    };
  }

  const logCard = document.getElementById('write-log-card');
  const logEl   = document.getElementById('write-log');
  logCard.style.display = 'block';
  logEl.innerHTML = '';
  document.getElementById('gen-btn').disabled = true;
  setStatus('AI 写稿中...', 'dot-yellow');

  const taskId = uuid();

  // 先发送 POST 请求，等待返回后再订阅 SSE
  try {
    const wordCountEl = document.getElementById('write-words');
    const styleEl = document.getElementById('write-style');
    const skillEl = document.getElementById('write-skill');
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        task_id: taskId,
        topic: topic,
        account_id: currentAccountId,
        style: styleEl ? styleEl.value : '',
        word_count: wordCountEl ? parseInt(wordCountEl.value) : 2000,
        skill_id: skillEl ? skillEl.value : '',
      }),
    });
    const data = await res.json();

    if (!data.ok) {
      toast('启动任务失败', 'error');
      logCard.style.display = 'none';
      const genBtn = document.getElementById('gen-btn');
      if (genBtn) genBtn.disabled = false;
      setStatus('就绪', 'dot-green');
      return;
    }

    // POST 请求成功后，再订阅 SSE
    subscribeSSE(taskId, logEl, (result) => {
      if (result.md_content) {
        document.getElementById('md-editor').value = result.md_content;
        state.currentArticlePath = result.saved_path;
        document.getElementById('publish-btn').disabled = false;
        previewMarkdown();
        toast('文章生成完成！', 'success');
      }
    }, () => {
      logCard.style.display = 'none';
      document.getElementById('gen-btn').disabled = false;
      setStatus('就绪', 'dot-green');
    });
  } catch (err) {
    toast('启动任务失败：' + err.message, 'error');
    logCard.style.display = 'none';
    const genBtn = document.getElementById('gen-btn');
    if (genBtn) genBtn.disabled = false;
    setStatus('就绪', 'dot-green');
  }
}

async function previewMarkdown() {
  const md = document.getElementById('md-editor').value;
  if (!md.trim()) return;
  const theme = document.getElementById('write-theme').value;
  const template = document.getElementById('write-template')?.value || '';

  // 获取当前账号的 ending_text
  const selector = document.getElementById('account-selector');
  const accountId = selector ? selector.value : currentAccountId;
  const endingText = (accountId && accounts[accountId]) ? accounts[accountId].ending_text || '' : '';

  try {
    const res  = await fetch('/api/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ md_text: md, theme, template, ending_text: endingText }),
    });
    const data = await res.json();
    if (data.success || data.ok) {
      const iframe = document.getElementById('preview-iframe');
      iframe.srcdoc = data.html;
    }
  } catch {}
}

function syncPublishBtn() {
  const editor = document.getElementById('md-editor');
  const btn = document.getElementById('publish-btn');
  if (!editor || !btn) return;
  const hasContent = editor.value.trim().length > 0;
  btn.disabled = !hasContent;
}

function debouncedPreview() {
  clearTimeout(state.previewDebounceTimer);
  state.previewDebounceTimer = setTimeout(previewMarkdown, 800);
  syncPublishBtn();
}

function clearEditor() {
  document.getElementById('md-editor').value = '';
  document.getElementById('preview-iframe').srcdoc = '<html><body style="background:#f5f5f5;display:flex;align-items:center;justify-content:center;height:100vh;color:#999;font-family:sans-serif;">预览区域</body></html>';
  state.currentArticlePath = null;
  document.getElementById('publish-btn').disabled = true;
}

function clearCustomTopic() {
  const customTopicEl = document.getElementById('custom-topic');
  if (customTopicEl) {
    customTopicEl.value = '';
    toast('已清空自定义选题', 'success');
  }
}

function clearImportEditor() {
  document.getElementById('import-markdown').value = '';
  document.getElementById('import-preview').innerHTML = '';
  document.getElementById('import-title').value = '';
}

function copyMd() {
  const md = document.getElementById('md-editor').value;
  navigator.clipboard.writeText(md).then(() => toast('已复制 Markdown', 'success'));
}

function openPreviewInTab() {
  const iframe = document.getElementById('preview-iframe');
  const html   = iframe.srcdoc;
  if (!html) return;
  const blob = new Blob([html], {type:'text/html;charset=utf-8'});
  window.open(URL.createObjectURL(blob));
}

function openImportPreviewInTab() {
  const preview = document.getElementById('import-preview');
  const html = preview.innerHTML;
  if (!html || html.trim() === '') {
    toast('请先生成预览内容', 'error');
    return;
  }
  const blob = new Blob([html], {type:'text/html;charset=utf-8'});
  window.open(URL.createObjectURL(blob));
}

async function copyWechatHtml() {
  const iframe = document.getElementById('preview-iframe');
  const html = iframe.srcdoc;
  if (!html) {
    toast('请先生成预览内容', 'error');
    return;
  }

  try {
    // 使用 Clipboard API 复制 HTML 内容
    const clipboardItem = new ClipboardItem({
      'text/html': new Blob([html], {type: 'text/html'}),
      'text/plain': new Blob([html], {type: 'text/plain'})
    });
    await navigator.clipboard.write([clipboardItem]);
    toast('✅ 已复制富文本内容！<br>现在可以直接粘贴到编辑器中', 'success');
  } catch (e) {
    // 如果 ClipboardItem 不支持，降级到纯文本
    try {
      await navigator.clipboard.writeText(html);
      toast('✅ 已复制内容（纯文本模式）<br>粘贴后可能需要重新调整格式', 'success');
    } catch (e2) {
      toast('❌ 复制失败，请手动选择内容复制', 'error');
    }
  }
}

async function publishDraft() {
  const md = document.getElementById('md-editor').value.trim();
  if (!md && !state.currentArticlePath) {
    toast('编辑器内容为空，无法推送', 'error');
    return;
  }

  const theme  = document.getElementById('write-theme').value;
  const template = document.getElementById('write-template')?.value || '';
  const logEl  = document.getElementById('write-log');
  const pubBtn = document.getElementById('publish-btn');
  document.getElementById('write-log-card').style.display = 'block';
  logEl.innerHTML = '';
  if (pubBtn) { pubBtn.disabled = true; pubBtn.textContent = '⏳ 推送中...'; }
  setStatus('推送草稿中...', 'dot-yellow');

  // 验证是否选择了账号
  if (!currentAccountId) {
    toast('请先在右上角选择账号！', 'error');
    if (pubBtn) { pubBtn.disabled = false; pubBtn.textContent = '📤 推送草稿'; }
    setStatus('就绪', 'dot-green');
    return;
  }

  // 显示当前选择的账号
  const accountName = accounts[currentAccountId]?.name || currentAccountId;
  console.log(`[推送草稿] 当前使用账号: ${accountName} (ID: ${currentAccountId})`);

  const taskId = uuid();
  // 始终传 md_text（编辑器实时内容），后端以此为准写临时文件
  // 同时附上 md_path（AI 生成时的真实路径），后端优先用 md_path 但文本不一致时以 md_text 为准
  const body = { task_id: taskId, account_id: currentAccountId, theme, template, md_text: md };
  if (state.currentArticlePath && !state.currentArticlePath.startsWith('/path/to/')) {
    body.md_path = state.currentArticlePath;
  }
  const res = await fetch('/api/publish', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) {
    toast(data.error || '启动推送任务失败', 'error');
    setStatus('就绪', 'dot-green');
    return;
  }

  subscribeSSE(taskId, logEl, (result) => {
    console.log('[推送草稿] 收到结果:', result);
    if (result.success) {
      toast('✅ 草稿已保存到本地！可后续导出发布', 'success');
      // 刷新历史文章列表，更新状态显示
      if (document.getElementById('page-history').classList.contains('active')) {
        loadHistory();
      }
    } else {
      toast(`❌ 推送失败：${result.msg || '未知错误'}`, 'error');
    }
  }, () => {
    setStatus('就绪', 'dot-green');
    if (pubBtn) { pubBtn.disabled = false; pubBtn.textContent = '📤 推送草稿'; }
  });
}

// ═══════════════════════════════════════════════════
// 历史文章
// ═══════════════════════════════════════════════════
// ── 历史文章：无限滚动状态 ──
let _historyState = {
  page: 1,
  loading: false,
  hasMore: true,
  total: 0,
  keyword: '',
  debounceTimer: null
};

async function loadHistory(resetPage) {
  console.log('[loadHistory] 开始加载历史文章...');
  const gridEl = document.getElementById('article-grid');
  if (!gridEl) return;

  if (resetPage !== false) {
    _historyState.page = 1;
    _historyState.hasMore = true;
    _historyState.total = 0;
    gridEl.innerHTML = '';
  }

  const container = document.getElementById('history-scroll-container');
  const loadMoreEl = document.getElementById('history-load-more');
  const endEl = document.getElementById('history-end');
  const statsEl = document.getElementById('history-stats');

  if (!_historyState.hasMore) return;
  if (_historyState.loading) return;
  _historyState.loading = true;

  if (loadMoreEl) loadMoreEl.style.display = 'flex';
  if (endEl) endEl.style.display = 'none';

  // 首次加载显示 loading
  if (_historyState.page === 1 && gridEl.children.length === 0) {
    gridEl.innerHTML = '<div style="color:var(--text2);text-align:center;padding:30px;grid-column:1/-1;">加载中...</div>';
  }

  try {
    const selector = document.getElementById('account-selector');
    const selectedAccountId = selector ? selector.value : '';
    const keyword = _historyState.keyword;

    let url = `/api/articles?page=${_historyState.page}&page_size=12`;
    if (selectedAccountId) url += `&account_id=${selectedAccountId}`;
    if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;

    console.log('[loadHistory] 请求 URL:', url);
    const res = await fetch(url);

    if (!res.ok) {
      const errorText = await res.text();
      throw new Error(`接口请求失败 (${res.status})`);
    }

    const data = await res.json();
    const articles = data.articles || [];
    const pagination = data.pagination || {};

    _historyState.total = pagination.total || 0;
    const totalPages = pagination.total_pages || 0;
    if (_historyState.page >= totalPages) _historyState.hasMore = false;

    // 清除首次 loading 占位
    if (_historyState.page === 1) gridEl.innerHTML = '';

    if (articles.length === 0 && _historyState.page === 1) {
      gridEl.innerHTML = `<div style="color:var(--text2);text-align:center;padding:40px;grid-column:1/-1;">
        ${keyword ? '没有找到匹配的文章' : '暂无历史文章'}
      </div>`;
      _historyState.hasMore = false;
    }

    // 追加文章卡片
    articles.forEach(a => {
      const div = document.createElement('div');
      div.className = 'article-card article-card-enter';
      const displayTitle = a.title || a.filename || '无标题';
      const displaySize = a.size ? `${(a.size/1024).toFixed(1)} KB` : '-';
      const displayTime = a.mtime || '-';
      const displayCreatedAt = a.created_at || '-';
      const accountName = a.account_name || '未分类';

      let statusBadge = '';
      if (a.status === 'published') {
        statusBadge = '<span class="status-badge status-published">✅ 已发布</span>';
      } else if (a.status === 'saved') {
        statusBadge = '<span class="status-badge status-saved">💾 已保存</span>';
      } else if (a.status === 'draft') {
        statusBadge = '<span class="status-badge status-unpublished">📝 本地草稿</span>';
      } else {
        statusBadge = '<span class="status-badge status-unpublished">📝 本地草稿</span>';
      }

      div.innerHTML = `
        <button class="article-card-del" title="删除文章" onclick="deleteArticle(event,'${a.id}')">✕</button>
        <div class="article-card-header">
          <div class="article-card-account">📱 ${accountName}</div>
          ${statusBadge}
        </div>
        <div class="article-card-title" title="${displayTitle}">${displayTitle}</div>
        <div class="article-card-meta">
          <div class="article-card-meta-item">
            <span>📅</span>
            <span>${displayTime}</span>
          </div>
          <div class="article-card-meta-item">
            <span>📏</span>
            <span>${displaySize}</span>
          </div>
          <div class="article-card-meta-item">
            <span>🕐</span>
            <span>${displayCreatedAt}</span>
          </div>
        </div>`;
      div.onclick = () => openArticle(a);
      gridEl.appendChild(div);
    });

    // 更新统计
    if (statsEl) {
      const kw = keyword ? ` · 搜索"${keyword}"` : '';
      statsEl.textContent = `共 ${_historyState.total} 篇${kw}`;
    }

  } catch (e) {
    console.error('加载历史文章失败:', e);
    if (_historyState.page === 1 && gridEl.children.length === 0) {
      gridEl.innerHTML = `<div style="color:#dc3545;text-align:center;padding:40px;grid-column:1/-1;">加载失败：${e.message}</div>`;
    }
  } finally {
    _historyState.loading = false;
    if (loadMoreEl) loadMoreEl.style.display = 'none';
    if (endEl && !_historyState.hasMore && _historyState.total > 0) endEl.style.display = 'flex';
  }
}

// 加载更多文章（无限滚动）
function loadMoreArticles() {
  if (_historyState.loading || !_historyState.hasMore) return;
  _historyState.page++;
  loadHistory(false);
}

// 搜索处理（带防抖）
function onHistorySearch() {
  const input = document.getElementById('history-search');
  const clearBtn = document.getElementById('history-search-clear');
  if (clearBtn) clearBtn.style.display = input.value ? 'flex' : 'none';

  clearTimeout(_historyState.debounceTimer);
  _historyState.debounceTimer = setTimeout(() => {
    _historyState.keyword = input.value.trim();
    _historyState.page = 1;
    _historyState.hasMore = true;
    loadHistory();
  }, 350);
}

// 清除搜索
function clearHistorySearch() {
  const input = document.getElementById('history-search');
  const clearBtn = document.getElementById('history-search-clear');
  if (input) input.value = '';
  if (clearBtn) clearBtn.style.display = 'none';
  _historyState.keyword = '';
  _historyState.page = 1;
  _historyState.hasMore = true;
  loadHistory();
}

// 预览文章（history.html 表格布局使用）
async function previewArticle(filename) {
  if (!filename) return;

  const previewContent = document.getElementById('article-preview-content');
  if (!previewContent) {
    toast('无法找到预览元素', 'error');
    return;
  }

  document.getElementById('article-modal').classList.add('show');
  previewContent.textContent = '加载中...';

  try {
    const res  = await fetch(`/api/articles/${filename}`);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();

    if (data.error) {
      throw new Error(data.error);
    }

    previewContent.textContent = data.md_text || '(空内容)';
  } catch(e) {
    console.error('加载文章失败:', e);
    previewContent.textContent = `加载失败: ${e.message}`;
  }
}

async function openArticle(a) {
  state.currentArticleFilename = a.filename;
  state.currentArticleId = a.id;
  // 保存文章在服务器上的实际路径，推送时直接复用，避免重复创建文件
  state._currentArticleServerPath = null;  // 待后端返回
  document.getElementById('modal-article-title').textContent = a.title || a.filename;
  document.getElementById('modal-article-content').textContent = '加载中...';
  document.getElementById('article-modal').classList.add('show');

  try {
    // 优先用 article_history 接口（协同创作保存的文章）
    const url = a.id ? `/api/collaborative/articles/${a.id}` : `/api/articles/${a.filename}`;
    const res  = await fetch(url);
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    const data = await res.json();

    if (data.error) {
      throw new Error(data.error);
    }

    // article_history 接口返回 {article:{...content}}，旧接口返回 {md_text:...}
    const mdText = data.article ? (data.article.content || data.article.content_json || '') : (data.md_text || '(空内容)');
    document.getElementById('modal-article-content').textContent = mdText || '(空内容)';
    state._currentModalMd = mdText || '';
    // 记录服务器路径（后端返回 server_path 时存入，否则用 articles_path 约定拼接）
    state._currentArticleServerPath = data.server_path || null;
  } catch(e) {
    console.error('加载文章失败:', e);
    document.getElementById('modal-article-content').textContent = `加载失败: ${e.message}`;
    state._currentModalMd = null;
    state._currentArticleServerPath = null;
  }
}

async function deleteArticle(event, id) {
  if (event) event.stopPropagation();
  if (!id) return;

  // 用自定义美化弹框，替代原生 confirm()
  // 兼容两种元素 ID：confirm-modal-msg（history.html）
  const confirmMsg = document.getElementById('confirm-modal-msg');
  if (confirmMsg) {
    confirmMsg.textContent = `即将删除文章：${id}\n\n此操作不可恢复。`;
  }

  document.getElementById('confirm-modal').classList.add('show');

  // 等待用户点击确认或取消
  await new Promise(resolve => {
    // 兼容两种确认按钮 ID
    const okBtn = document.getElementById('confirm-modal-ok') || document.getElementById('confirm-ok-btn');
    const overlay = document.getElementById('confirm-modal');
    function onOk() {
      cleanup(); resolve(true);
    }
    function onCancel() {
      cleanup(); resolve(false);
    }
    function onOverlayClick(e) {
      if (e.target === overlay) { cleanup(); resolve(false); }
    }
    function cleanup() {
      if (okBtn) okBtn.removeEventListener('click', onOk);
      overlay.removeEventListener('click', onOverlayClick);
      closeModal('confirm-modal');
    }
    if (okBtn) {
      okBtn.addEventListener('click', onOk, { once: true });
    }
    overlay.addEventListener('click', onOverlayClick);
    // 取消按钮通过 closeModal 关闭，这里监听 modal 被关闭
    const cancelBtn = overlay.querySelector('.modal-footer .btn:not(.btn-primary)');
    if (cancelBtn) {
      cancelBtn.addEventListener('click', onCancel, { once: true });
    }
  }).then(async (confirmed) => {
    if (!confirmed) return;
    // 优先用 article_history 接口（协同创作保存的文章），回退到旧接口
    const url = (id && String(id).match(/^\d+$/)) ? `/api/collaborative/articles/${id}` : `/api/articles/${filename}`;
    const res  = await fetch(url, { method: 'DELETE' });
    const data = await res.json();
    if (data.success || data.ok || data.deleted) {
      toast('文章已删除', 'success');
      closeModal('article-modal');
      // 立即刷新列表
      loadHistory();
      // 如果在工作台，也刷新统计
      if (typeof loadDashStats === 'function') {
        loadDashStats();
      }
    } else {
      toast(data.error || '删除失败', 'error');
    }
  });
}

// 在编辑器中打开：基于历史文章新建预填充项目，跳转到工作台（Markdown 编辑器）
function loadArticleToEditor() {
  const id = state.currentArticleId;
  if (!id) { toast('未找到文章', 'error'); return; }
  closeModal('article-modal');
  // 新建预填充项目并跳转到工作台 Markdown 编辑器（支持编辑 + 保存）
  fetch('/api/collaborative/articles/' + id + '/continue', { method: 'POST' })
    .then(function (res) { return res.json().then(function (d) { return { ok: res.ok, data: d }; }); })
    .then(function (r) {
      if (r.ok && r.data.project_id) {
        window.location.href = '/collaborative/' + r.data.project_id;
      } else {
        toast(r.data.error || '操作失败，请重试', 'error');
      }
    })
    .catch(function (e) { toast('操作失败：' + e.message, 'error'); });
}

// ═══════════════════════════════════════════════════
// 系统配置
// ═══════════════════════════════════════════════════
function toggleAccordion(id) {
  const el = document.getElementById(id);
  const isOpen = el.classList.contains('open');

  // 关闭所有
  document.querySelectorAll('.accordion').forEach(acc => {
    acc.classList.remove('open');
  });

  // 如果之前是关闭的，则打开
  if (!isOpen) {
    el.classList.add('open');
  }
}

async function loadConfig() {
  // 默认打开第一个手风琴（账号管理）
  document.getElementById('acc-accounts').classList.add('open');

  // 加载账号列表
  await renderAccountList();

  // 加载领域列表
  await loadDomains();

  // 加载AI模型列表
  await loadAIModels();
}

async function renderAccountList() {
  const res = await fetch('/api/accounts');
  const data = await res.json();
  const container = document.getElementById('account-list');
  if (!container) return;

  const accountArray = data.accounts || [];

  // 初始化全局 accounts 对象和 currentAccountId
  accounts = {};
  accountArray.forEach(acc => {
    accounts[acc.account_id] = acc;
  });
  currentAccountId = data.default_account_id || '';

  // 更新顶部账号选择器
  const selector = document.getElementById('account-selector');
  if (selector) {
    selector.innerHTML = '<option value="">-- 选择账号 --</option>';
    Object.entries(accounts).forEach(([id, acc]) => {
      const opt = document.createElement('option');
      opt.value = id;
      opt.textContent = acc.name || id;
      if (id === currentAccountId) opt.selected = true;
      selector.appendChild(opt);
    });
    if (currentAccountId && selector.value === '') {
      selector.value = currentAccountId;
    }
  }

  if (accountArray.length === 0) {
    container.innerHTML = `
      <div style="text-align:center;color:var(--text2);padding:40px 0;font-size:13px;">
        <div style="font-size:36px;margin-bottom:12px;">📱</div>
        暂无账号，点击右上角「+ 新增账号」添加
      </div>`;
    return;
  }

  // 颜色主题映射
  const themeGradients = {
    green: 'linear-gradient(135deg,#07c160,#0d9e4f)',
    blue:  'linear-gradient(135deg,#4f8ef7,#2563eb)',
    warm:  'linear-gradient(135deg,#f5a623,#e07b39)',
    dark:  'linear-gradient(135deg,#6b7280,#374151)',
  };

  const grid = document.createElement('div');
  grid.className = 'account-grid';

  accountArray.forEach(acc => {
    const isDefault = acc.account_id === data.default_account_id;
    const gradient = themeGradients[acc.theme] || themeGradients.blue;
    // 取账号名首字作为头像
    const avatarChar = (acc.name || acc.account_id).charAt(0).toUpperCase();
    const appIdMasked = acc.app_id
      ? acc.app_id.substring(0, 4) + '****' + acc.app_id.slice(-4)
      : '未配置';

    const card = document.createElement('div');
    card.className = 'account-card' + (isDefault ? ' is-default' : '');
    card.innerHTML = `
      ${isDefault ? '<div class="account-default-badge">✓ 默认</div>' : ''}
      <div class="account-card-header">
        <div class="account-avatar" style="background:${gradient};">${avatarChar}</div>
        <div>
          <div class="account-card-name">${acc.name || acc.account_id}</div>
          <div class="account-card-id">ID: ${acc.account_id}</div>
        </div>
      </div>
      <div class="account-card-meta">
        <div class="account-card-meta-row">
          <span>👤 作者</span>
          <span>${acc.author || '未填写'}</span>
        </div>
        <div class="account-card-meta-row">
          <span>🔑 AppID</span>
          <span>${appIdMasked}</span>
        </div>
        <div class="account-card-meta-row">
          <span>📂 领域</span>
          <span>${acc.domain || '科技'}</span>
        </div>
        <div class="account-card-meta-row">
          <span>✍️ 风格</span>
          <span>${acc.article_style || '观点评论'} · ${acc.word_count || 2000} 字</span>
        </div>
      </div>
      <div class="account-card-actions">
        ${!isDefault ? `<button class="btn btn-secondary btn-sm" onclick="setDefaultAccount(${acc.id})">设为默认</button>` : ''}
        <button class="btn btn-secondary btn-sm" onclick="checkAccountIP('${acc.account_id}')">🌐 检测IP</button>
        <button class="btn btn-secondary btn-sm" onclick="editAccount('${acc.account_id}')">✏️ 编辑</button>
        ${!isDefault ? `<button class="btn btn-danger btn-sm" onclick="deleteAccount(${acc.id})">🗑 删除</button>` : ''}
      </div>
    `;
    grid.appendChild(card);
  });

  container.innerHTML = '';
  container.appendChild(grid);
}

let editingAccountId = '';
let editingAccountDbId = null;

function toggleSecretVisibility() {
  const input = document.getElementById('acc-appsecret');
  const btn = document.getElementById('btn-toggle-secret');
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
    btn.title = '隐藏 AppSecret';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
    btn.title = '显示 AppSecret';
  }
}

function openAccountModal(accountId = null) {
  editingAccountId = accountId || '';
  editingAccountDbId = accountId ? accounts[accountId]?.id : null;
  const modal = document.getElementById('account-modal');
  const title = document.getElementById('account-modal-title');
  const idInput = document.getElementById('acc-id');

  // 填充领域选择框
  const domainSelect = document.getElementById('acc-domain');
  domainSelect.innerHTML = '';
  if (state.domains && state.domains.length > 0) {
    state.domains.forEach(d => {
      domainSelect.innerHTML += `<option value="${d.name}">${d.name}</option>`;
    });
  } else {
    domainSelect.innerHTML = '<option value="">暂无领域</option>';
  }

  title.textContent = accountId ? '编辑账号' : '新增账号';
  idInput.disabled = !!accountId;  // 编辑时禁止修改 ID

  if (accountId && accounts[accountId]) {
    const acc = accounts[accountId];
    document.getElementById('acc-id').value = accountId;
    document.getElementById('acc-name').value = acc.name || '';
    document.getElementById('acc-appid').value = acc.app_id || '';
    document.getElementById('acc-appsecret').value = '';  // 先清空，异步获取明文后填入
    document.getElementById('acc-author').value = acc.author || '';
    document.getElementById('acc-domain').value = acc.domain || '';
    document.getElementById('acc-topic-prompt').value = acc.topic_prompt || '';
  document.getElementById('acc-style').value = acc.article_style || '观点评论';
  document.getElementById('acc-words').value = acc.word_count || 2000;
  document.getElementById('acc-theme').value = acc.theme || 'blue';
  document.getElementById('acc-writing-prompt').value = acc.writing_prompt || '';
    document.getElementById('acc-ending-text').value = acc.ending_text || '感谢阅读，我们下期见。';
    document.getElementById('acc-set-default').checked = accountId === currentAccountId;

    // 异步获取明文 AppSecret（后端单独接口）
    if (acc.id) {
      fetch(`/api/accounts/${acc.id}`)
        .then(r => r.json())
        .then(detail => {
          if (detail && detail.app_secret) {
            document.getElementById('acc-appsecret').value = detail.app_secret;
          }
        })
        .catch(() => {});  // 失败时静默处理，用户可手动填写
    }
  } else {
    // 清空表单
    document.getElementById('acc-id').value = '';
    document.getElementById('acc-name').value = '';
    document.getElementById('acc-appid').value = '';
    document.getElementById('acc-appsecret').value = '';
    document.getElementById('acc-author').value = '';
    document.getElementById('acc-domain').value = '';
    document.getElementById('acc-topic-prompt').value = '';
    document.getElementById('acc-style').value = '观点评论';
    document.getElementById('acc-words').value = 2000;
    document.getElementById('acc-theme').value = 'blue';
    document.getElementById('acc-writing-prompt').value = '';
    document.getElementById('acc-ending-text').value = '感谢阅读，我们下期见。';
    document.getElementById('acc-set-default').checked = Object.keys(accounts).length === 0;  // 第一个账号自动设为默认
  }

  modal.classList.add('show');
}

async function saveAccount() {
  const accountId = document.getElementById('acc-id').value.trim();
  if (!accountId) return toast('请填写账号 ID', 'error');

  const payload = {
    id: editingAccountDbId,  // 编辑时传数据库 ID
    account_id: accountId,
    name: document.getElementById('acc-name').value.trim(),
    app_id: document.getElementById('acc-appid').value.trim(),
    app_secret: document.getElementById('acc-appsecret').value.trim(),
    author: document.getElementById('acc-author').value.trim(),
    domain: document.getElementById('acc-domain').value,
    topic_prompt: document.getElementById('acc-topic-prompt').value.trim(),
    article_style: document.getElementById('acc-style').value,
    word_count: parseInt(document.getElementById('acc-words').value) || 2000,
    theme: document.getElementById('acc-theme').value,
    writing_prompt: document.getElementById('acc-writing-prompt').value.trim(),
    ending_text: document.getElementById('acc-ending-text').value.trim() || '感谢阅读，我们下期见。',
    set_as_default: document.getElementById('acc-set-default').checked,
  };

  const btn = document.getElementById('acc-save-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 保存中...';

  try {
    const res = await fetch('/api/accounts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success || data.ok) {
      toast('账号保存成功！', 'success');
      closeModal('account-modal');
      await loadAccounts();
      await renderAccountList();
      // 如果设为了默认账号，更新全局选择器当前值
      if (payload.set_as_default && accounts[accountId]) {
        currentAccountId = accountId;
        const selector = document.getElementById('account-selector');
        if (selector) selector.value = accountId;
      }
    } else {
      toast(data.error || '保存失败', 'error');
    }
  } catch(e) {
    toast('保存失败：' + e.message, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 保存账号';
  }
}

function editAccount(accountId) {
  openAccountModal(accountId);
}

async function deleteAccount(accountDbId) {
  if (!confirm(`确定要删除此账号吗？`)) return;

  try {
    const res = await fetch(`/api/accounts/${accountDbId}`, { method: 'DELETE' });
    const data = await res.json();
    if (data.success || data.ok) {
      toast('账号已删除', 'success');
      await loadAccounts();
      await renderAccountList();
    } else {
      toast(data.error || '删除失败', 'error');
    }
  } catch(e) {
    toast('删除失败：' + e.message, 'error');
  }
}

async function setDefaultAccount(accountDbId) {
  try {
    const res = await fetch(`/api/accounts/${accountDbId}/set_default`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
    });
    const data = await res.json();
    if (data.success || data.ok) {
      toast('已设为默认账号', 'success');
      await loadAccounts();
      await renderAccountList();
    } else {
      toast(data.error || '操作失败', 'error');
    }
  } catch(e) {
    toast('操作失败：' + e.message, 'error');
  }
}

async function checkAccountIP(accountId) {
  const toastMsg = `正在检测 ${accountId} 的访问IP...`;
  toast(toastMsg, 'info');

  try {
    const res = await fetch(`/api/accounts/check_ip`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({account_id: accountId})
    });
    const data = await res.json();

    if (data.success) {
      // 根据检测结果显示不同的信息
      const isAllowed = data.status === 'ok';
      const modal = document.createElement('div');
      modal.className = 'modal-overlay';
      modal.id = 'ip-modal';

      if (isAllowed) {
        // IP在白名单中
        modal.innerHTML = `
          <div class="modal" style="max-width:450px;">
            <div class="modal-header">
              <h3>🌐 IP检测结果</h3>
              <button class="modal-close" onclick="closeIPModal()">×</button>
            </div>
            <div class="modal-body" style="text-align:center;padding:30px 20px;">
              <div style="font-size:48px;margin-bottom:16px;">✅</div>
              <div style="font-size:16px;font-weight:600;margin-bottom:12px;color:var(--success);">
                IP地址已在白名单中
              </div>
              <div style="font-size:13px;color:var(--text2);margin-bottom:24px;">
                账号 <strong>${accountId}</strong> 可以正常访问平台 API
              </div>
              <div style="background:var(--bg2);padding:16px;border-radius:8px;text-align:left;margin-bottom:20px;">
                <div style="font-size:12px;color:var(--text2);margin-bottom:8px;">检测说明：</div>
                <ul style="margin:0;padding-left:20px;font-size:13px;line-height:1.8;color:var(--text1);">
                  <li>成功获取 access_token</li>
                  <li>IP白名单配置正确</li>
                  <li>可以正常发布文章</li>
                </ul>
              </div>
              <button class="btn btn-success" onclick="closeIPModal()" style="width:100%;">
                确定
              </button>
            </div>
          </div>
        `;
      } else if (data.status === 'not_allowed') {
        // IP未在白名单中
        modal.innerHTML = `
          <div class="modal" style="max-width:500px;">
            <div class="modal-header">
              <h3>🌐 IP检测结果</h3>
              <button class="modal-close" onclick="closeIPModal()">×</button>
            </div>
            <div class="modal-body" style="text-align:center;padding:30px 20px;">
              <div style="font-size:48px;margin-bottom:16px;">⚠️</div>
              <div style="font-size:16px;font-weight:600;margin-bottom:12px;color:var(--warning);">
                IP地址未在白名单中
              </div>
              <div style="background:#fff4e5;padding:12px;border-radius:6px;margin-bottom:16px;text-align:left;border:1px solid #ffd591;">
                <div style="font-size:12px;color:#856404;margin-bottom:6px;">错误详情：</div>
                <div style="font-size:13px;color:#333;margin-bottom:4px;">错误码：<strong>${data.errcode}</strong></div>
                <div style="font-size:13px;color:#333;word-break:break-all;">${data.errmsg}</div>
              </div>
              <div style="background:var(--bg2);padding:16px;border-radius:8px;text-align:left;margin-bottom:20px;">
                <div style="font-size:12px;color:var(--text2);margin-bottom:8px;">解决方案：</div>
                <ol style="margin:0;padding-left:20px;font-size:13px;line-height:1.8;color:var(--text1);">
                  <li>获取服务器公网IP地址（联系管理员或使用第三方检测工具）</li>
                  <li>登录平台后台</li>
                  <li>进入「开发 → 基本配置 → IP白名单」</li>
                  <li>点击「查看IP」，确认当前服务器IP</li>
                  <li>将IP地址添加到白名单并保存</li>
                </ol>
              </div>
              <button class="btn btn-primary" onclick="closeIPModal()" style="width:100%;">
                我知道了
              </button>
            </div>
          </div>
        `;
      } else {
        // 其他错误
        modal.innerHTML = `
          <div class="modal" style="max-width:400px;">
            <div class="modal-header">
              <h3>🌐 IP检测结果</h3>
              <button class="modal-close" onclick="closeIPModal()">×</button>
            </div>
            <div class="modal-body" style="text-align:center;padding:30px 20px;">
              <div style="font-size:48px;margin-bottom:16px;">❌</div>
              <div style="font-size:16px;font-weight:600;margin-bottom:12px;">
                检测失败
              </div>
              <div style="font-size:13px;color:var(--text2);margin-bottom:12px;">
                ${data.message}
              </div>
              ${data.errcode ? `<div style="font-size:12px;color:var(--text2);margin-bottom:8px;">错误码：${data.errcode}</div>` : ''}
              ${data.errmsg ? `<div style="font-size:12px;color:var(--text2);margin-bottom:20px;">错误信息：${data.errmsg}</div>` : ''}
              <button class="btn btn-secondary" onclick="closeIPModal()" style="width:100%;">
                关闭
              </button>
            </div>
          </div>
        `;
      }

      document.body.appendChild(modal);

      // 显示弹窗（添加 show 类触发动画）
      modal.classList.add('show');

      // 点击背景关闭
      modal.onclick = (e) => {
        if (e.target === modal) closeIPModal();
      };
    } else {
      toast(data.error || '检测失败', 'error');
    }
  } catch(e) {
    toast('检测失败：' + e.message, 'error');
  }
}

function closeIPModal() {
  const modal = document.getElementById('ip-modal');
  if (modal) {
    modal.remove();
  }
}

async function copyIP(ip) {
  try {
    await navigator.clipboard.writeText(ip);
    toast('✅ IP地址已复制到剪贴板', 'success');
  } catch(e) {
    // 降级方案
    const textarea = document.createElement('textarea');
    textarea.value = ip;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);
    toast('✅ IP地址已复制到剪贴板', 'success');
  }
}

// ═══════════════════════════════════════════════════
// 系统配置（仅 AI 配置）
// ═══════════════════════════════════════════════════
async function saveConfig() {
  const payload = {
    ai_api_key: document.getElementById('cfg-aikey').value,
    ai_api_base: document.getElementById('cfg-aibase').value,
    ai_model: document.getElementById('cfg-aimodel').value,
  };

  const btn = document.querySelector('[onclick="saveConfig()"]');
  btn.disabled = true;
  btn.textContent = '⏳ 保存中...';

  try {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    if (data.success || data.ok) toast('AI 配置已保存！', 'success');
    else toast('保存失败', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = '💾 保存 AI 配置';
  }
}

// ═══════════════════════════════════════════════════
// 领域分类管理
// ═══════════════════════════════════════════════════
let currentDomainId = null;

async function loadAIConfigForm() {
  // 加载 AI 基础配置到表单（API Key / Base URL / 模型）
  try {
    const res = await fetch('/api/config');
    const data = await res.json();
    const keyEl = document.getElementById('cfg-aikey');
    const baseEl = document.getElementById('cfg-aibase');
    const modelEl = document.getElementById('cfg-aimodel');
    if (keyEl) keyEl.value = data.ai_api_key || '';
    if (baseEl) baseEl.value = data.ai_api_base || '';
    if (modelEl) modelEl.value = data.ai_model || '';
  } catch (e) {
    console.error('加载 AI 配置失败:', e);
  }
}

async function loadDomains() {
  try {
    const res = await fetch('/api/domains');
    const data = await res.json();
    if (data.ok) {
      renderDomainList(data.domains);
    } else {
      console.error('加载领域失败:', data.error);
    }
  } catch (e) {
    console.error('加载领域出错:', e);
  }
}

function renderDomainList(domains) {
  const container = document.getElementById('domain-list');
  if (!container) return;
  state.domains = domains;  // 保存到 state

  if (domains.length === 0) {
    container.innerHTML = '<div style="text-align:center;color:var(--text2);padding:32px 0;font-size:13px;">暂无领域分类，点击"新增领域"添加</div>';
    return;
  }

  // 分离系统领域和自定义领域
  const systemDomains = domains.filter(d => d.is_system === 1);
  const customDomains = domains.filter(d => d.is_system === 0);

  function buildWebsiteHtml(websites) {
    if (!websites || websites.length === 0) return '';
    return `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:6px;">
      ${websites.map(w => {
        const url = typeof w === 'string' ? w : (w.url || w);
        const name = typeof w === 'object' ? (w.name || url) : url;
        return `<a href="${url}" target="_blank" style="font-size:11px;color:var(--primary);background:var(--bg3);border:1px solid var(--border);border-radius:4px;padding:2px 8px;text-decoration:none;white-space:nowrap;" title="${url}">${name}</a>`;
      }).join('')}
    </div>`;
  }

  let html = '';
  if (systemDomains.length > 0) {
    html += '<div style="font-size:12px;color:var(--text2);margin:12px 0 8px;">系统默认领域</div>';
    html += '<div style="display:flex;flex-direction:column;gap:8px;margin-bottom:16px;">';
    systemDomains.forEach(d => {
      const websiteHtml = buildWebsiteHtml(d.ref_websites);
      html += `
        <div style="display:flex;align-items:flex-start;justify-content:space-between;padding:10px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;">
          <div style="flex:1;min-width:0;">
            <div style="font-weight:500;color:var(--text);margin-bottom:2px;">${d.name} <span style="font-size:11px;color:var(--text3);font-weight:400;background:var(--bg3);padding:1px 6px;border-radius:4px;">系统</span></div>
            <div style="font-size:12px;color:var(--text2);">${d.description || ''}</div>
            ${websiteHtml}
          </div>
          <button class="btn btn-sm btn-secondary" style="margin-left:12px;flex-shrink:0;" onclick="editDomain(${d.id})">编辑网站</button>
        </div>
      `;
    });
    html += '</div>';
  }

  if (customDomains.length > 0) {
    html += '<div style="font-size:12px;color:var(--text2);margin:12px 0 8px;">自定义领域</div>';
    html += '<div style="display:flex;flex-direction:column;gap:10px;">';
    customDomains.forEach(d => {
      const websiteHtml = buildWebsiteHtml(d.ref_websites);
      html += `
        <div style="display:flex;align-items:flex-start;justify-content:space-between;padding:12px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;">
          <div style="flex:1;min-width:0;">
            <div style="font-weight:500;color:var(--text);margin-bottom:4px;">${d.name}</div>
            <div style="font-size:12px;color:var(--text2);">${d.description || '暂无描述'}</div>
            ${websiteHtml}
          </div>
          <div style="display:flex;gap:8px;margin-left:12px;flex-shrink:0;">
            <button class="btn btn-sm btn-secondary" onclick="editDomain(${d.id})">编辑</button>
            <button class="btn btn-sm" style="background:rgba(239,68,68,0.1);color:#ef4444;border:1px solid rgba(239,68,68,0.25);" onclick="deleteDomain(${d.id})">删除</button>
          </div>
        </div>
      `;
    });
    html += '</div>';
  }

  container.innerHTML = html;
}

function openDomainModal(domainId = null) {
  currentDomainId = domainId;
  const titleEl = document.getElementById('domain-modal-title');
  const nameEl = document.getElementById('domain-name');
  const descEl = document.getElementById('domain-desc');
  const websitesEl = document.getElementById('domain-websites');
  const saveBtn = document.getElementById('domain-save-btn');

  if (domainId) {
    const d = state.domains.find(d => d.id === domainId);
    titleEl.textContent = d?.is_system ? '编辑领域网站' : '编辑领域分类';
    nameEl.value = d?.name || '';
    nameEl.disabled = !!d?.is_system;  // 系统领域名称不可改
    descEl.disabled = !!d?.is_system;  // 系统领域描述不可改
    descEl.value = d?.description || '';
    // 将网站列表转为每行一个
    const sites = d?.ref_websites || [];
    websitesEl.value = sites.map(w => {
      if (typeof w === 'object') {
        // 如果 name 里已经包含 url，说明是之前解析异常导致重复，只保留 name
        if (w.name && w.url && w.name.includes(w.url)) return w.name;
        if (w.name && w.url) return `${w.name}：${w.url}`;  // 中文冒号
        return w.url || w.name || '';
      }
      return w;
    }).join('\n');
  } else {
    titleEl.textContent = '新增领域分类';
    nameEl.disabled = false;
    descEl.disabled = false;
    nameEl.value = '';
    descEl.value = '';
    websitesEl.value = '';
  }

  openModal('domain-modal');
}

async function editDomain(domainId) {
  const domain = state.domains?.find(d => d.id === domainId);
  if (!domain) return;
  // 系统领域可以编辑网站，但不可改名
  openDomainModal(domainId);
}

async function saveDomain() {
  const name = document.getElementById('domain-name').value.trim();
  const desc = document.getElementById('domain-desc').value.trim();
  const websitesRaw = document.getElementById('domain-websites').value.trim();
  const saveBtn = document.getElementById('domain-save-btn');

  if (!name) {
    toast('请输入领域名称', 'error');
    return;
  }

  // 解析网站列表：每行一个，支持"名称:URL"或"名称：URL"（中英文冒号）或直接"URL"格式
  const ref_websites = websitesRaw
    .split('\n')
    .map(line => line.trim())
    .filter(line => line && (line.startsWith('http') || line.includes('/') || line.includes(':')))
    .map(line => {
      // 纯 URL 起头
      if (line.startsWith('http')) {
        try {
          return {name: new URL(line).hostname.replace('www.', ''), url: line};
        } catch (e) {
          return {name: line, url: line};
        }
      }
      // 尝试用中英文冒号分割 "名称:URL" / "名称：URL"
      // 注意要匹配冒号后面紧跟 http 或 /
      const match = line.match(/^(.+?)\s*[:：]\s*(https?:\/\/.+)/i);
      if (match) {
        return {name: match[1].trim(), url: match[2].trim()};
      }
      // 兜底：整行作为 url
      return {name: line, url: line};
    });

  saveBtn.disabled = true;
  saveBtn.textContent = '⏳ 保存中...';

  try {
    const isSystem = state.domains?.find(d => d.id === currentDomainId)?.is_system;
    const url = currentDomainId ? `/api/domains/${currentDomainId}` : '/api/domains';
    const method = currentDomainId ? 'PUT' : 'POST';

    // 系统领域只提交 ref_websites，不传 name/description
    const body = isSystem
      ? {ref_websites}
      : {name, description: desc, ref_websites};

    const res = await fetch(url, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body),
    });
    const data = await res.json();

    if (data.ok) {
      toast(currentDomainId ? '领域已更新' : '领域已创建', 'success');
      closeModal('domain-modal');
      loadDomains();
    } else {
      toast(data.error || '操作失败', 'error');
    }
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = '💾 保存领域';
  }
}

async function deleteDomain(domainId) {
  const domain = state.domains?.find(d => d.id === domainId);
  if (!domain) return;

  if (domain.is_system === 1) {
    toast('系统领域不可删除', 'error');
    return;
  }

  if (!confirm(`确认删除领域「${domain.name}」吗？`)) return;

  const res = await fetch(`/api/domains/${domainId}`, {method: 'DELETE'});
  const data = await res.json();

  if (data.ok) {
    toast('领域已删除', 'success');
    loadDomains();
  } else {
    toast(data.error || '删除失败', 'error');
  }
}

// ═══════════════════════════════════════════════════
// AI 模型管理
// ═══════════════════════════════════════════════════

let aiModels = [];
let currentAIModelId = null;

async function loadAIModels() {
  try {
    const res = await fetch('/api/ai_models');
    const data = await res.json();
    if (data.ok) {
      aiModels = data.models || [];
      renderAIModelList(aiModels);
    } else {
      console.error('加载AI模型失败:', data.error);
    }
  } catch (e) {
    console.error('加载AI模型出错:', e);
  }
}

function renderAIModelList(models) {
  const container = document.getElementById('ai-model-list');
  if (!container) return;

  if (models.length === 0) {
    container.innerHTML = '<div style="text-align:center;color:var(--text2);padding:32px 0;font-size:13px;">暂无AI模型配置，点击"新增模型"添加</div>';
    return;
  }

  // 分离默认模型和其他模型
  const defaultModel = models.find(m => m.is_default === 1);
  const otherModels = models.filter(m => m.is_default === 0);

  let html = '';

  // 默认模型
  if (defaultModel) {
    const imgBadge = defaultModel.is_image_model ? '<span class="badge" style="background:rgba(59,130,246,0.2);color:#3b82f6;font-size:11px;padding:4px 8px;border-radius:4px;">🖼️ 图像</span>' : '';
    html += `
      <div style="display:flex;align-items:center;justify-content:space-between;padding:14px 16px;background:rgba(34,197,94,0.1);border:1px solid rgba(34,197,94,0.3);border-radius:8px;margin-bottom:12px;">
        <div style="display:flex;align-items:center;gap:10px;">
          <div style="font-size:20px;">${defaultModel.is_image_model ? '🖼️' : '🤖'}</div>
          <div>
            <div style="font-weight:600;color:var(--text);margin-bottom:4px;">${defaultModel.name}</div>
            <div style="font-size:12px;color:var(--text2);">
              ${defaultModel.provider} · ${defaultModel.model_name}
            </div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:8px;">
          <span class="badge" style="background:rgba(34,197,94,0.2);color:#22c55e;font-size:11px;padding:4px 8px;border-radius:4px;">默认</span>
          ${imgBadge}
          <button class="btn btn-sm btn-secondary" onclick="editAIModel(${defaultModel.id})">编辑</button>
          <button class="btn btn-sm" style="background:rgba(239,68,68,0.1);color:#ef4444;border:1px solid rgba(239,68,68,0.25);" onclick="deleteAIModel(${defaultModel.id})">删除</button>
        </div>
      </div>
    `;
  }

  // 其他模型
  if (otherModels.length > 0) {
    html += '<div style="font-size:12px;color:var(--text2);margin:12px 0 8px;">其他模型</div>';
    html += '<div style="display:flex;flex-direction:column;gap:10px;">';
    otherModels.forEach(m => {
      const imgBadge = m.is_image_model ? '<span class="badge" style="background:rgba(59,130,246,0.2);color:#3b82f6;font-size:11px;padding:4px 8px;border-radius:4px;">🖼️ 图像</span>' : '';
      html += `
        <div style="display:flex;align-items:center;justify-content:space-between;padding:12px 14px;background:var(--bg2);border:1px solid var(--border);border-radius:8px;">
          <div style="display:flex;align-items:center;gap:10px;">
            <div style="font-size:18px;">${m.is_image_model ? '🖼️' : '🤖'}</div>
            <div>
              <div style="font-weight:500;color:var(--text);margin-bottom:4px;">${m.name}</div>
              <div style="font-size:12px;color:var(--text2);">
                ${m.provider} · ${m.model_name}
              </div>
            </div>
          </div>
          <div style="display:flex;gap:8px;">
            ${imgBadge}
            <button class="btn btn-sm btn-primary" onclick="setDefaultAIModel(${m.id})">设为默认</button>
            <button class="btn btn-sm btn-secondary" onclick="editAIModel(${m.id})">编辑</button>
            <button class="btn btn-sm" style="background:rgba(239,68,68,0.1);color:#ef4444;border:1px solid rgba(239,68,68,0.25);" onclick="deleteAIModel(${m.id})">删除</button>
          </div>
        </div>
      `;
    });
    html += '</div>';
  }

  container.innerHTML = html;
}

function openAIModelModal(modelId = null) {
  currentAIModelId = modelId;
  const titleEl = document.getElementById('ai-model-modal-title');
  const nameEl = document.getElementById('ai-model-name');
  const providerEl = document.getElementById('ai-model-provider');
  const modelNameEl = document.getElementById('ai-model-model');
  const apiKeyEl = document.getElementById('ai-model-api-key');
  const apiBaseEl = document.getElementById('ai-model-base-url');
  const isImageEl = document.getElementById('ai-model-is-image');
  const saveBtn = document.getElementById('ai-model-save-btn');

  if (modelId) {
    const model = aiModels.find(m => m.id === modelId);
    titleEl.textContent = '编辑 AI 模型';
    nameEl.value = model?.name || '';
    providerEl.value = model?.provider || 'openai';
    modelNameEl.value = model?.model_name || '';
    apiKeyEl.value = '';  // 不回填API密钥
    apiBaseEl.value = model?.api_base || '';
    isImageEl.checked = model?.is_image_model ? true : false;
  } else {
    titleEl.textContent = '新增 AI 模型';
    nameEl.value = '';
    providerEl.value = 'openai';
    modelNameEl.value = '';
    apiKeyEl.value = '';
    apiBaseEl.value = '';
    isImageEl.checked = false;
  }

  openModal('ai-model-modal');
}

async function editAIModel(modelId) {
  const model = aiModels.find(m => m.id === modelId);
  if (!model) return;
  openAIModelModal(modelId);
}

async function saveAIModel() {
  const name = document.getElementById('ai-model-name').value.trim();
  const provider = document.getElementById('ai-model-provider').value;
  const modelName = document.getElementById('ai-model-model').value.trim();
  const apiKey = document.getElementById('ai-model-api-key').value.trim();
  const apiBase = document.getElementById('ai-model-base-url').value.trim();
  const isImageModel = document.getElementById('ai-model-is-image').checked;
  const saveBtn = document.getElementById('ai-model-save-btn');

  if (!name) {
    toast('请输入模型名称', 'error');
    return;
  }
  if (!modelName) {
    toast('请输入模型标识', 'error');
    return;
  }
  if (!currentAIModelId && !apiKey) {
    toast('请输入API密钥', 'error');
    return;
  }

  saveBtn.disabled = true;
  saveBtn.textContent = '⏳ 保存中...';

  try {
    const url = currentAIModelId ? `/api/ai_models/${currentAIModelId}` : '/api/ai_models';
    const method = currentAIModelId ? 'PUT' : 'POST';

    const payload = {name, provider, model_name: modelName, is_image_model: isImageModel};
    if (apiKey) payload.api_key = apiKey;
    if (apiBase) payload.api_base = apiBase;

    const res = await fetch(url, {
      method,
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(payload),
    });
    const data = await res.json();

    if (data.ok) {
      toast(currentAIModelId ? '模型已更新' : '模型已创建', 'success');
      closeModal('ai-model-modal');
      loadAIModels();
    } else {
      toast(data.error || '操作失败', 'error');
    }
  } finally {
    saveBtn.disabled = false;
    saveBtn.textContent = '💾 保存模型';
  }
}

async function setDefaultAIModel(modelId) {
  const res = await fetch(`/api/ai_models/${modelId}/set_default`, {method: 'POST'});
  const data = await res.json();

  if (data.ok) {
    toast('已设为默认模型', 'success');
    loadAIModels();
  } else {
    toast(data.error || '操作失败', 'error');
  }
}

async function deleteAIModel(modelId) {
  const model = aiModels.find(m => m.id === modelId);
  if (!model) return;

  if (!confirm(`确认删除模型「${model.name}」吗？`)) return;

  const res = await fetch(`/api/ai_models/${modelId}`, {method: 'DELETE'});
  const data = await res.json();

  if (data.ok) {
    toast('模型已删除', 'success');
    loadAIModels();
  } else {
    toast(data.error || '删除失败', 'error');
  }
}

// ═══════════════════════════════════════════════════


// ═══════════════════════════════════════════════════
// 文章复制导入
// ═══════════════════════════════════════════════════
async function parseImportedArticle() {
  const source = document.getElementById('import-source').value.trim();
  if (!source) {
    toast('请先粘贴文章内容', 'error');
    return;
  }

  // 按行分割
  const lines = source.split('\n');
  let title = '';
  const bodyLines = [];

  // 第一行作为标题（去除空行）
  for (const line of lines) {
    if (line.trim()) {
      title = line.trim().replace(/^#+\s*/, ''); // 去除开头的 # ## 等 Markdown 标题标记
      break;
    }
  }

  // 处理正文：识别小标题
  let inBody = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!inBody) {
      inBody = true;
      continue; // 跳过标题行
    }
    if (!trimmed) {
      bodyLines.push(''); // 保留空行
      continue;
    }
    // 识别小标题模式
    if (/^(第[一二三四五六七八九十零\d]+[章节部分]|第\d+节|### |## |【|▌|▍|▎|■|▪|•|·|\d+\.)/.test(trimmed)) {
      bodyLines.push(`\n## ${trimmed.replace(/^#+\s*/, '').replace(/^【|】$/g, '')}\n`);
    } else {
      bodyLines.push(trimmed);
    }
  }

  let markdown = bodyLines.join('\n');

  // 如果没有正文内容，添加一个占位段落
  if (!markdown.trim()) {
    markdown = '文章内容...';
  }

  // 填充表单
  document.getElementById('import-title').value = title;
  document.getElementById('import-markdown').value = markdown;
  document.getElementById('import-result-card').style.display = 'block';

  // 实时预览
  await previewImportMarkdown();

  toast('解析完成！', 'success');
}

async function previewImportMarkdown() {
  const md = document.getElementById('import-markdown').value;
  const preview = document.getElementById('import-preview');
  const theme = document.getElementById('import-theme')?.value || 'blue';
  const template = document.getElementById('import-template')?.value || '';

  if (!md.trim()) {
    preview.innerHTML = '';
    return;
  }

  // 获取当前账号的 ending_text
  const selector = document.getElementById('account-selector');
  const accountId = selector ? selector.value : currentAccountId;
  const endingText = (accountId && accounts[accountId]) ? accounts[accountId].ending_text || '' : '';

  try {
    const res = await fetch('/api/preview', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ md_text: md, theme, template, ending_text: endingText }),
    });
    const data = await res.json();
    if (data.success || data.ok) {
      preview.innerHTML = data.html;
    } else {
      preview.textContent = data.error || '预览生成失败';
    }
  } catch (e) {
    preview.textContent = '预览生成失败：' + e.message;
  }
}

// 刷新导入预览
async function refreshImportPreview() {
  await previewImportMarkdown();
}

// 复制导入的 Markdown
function copyImportMd() {
  const editor = document.getElementById('import-markdown');
  if (!editor) return;
  const md = editor.value;
  if (!md.trim()) {
    toast('请先生成 Markdown 内容', 'error');
    return;
  }
  navigator.clipboard.writeText(md).then(() => {
    toast('Markdown 内容已复制到剪贴板', 'success');
  }).catch(() => {
    toast('复制失败', 'error');
  });
}

// 复制导入的富文本格式
async function copyImportWechatHtml() {
  const preview = document.getElementById('import-preview');
  if (!preview) return;
  const html = preview.innerHTML;
  if (!html || html.trim() === '') {
    toast('请先生成预览内容', 'error');
    return;
  }

  try {
    const clipboardItem = new ClipboardItem({
      'text/html': new Blob([html], {type: 'text/html'}),
      'text/plain': new Blob([html], {type: 'text/plain'})
    });
    await navigator.clipboard.write([clipboardItem]);
    toast('✅ 已复制富文本内容！<br>现在可以直接粘贴到编辑器中', 'success');
  } catch (e) {
    try {
      await navigator.clipboard.writeText(html);
      toast('✅ 已复制内容（纯文本模式）<br>粘贴后可能需要重新调整格式', 'success');
    } catch (e2) {
      toast('❌ 复制失败，请手动选择内容复制', 'error');
    }
  }
}

async function copyImportHtml() {
  const preview = document.getElementById('import-preview');
  const html = preview.innerHTML;
  if (!html || html.trim() === '') {
    toast('请先生成预览内容', 'error');
    return;
  }

  try {
    const clipboardItem = new ClipboardItem({
      'text/html': new Blob([html], {type: 'text/html'}),
      'text/plain': new Blob([html], {type: 'text/plain'})
    });
    await navigator.clipboard.write([clipboardItem]);
    toast('✅ 已复制富文本内容！<br>现在可以直接粘贴到编辑器中', 'success');
  } catch (e) {
    try {
      await navigator.clipboard.writeText(html);
      toast('✅ 已复制内容（纯文本模式）<br>粘贴后可能需要重新调整格式', 'success');
    } catch (e2) {
      toast('❌ 复制失败，请手动选择内容复制', 'error');
    }
  }
}

async function aiFormatArticle() {
  const md = document.getElementById('import-markdown').value.trim();
  if (!md) {
    toast('请先解析文章或输入 Markdown 内容', 'error');
    return;
  }

  const logCard = document.getElementById('import-format-log-card');
  const logEl = document.getElementById('import-format-log');
  const btn = document.getElementById('ai-format-btn');

  logCard.style.display = 'block';
  logEl.innerHTML = '';
  if (btn) { btn.disabled = true; btn.textContent = '⏳ 排版中...'; }

  const taskId = uuid();
  const res = await fetch('/api/format', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ task_id: taskId, md_text: md }),
  });
  const data = await res.json();
  if (!data.ok) {
    toast(data.error || '启动排版任务失败', 'error');
    if (btn) { btn.disabled = false; btn.textContent = '🤖 AI 排版优化'; }
    return;
  }

  subscribeSSE(taskId, logEl, (result) => {
    if (result.formatted_md) {
      document.getElementById('import-markdown').value = result.formatted_md;
      previewImportMarkdown();
      toast('AI 排版完成！', 'success');
    }
  }, () => {
    if (btn) { btn.disabled = false; btn.textContent = '🤖 AI 排版优化'; }
  });
}

async function publishImportedArticle() {
  const title = document.getElementById('import-title').value.trim();
  const md = document.getElementById('import-markdown').value.trim();

  if (!title || !md) {
    toast('请确保标题和内容不为空', 'error');
    return;
  }

  // 验证是否选择了账号
  if (!currentAccountId) {
    toast('请先在右上角选择账号！', 'error');
    return;
  }

  // 构造 Markdown（标题 + 内容）
  const fullMd = `# ${title}\n\n${md}`;

  const theme = document.getElementById('import-theme')?.value || 'blue';
  const template = document.getElementById('import-template')?.value || '';
  const logCard = document.getElementById('import-log-card');
  const logEl = document.getElementById('import-log');
  const pubBtn = document.getElementById('import-publish-btn');

  logCard.style.display = 'block';
  logEl.innerHTML = '';
  if (pubBtn) { pubBtn.disabled = true; pubBtn.textContent = '⏳ 推送中...'; }

  // 显示当前选择的账号
  const accountName = accounts[currentAccountId]?.name || currentAccountId;
  console.log(`[推送草稿] 当前使用账号: ${accountName} (ID: ${currentAccountId})`);

  const taskId = uuid();
  const res = await fetch('/api/publish', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ task_id: taskId, account_id: currentAccountId, theme, template, md_text: fullMd }),
  });
  const data = await res.json();
  if (!data.ok) {
    toast(data.error || '启动推送任务失败', 'error');
    if (pubBtn) { pubBtn.disabled = false; pubBtn.textContent = '📤 推送到草稿箱'; }
    return;
  }

  subscribeSSE(taskId, logEl, (result) => {
    if (result.success) {
      toast('草稿已保存到本地！', 'success');
    } else {
      toast(result.msg || '推送失败', 'error');
    }
  }, () => {
    if (pubBtn) { pubBtn.disabled = false; pubBtn.textContent = '📤 推送到草稿箱'; }
  });
}


// JSON 语法高亮
function highlightJSON(jsonStr) {
  if (!jsonStr) return '';
  try {
    const json = JSON.parse(jsonStr);
    return syntaxHighlight(JSON.stringify(json, null, 2));
  } catch {
    return escapeHtml(jsonStr);
  }
}

// 简单的语法高亮函数
function syntaxHighlight(json) {
  json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?|\b(true|false|null)\b|-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g, function (match) {
    let cls = 'json-number';
    if (/^"/.test(match)) {
      if (/:$/.test(match)) {
        cls = 'json-key';
      } else {
        cls = 'json-string';
      }
    } else if (/true|false/.test(match)) {
      cls = 'json-boolean';
    } else if (/null/.test(match)) {
      cls = 'json-null';
    }
    return '<span class="' + cls + '">' + match + '</span>';
  });
}

// 日志语法高亮（时间戳、错误、成功等）
function highlightLog(logStr) {
  if (!logStr) return '';
  let html = escapeHtml(logStr);

  // 高亮时间戳 [HH:MM:SS]
  html = html.replace(/\[\d{2}:\d{2}:\d{2}\]/g, '<span style="color:#569cd6;">$&</span>');

  // 高亮成功标记 ✓ / ✅ / success
  html = html.replace(/[✓✅]|\bsuccess\b/gi, '<span style="color:#4ec9b0;">$&</span>');

  // 高亮错误标记 ✗ / ❌ / error / failed
  html = html.replace(/[✗❌]|\b(error|failed|exception)\b/gi, '<span style="color:#f44747;">$&</span>');

  // 高亮警告标记 ⚠️ / warning
  html = html.replace(/[⚠️]|\bwarning\b/gi, '<span style="color:#cca700;">$&</span>');

  // 高亮信息标记 ℹ️ / info
  html = html.replace(/[ℹ️]|\binfo\b/gi, '<span style="color:#3794ff;">$&</span>');

  // 高亮 HTTP 状态码
  html = html.replace(/\b(200|201|204|301|302|400|401|403|404|500|502|503)\b/g, '<span style="color:#dcdcaa;">$&</span>');

  // 高亮 URL
  html = html.replace(/(https?:\/\/[^\s]+)/g, '<span style="color:#ce9178;">$1</span>');

  return html;
}

// HTML 转义
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// 格式化本地时间（正确处理时区）
function formatLocalTime(timeStr, format = 'YYYY-MM-DD HH:mm:ss') {
  if (!timeStr) return '-';

  // SQLite 存储的时间是本地时间，直接解析即可
  const date = new Date(timeStr);

  if (isNaN(date.getTime())) return '-';

  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const hours = String(date.getHours()).padStart(2, '0');
  const minutes = String(date.getMinutes()).padStart(2, '0');
  const seconds = String(date.getSeconds()).padStart(2, '0');

  switch (format) {
    case 'MM-DD HH:mm':
      return `${month}-${day} ${hours}:${minutes}`;
    case 'YYYY-MM-DD HH:mm:ss':
    default:
      return `${year}-${month}-${day} ${hours}:${minutes}:${seconds}`;
  }
}

// 加载用户资料
async function loadUserProfile() {
  const infoEl = document.getElementById('profile-info');
  if (!infoEl) return;  // 如果不在个人中心页面，直接返回

  infoEl.innerHTML = '<div style="text-align:center;padding:40px 0;"><div style="font-size:36px;margin-bottom:16px;">⏳</div><div style="color:var(--text2);">加载中...</div></div>';

  try {
    const res = await fetch('/api/user/current');
    const data = await res.json();

    if (!data.success || !data.user) {
      infoEl.innerHTML = '<div style="text-align:center;padding:40px 0;color:#dc3545;">加载失败：无法获取用户信息</div>';
      return;
    }

    const user = data.user;
    const createdAt = user.created_at ? formatLocalTime(user.created_at) : '-';

    infoEl.innerHTML = `
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:20px;">
        <div>
          <div style="color:var(--text2);font-size:13px;margin-bottom:6px;">用户名</div>
          <div style="font-size:15px;font-weight:500;">${user.username || '-'}</div>
        </div>
        <div>
          <div style="color:var(--text2);font-size:13px;margin-bottom:6px;">邮箱</div>
          <div style="font-size:15px;">${user.email || '-'}</div>
        </div>
        <div>
          <div style="color:var(--text2);font-size:13px;margin-bottom:6px;">注册时间</div>
          <div style="font-size:15px;">${createdAt}</div>
        </div>
        <div>
          <div style="color:var(--text2);font-size:13px;margin-bottom:6px;">用户ID</div>
          <div style="font-size:15px;font-family:monospace;">#${user.id}</div>
        </div>
      </div>
    `;
  } catch (e) {
    console.error('加载用户资料失败:', e);
    if (infoEl) {
      infoEl.innerHTML = '<div style="text-align:center;padding:40px 0;color:#dc3545;">加载失败：' + e.message + '</div>';
    }
  }
}

// ═══════════════════════════════════════════════════
// 侧边栏收缩/展开
// ═══════════════════════════════════════════════════
function toggleSidebar() {
  var sb = document.querySelector('.sidebar');
  if (!sb) return;
  sb.classList.toggle('collapsed');
  document.body.classList.toggle('sb-collapsed', sb.classList.contains('collapsed'));
  localStorage.setItem('sidebar_collapsed', sb.classList.contains('collapsed') ? '1' : '0');
}

(function restoreSidebarState() {
  if (localStorage.getItem('sidebar_collapsed') === '1') {
    var sb = document.querySelector('.sidebar');
    if (sb) { sb.classList.add('collapsed'); document.body.classList.add('sb-collapsed'); }
  }
})();

// ═══════════════════════════════════════════════════
// 全局初始化（在所有页面加载时执行）
// ═══════════════════════════════════════════════════
(async function initCommon() {
  // 加载当前用户信息
  await loadCurrentUser();

  // 加载账号列表
  await loadAccounts();

  // 加载配置（一次请求，填充各表单默认值）
  try {
    const res  = await fetch('/api/config');
    const data = await res.json();

    // 填充选题页 & 写稿页的表单默认值
    if (document.getElementById('topic-prompt')) {
      document.getElementById('topic-prompt').value  = data.topic_prompt || '';
    }
    // search_queries 已废弃，不再加载
    if (document.getElementById('write-style')) {
      document.getElementById('write-style').value   = data.article_style || '观点评论';
    }
    if (document.getElementById('write-words')) {
      document.getElementById('write-words').value   = data.word_count || 2000;
    }
    if (document.getElementById('write-theme')) {
      document.getElementById('write-theme').value   = data.theme || 'blue';
    }
  } catch(e) {
    console.error('初始化配置加载失败:', e);
    // 只有在非401错误时才显示提示，避免与登录跳转重复
    if (e.message && !e.message.includes('401')) {
      toast('连接服务失败，请确认服务已启动后刷新页面', 'error');
    }
  }

  // 初始化推送按钮状态（仅在写稿页有编辑器时）
  syncPublishBtn();
})();

// ═══════════════════════════════════════════════════
// AI助手抽屉面板（直接嵌入，非iframe）
// ═══════════════════════════════════════════════════
let aiAssistantPanel = null;
let aiAssistantLoaded = false;

function toggleAIAssistant() {
  if (!aiAssistantPanel) {
    createAIAssistantPanel();
  }
  aiAssistantPanel.classList.toggle('show');
  document.body.classList.toggle('ai-panel-open', aiAssistantPanel.classList.contains('show'));

  const btn = document.getElementById('ai-assistant-btn');
  if (btn) {
    btn.classList.toggle('pulse', aiAssistantPanel.classList.contains('show'));
  }
}

function createAIAssistantPanel() {
  aiAssistantPanel = document.createElement('div');
  aiAssistantPanel.className = 'ai-assistant-drawer';
  aiAssistantPanel.id = 'ai-assistant-panel';
  aiAssistantPanel.innerHTML = `
    <div class="ai-drawer-header">
      <div class="ai-drawer-title">
        <span class="icon">🤖</span>
        <span>AI 助手</span>
      </div>
      <button class="ai-drawer-close" onclick="toggleAIAssistant()" title="关闭">✕</button>
    </div>
    <div class="ai-drawer-body">
      <!-- 快捷功能 -->
      <div class="ai-quick-actions">
        <!-- 第一行：自由对话（绿色高亮）+ 2个功能 -->
        <button class="ai-quick-btn ai-chat-btn active" data-mode="chat" onclick="aiSetMode('chat')">
          <span>💬</span> 自由对话
        </button>
        <button class="ai-quick-btn" data-mode="writing" onclick="aiSetMode('writing')">
          <span>✍️</span> 辅助写作
        </button>
        <button class="ai-quick-btn" data-mode="polish" onclick="aiSetMode('polish')">
          <span>✨</span> 文章润色
        </button>
        <!-- 第二行：剩余4个功能 -->
        <button class="ai-quick-btn" data-mode="expand" onclick="aiSetMode('expand')">
          <span>📈</span> 内容扩写
        </button>
        <button class="ai-quick-btn" data-mode="condense" onclick="aiSetMode('condense')">
          <span>📉</span> 精简缩写
        </button>
        <button class="ai-quick-btn" data-mode="title" onclick="aiSetMode('title')">
          <span>🎯</span> 标题生成
        </button>
        <button class="ai-quick-btn" data-mode="topic" onclick="aiSetMode('topic')">
          <span>💡</span> 选题建议
        </button>
      </div>
      
      <!-- 对话区域 -->
      <div class="ai-chat-container">
        <div class="ai-chat-messages" id="ai-chat-messages">
          <div class="ai-welcome">
            <div class="ai-avatar">🤖</div>
            <div class="ai-welcome-text">
              <p>你好！我是你的 AI 写作助手。</p>
              <p>点击上方快捷功能开始，或直接输入你的问题。</p>
            </div>
          </div>
        </div>
        <div class="ai-chat-input-area">
          <div class="ai-mode-badge" id="ai-current-mode">自由对话</div>
          <textarea id="ai-chat-input" placeholder="输入你的问题..." rows="3" onkeydown="aiHandleKeydown(event)"></textarea>
          <div class="ai-input-actions">
            <span class="ai-hint">Enter 发送，Shift+Enter 换行</span>
            <button class="btn btn-primary btn-sm" onclick="aiSendMessage()">
              <span>📤</span> 发送
            </button>
          </div>
        </div>
      </div>
    </div>
  `;
  document.body.appendChild(aiAssistantPanel);

  // 点击外部关闭
  document.addEventListener('click', (e) => {
    const btn = document.getElementById('ai-assistant-btn');
    if (aiAssistantPanel &&
        aiAssistantPanel.classList.contains('show') &&
        !aiAssistantPanel.contains(e.target) &&
        btn && !btn.contains(e.target)) {
      toggleAIAssistant();
    }
  });

  // 加载历史记录
  aiLoadHistory();
}

// AI助手功能函数
let aiCurrentMode = 'chat';
let aiChatHistory = [];

const aiModeNames = {
  chat: '自由对话',
  writing: '辅助写作',
  polish: '文章润色',
  expand: '内容扩写',
  condense: '精简缩写',
  title: '标题生成',
  topic: '选题建议'
};

function aiSetMode(mode) {
  aiCurrentMode = mode;
  document.getElementById('ai-current-mode').textContent = aiModeNames[mode] || '自由对话';

  // 更新按钮状态
  document.querySelectorAll('.ai-quick-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === mode);
  });

  // 添加系统提示
  const messagesContainer = document.getElementById('ai-chat-messages');
  const modeHint = document.createElement('div');
  modeHint.className = 'ai-system-message';
  modeHint.innerHTML = `<span>已切换到：${aiModeNames[mode]}</span>`;
  messagesContainer.appendChild(modeHint);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function aiHandleKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    aiSendMessage();
  }
}

async function aiSendMessage() {
  const input = document.getElementById('ai-chat-input');
  const message = input.value.trim();
  if (!message) return;

  input.value = '';

    // 添加用户消息
    const messagesContainer = document.getElementById('ai-chat-messages');
    const userMsg = document.createElement('div');
    userMsg.className = 'ai-message ai-user';
    userMsg.innerHTML = `
      <div class="ai-bubble">
        ${escapeHtml(message)}
        <button class="ai-copy-btn" onclick="copyAiMessage(this, '${escapeHtml(message).replace(/'/g, "\\'")}')" title="复制">
          <span>📋</span>
        </button>
      </div>
    `;
    messagesContainer.appendChild(userMsg);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

  // 添加加载状态
  const loadingMsg = document.createElement('div');
  loadingMsg.className = 'ai-message ai-assistant';
  loadingMsg.id = 'ai-loading';
  loadingMsg.innerHTML = `
    <div class="ai-avatar">🤖</div>
    <div class="ai-bubble ai-loading">
      <span class="ai-dot"></span>
      <span class="ai-dot"></span>
      <span class="ai-dot"></span>
    </div>
  `;
  messagesContainer.appendChild(loadingMsg);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  try {
    const response = await fetch('/api/ai_assistant/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, mode: aiCurrentMode })
    });

    const data = await response.json();

    // 移除加载状态
    const loading = document.getElementById('ai-loading');
    if (loading) loading.remove();

    // 检查是否有错误
    let responseContent;
    if (!data.ok) {
      responseContent = data.error || '请求失败';
    } else {
      responseContent = data.content || data.response || '抱歉，我暂时无法回答。';
    }

    // 添加AI回复
    const aiMsg = document.createElement('div');
    aiMsg.className = 'ai-message ai-assistant';
    const safeContent = responseContent.replace(/'/g, "\\'").replace(/\n/g, "\\n");
    aiMsg.innerHTML = `
      <div class="ai-avatar">🤖</div>
      <div class="ai-bubble ${!data.ok ? 'ai-error' : ''}">
        ${formatAiResponse(responseContent)}
        <button class="ai-copy-btn" onclick="copyAiMessage(this, '${safeContent}')" title="复制">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor">
            <path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/>
          </svg>
        </button>
      </div>
    `;
    messagesContainer.appendChild(aiMsg);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // 保存历史
    aiChatHistory.push({ role: 'user', content: message });
    aiChatHistory.push({ role: 'assistant', content: responseContent });
    localStorage.setItem('ai_chat_history', JSON.stringify(aiChatHistory.slice(-20)));

  } catch (err) {
    const loading = document.getElementById('ai-loading');
    if (loading) loading.remove();

    const errorMsg = document.createElement('div');
    errorMsg.className = 'ai-message ai-assistant';
    errorMsg.innerHTML = `
      <div class="ai-avatar">🤖</div>
      <div class="ai-bubble ai-error">请求失败，请稍后重试</div>
    `;
    messagesContainer.appendChild(errorMsg);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

function aiLoadHistory() {
  const saved = localStorage.getItem('ai_chat_history');
  if (saved) {
    aiChatHistory = JSON.parse(saved);
    const messagesContainer = document.getElementById('ai-chat-messages');

    aiChatHistory.forEach(msg => {
      const msgDiv = document.createElement('div');
      msgDiv.className = `ai-message ai-${msg.role}`;
      const safeContent = msg.content.replace(/'/g, "\\'").replace(/\n/g, "\\n");
      const copyIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`;
      if (msg.role === 'user') {
        msgDiv.innerHTML = `
          <div class="ai-bubble">
            ${escapeHtml(msg.content)}
            <button class="ai-copy-btn" onclick="copyAiMessage(this, '${safeContent}')" title="复制">
              ${copyIcon}
            </button>
          </div>
        `;
      } else {
        msgDiv.innerHTML = `
          <div class="ai-avatar">🤖</div>
          <div class="ai-bubble">
            ${formatAiResponse(msg.content)}
            <button class="ai-copy-btn" onclick="copyAiMessage(this, '${safeContent}')" title="复制">
              ${copyIcon}
            </button>
          </div>
        `;
      }
      messagesContainer.appendChild(msgDiv);
    });

    messagesContainer.scrollTop = messagesContainer.scrollHeight;
  }
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function formatAiResponse(text) {
  if (!text || text.trim() === '') {
    return '<span style="color:var(--text2)">（无内容）</span>';
  }
  // 简单的Markdown格式化处理
  return escapeHtml(text)
    .replace(/\n/g, '<br>')
    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
    .replace(/`([^`]+)`/g, '<code>$1</code>');
}

function copyAiMessage(btn, text) {
  const copyIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"/></svg>`;
  const checkIcon = `<svg viewBox="0 0 24 24" width="16" height="16" fill="currentColor"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z"/></svg>`;

  navigator.clipboard.writeText(text).then(() => {
    btn.innerHTML = checkIcon;
    setTimeout(() => {
      btn.innerHTML = copyIcon;
    }, 1500);
  }).catch(() => {
    // 降级方案
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.opacity = '0';
    document.body.appendChild(textarea);
    textarea.select();
    document.execCommand('copy');
    document.body.removeChild(textarea);

    btn.innerHTML = checkIcon;
    setTimeout(() => {
      btn.innerHTML = copyIcon;
    }, 1500);
  });
}

// 版本：v2.5.8 (2026-04-15)
// 更新：AI助手改为抽屉式面板（直接嵌入，非iframe）
console.log('[common.js] 版本 v2.5.8 已加载');
console.log('[common.js] loadHistory 函数存在:', typeof loadHistory !== 'undefined');
console.log('[common.js] loadAccounts 函数存在:', typeof loadAccounts !== 'undefined');
