// 智能体页面交互逻辑

// 页面初始化
document.addEventListener('DOMContentLoaded', function() {
  // 高亮当前导航项
  const currentPage = window.location.pathname;
  document.querySelectorAll(".nav-item").forEach(item => {
    if (item.getAttribute("href") === currentPage) {
      item.classList.add("active");
    } else {
      item.classList.remove("active");
    }
  });

  loadAccounts();
});

// 生成文章
async function generateArticle() {
  const url = document.getElementById('agent-url').value.trim();
  const prompt = document.getElementById('agent-prompt').value.trim();
  const accountId = document.getElementById('account-selector').value;

  // 前端校验
  if (!url) {
    toast('请输入文章链接', 'error');
    return;
  }
  if (!accountId) {
    toast('请选择账号', 'error');
    return;
  }

  const btn = document.getElementById('agent-generate-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 生成中，请稍候...';
  setStatus('正在生成...', 'dot-yellow');

  // 显示进度区
  const logCard = document.getElementById('agent-log-card');
  const logEl = document.getElementById('agent-log');
  logCard.style.display = 'block';
  logEl.innerHTML = '';
  document.getElementById('agent-result-card').style.display = 'none';
  document.getElementById('agent-push-result').style.display = 'none';

  try {
    const res = await fetch('/api/agent/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url, account_id: accountId, prompt }),
    });
    const data = await res.json();

    if (res.status === 401) {
      toast('请先登录', 'error');
      setTimeout(() => { window.location.href = '/login.html'; }, 1000);
      return;
    }
    if (res.status === 400) {
      toast(data.error || '参数错误', 'error');
      return;
    }
    if (res.status === 502 || res.status === 504) {
      toast(data.error || '生成失败，请重试', 'error');
      return;
    }
    if (!data.title && !data.content) {
      toast('生成失败：返回结果为空', 'error');
      return;
    }

    // 展示结果
    document.getElementById('agent-result-title').value = data.title || '';
    document.getElementById('agent-result-content').value = data.content || '';
    document.getElementById('agent-result-card').style.display = 'block';
    toast('文章生成成功！', 'success');
    setStatus('生成完成', 'dot-green');
  } catch (err) {
    toast('生成失败：' + err.message, 'error');
    setStatus('生成失败', 'dot-red');
  } finally {
    btn.disabled = false;
    btn.textContent = '✨ 生成文章';
    logCard.style.display = 'none';
  }
}

// 推送到草稿箱
async function pushToDraft() {
  const title = document.getElementById('agent-result-title').value.trim();
  const content = document.getElementById('agent-result-content').value.trim();
  const accountId = document.getElementById('account-selector').value;

  if (!title) {
    toast('标题不能为空', 'error');
    return;
  }
  if (!content) {
    toast('正文不能为空', 'error');
    return;
  }
  if (!accountId) {
    toast('请选择账号', 'error');
    return;
  }

  const btn = document.getElementById('agent-push-btn');
  btn.disabled = true;
  btn.textContent = '⏳ 推送中...';
  setStatus('推送中...', 'dot-yellow');

  try {
    const res = await fetch('/api/agent/push_draft', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ title, content, account_id: accountId }),
    });
    const data = await res.json();

    const resultCard = document.getElementById('agent-push-result');
    const msgEl = document.getElementById('agent-push-msg');
    resultCard.style.display = 'block';

    if (res.status === 401) {
      toast('请先登录', 'error');
      msgEl.textContent = '未登录，请重新登录';
      return;
    }
    if (res.status === 400) {
      toast(data.error || '参数错误', 'error');
      msgEl.textContent = data.error || '参数错误';
      return;
    }
    if (res.status === 500) {
      toast('推送失败：' + (data.error || '微信 API 错误'), 'error');
      msgEl.textContent = '推送失败：' + (data.error || '微信 API 错误') + '。内容已保留，可修改后重试。';
      return;
    }
    if (!data.media_id) {
      toast('推送失败：未返回 media_id', 'error');
      return;
    }

    msgEl.innerHTML = `✅ 草稿创建成功！media_id：<code>${data.media_id}</code><br>请登录公众号后台审核后发布。`;
    toast('已推送到草稿箱！', 'success');
    setStatus('推送成功', 'dot-green');
  } catch (err) {
    toast('推送失败：' + err.message, 'error');
    setStatus('推送失败', 'dot-red');
  } finally {
    btn.disabled = false;
    btn.textContent = '📤 推送到草稿箱';
  }
}