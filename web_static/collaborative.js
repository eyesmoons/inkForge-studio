/**
 * collaborative.js
 * 协同创作：历史文章前端逻辑（查看 / 继续编辑 / 删除）。
 *
 * 依赖 common.js 提供的 toast / formatTime（若页面已定义则复用）。
 */

// ── 工具函数 ──

function _escHtml(s) {
  return String(s == null ? '' : s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

// 字数统计：中文字符数 + 英文/数字词数
function _wordCount(text) {
  if (!text) return 0;
  const s = String(text);
  const cjk = (s.match(/[一-龥]/g) || []).length;
  const rest = s.replace(/[一-龥]/g, ' ');
  const words = rest.trim().split(/\s+/).filter(w => /[a-zA-Z0-9]/.test(w)).length;
  return cjk + words;
}

function _formatTime(ts) {
  if (!ts) return '';
  try {
    const s = String(ts).replace('T', ' ');
    return s.slice(0, 16);
  } catch (e) {
    return '';
  }
}

// ── 历史文章列表 ──

async function loadHistoryArticles() {
  const container = document.getElementById('history-articles-list');
  if (!container) return;
  try {
    const res = await fetch('/api/collaborative/articles');
    if (res.status === 401) {
      container.innerHTML = '<div class="dash-recent-empty">请先登录</div>';
      return;
    }
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    const articles = (data && data.articles) || [];

    if (!articles.length) {
      container.innerHTML = '<div class="dash-recent-empty">暂无历史文章</div>';
      return;
    }

    let html = '<table class="history-table"><thead><tr>'
      + '<th>标题</th><th>保存时间</th><th>字数</th><th>操作</th>'
      + '</tr></thead><tbody>';
    articles.forEach(art => {
      const id = art.id;
      const title = _escHtml(art.title || '无标题');
      const time = _escHtml(_formatTime(art.created_at));
      const wc = _wordCount(art.content);
      html += `<tr data-article-id="${id}">`
        + `<td class="history-title">${title}</td>`
        + `<td>${time}</td>`
        + `<td>${wc}</td>`
        + `<td class="history-actions">`
        + `<button class="btn btn-sm" onclick="viewArticle(${id})">查看</button>`
        + `<button class="btn btn-sm" onclick="continueArticle(${id})">继续编辑</button>`
        + `<button class="btn btn-sm btn-danger" onclick="deleteArticle(${id})">删除</button>`
        + `</td>`
        + '</tr>';
    });
    html += '</tbody></table>';
    container.innerHTML = html;
  } catch (e) {
    console.error('加载历史文章失败:', e);
    container.innerHTML = '<div class="dash-recent-empty">加载失败，请重试</div>';
  }
}

// ── 查看文章（含末尾 AI 标识） ──

function _ensureViewModal() {
  let modal = document.getElementById('history-view-modal');
  if (modal) return modal;
  modal = document.createElement('div');
  modal.id = 'history-view-modal';
  modal.className = 'modal-overlay';
  modal.innerHTML = `
    <div class="modal" style="max-width:720px;width:92vw;">
      <div class="modal-header">
        <div class="history-view-title" id="history-view-title"></div>
        <button class="modal-close" onclick="closeViewModal()">×</button>
      </div>
      <div class="history-view-body" id="history-view-body"></div>
      <div class="history-view-footer">
        <button class="btn btn-primary" id="history-view-open-editor" type="button">在编辑器中打开</button>
        <button class="btn btn-secondary" onclick="closeViewModal()">关闭</button>
      </div>
    </div>`;
  document.body.appendChild(modal);
  modal.addEventListener('click', function (e) {
    if (e.target === modal) closeViewModal();
  });
  return modal;
}

function closeViewModal() {
  const modal = document.getElementById('history-view-modal');
  if (modal) modal.classList.remove('show');
}

async function viewArticle(id) {
  const modal = _ensureViewModal();
  const body = document.getElementById('history-view-body');
  const titleEl = document.getElementById('history-view-title');
  titleEl.textContent = '文章详情';
  body.innerHTML = '<div class="dash-recent-empty">加载中...</div>';
  modal.classList.add('show');

  try {
    const res = await fetch('/api/collaborative/articles/' + id);
    if (!res.ok) throw new Error('文章不存在');
    const data = await res.json();
    const art = data.article;
    if (!art) throw new Error('文章不存在');

    titleEl.textContent = art.title || '无标题';
    const label = _escHtml(art.ai_label || '');
    // 内容已含 AI 标识（attach_label），此处再单独强调标识行以便醒目
    const contentHtml = _escHtml(art.content || '').replace(/\n/g, '<br>');
    body.innerHTML = `
      <div class="history-view-content">${contentHtml}</div>
      <div class="history-view-ai-label">AI 标识：${label}</div>`;
    const openBtn = document.getElementById('history-view-open-editor');
    if (openBtn) {
      openBtn.onclick = function () { continueArticle(id); };
    }
  } catch (e) {
    body.innerHTML = '<div class="dash-recent-empty">加载失败：' + _escHtml(e.message) + '</div>';
  }
}

// ── 继续编辑：新建预填充项目并跳转到工作台 ──

async function continueArticle(id) {
  try {
    const res = await fetch('/api/collaborative/articles/' + id + '/continue', {
      method: 'POST',
    });
    const data = await res.json();
    if (res.ok && data.project_id) {
      window.location.href = '/collaborative/' + data.project_id;
    } else {
      toast(data.error || '操作失败，请重试', 'error');
    }
  } catch (e) {
    toast('操作失败：' + e.message, 'error');
  }
}

// ── 删除：确认后删除并刷新列表 ──

async function deleteArticle(id) {
  if (!confirm('确定要删除这篇文章吗？此操作不可恢复。')) return;
  try {
    const res = await fetch('/api/collaborative/articles/' + id, { method: 'DELETE' });
    const data = await res.json();
    if (res.ok && data.deleted) {
      toast('文章已删除', 'success');
      loadHistoryArticles();
    } else {
      toast(data.error || '删除失败', 'error');
    }
  } catch (e) {
    toast('删除失败：' + e.message, 'error');
  }
}
