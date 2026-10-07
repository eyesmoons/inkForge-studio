/**
 * document_rewrite.js — 文档改写前端逻辑
 *
 * 状态机：idle → file_selected → parsing → preview → rewriting → done
 */

const DR = {
  state: 'idle',
  currentFile: null,
  parsedContent: '',
};

// ── 初始化 ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // 使用 common.js 的 loadAccounts（如果可用），否则使用本地版本
  if (typeof window.loadAccounts === 'function') {
    window.loadAccounts();
  }
  setupDropZone();
});

// ── 拖拽 & 文件选择 ──────────────────────────────────────
function setupDropZone() {
  const dz = document.getElementById('dr-drop-zone');
  const input = document.getElementById('dr-file-input');
  if (!dz || !input) return;

  dz.addEventListener('click', () => input.click());

  dz.addEventListener('dragover', (e) => {
    e.preventDefault();
    dz.classList.add('dragover');
  });

  dz.addEventListener('dragleave', () => dz.classList.remove('dragover'));

  dz.addEventListener('drop', (e) => {
    e.preventDefault();
    dz.classList.remove('dragover');
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      onFileSelected(e.dataTransfer.files[0]);
    }
  });

  input.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
      onFileSelected(e.target.files[0]);
    }
  });
}

function onFileSelected(file) {
  const allowed = ['.docx', '.pdf', '.md', '.txt'];
  const ext = '.' + file.name.split('.').pop().toLowerCase();
  if (!allowed.includes(ext)) {
    toast('不支持的文件格式，请使用 .docx/.pdf/.md/.txt', 'error');
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    toast('文件大小不能超过 10MB', 'error');
    return;
  }
  DR.currentFile = file;
  DR.state = 'file_selected';
  document.getElementById('dr-filename').textContent = file.name + ' (' + formatSize(file.size) + ')';
  document.getElementById('dr-file-info').classList.remove('dr-hidden');
  updateUI();
}

function resetUpload() {
  DR.currentFile = null;
  DR.parsedContent = '';
  DR.state = 'idle';
  document.getElementById('dr-file-input').value = '';
  document.getElementById('dr-file-info').classList.add('dr-hidden');
  document.getElementById('dr-preview-textarea').value = '';
  document.getElementById('dr-preview-section').classList.add('dr-hidden');
  document.getElementById('dr-log-section').classList.add('dr-hidden');
  updateUI();
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// ── 解析文档 ──────────────────────────────────────────────
async function parseDocument() {
  if (!DR.currentFile) return;
  DR.state = 'parsing';
  updateUI();

  const formData = new FormData();
  formData.append('file', DR.currentFile);

  try {
    const resp = await fetch('/api/document/parse', {
      method: 'POST',
      body: formData,
    });
    const data = await resp.json();
    if (data.ok) {
      DR.parsedContent = data.content;
      DR.state = 'preview';
      var ta = document.getElementById('dr-preview-textarea');
      ta.value = data.content;
      document.getElementById('dr-preview-section').classList.remove('dr-hidden');
      toast('解析完成，请确认内容后开始改写', 'success');
    } else {
      toast(data.error || '解析失败', 'error');
      DR.state = 'file_selected';
    }
  } catch (e) {
    toast('网络错误', 'error');
    DR.state = 'file_selected';
  }
  updateUI();
}

// ── 结尾状态实时更新 ──────────────────────────────────────
function updateEndingStatus() {
  var statusEl = document.getElementById('dr-ending-status');
  var noEnding = document.getElementById('dr-no-ending').checked;
  var ending = document.getElementById('dr-ending').value.trim();
  if (!statusEl) return;
  if (noEnding) {
    statusEl.textContent = '✓ 文章将自然结束，不加任何结尾词';
    statusEl.style.color = 'var(--success)';
  } else if (ending) {
    statusEl.textContent = '✓ 结尾将使用：' + ending;
    statusEl.style.color = 'var(--accent)';
  } else {
    statusEl.textContent = 'AI 将自动生成结尾';
    statusEl.style.color = 'var(--text2)';
  }
}
  console.log('[DEBUG] startRewrite called');
  var content = document.getElementById('dr-preview-textarea').value.trim();
  if (!content) {
    toast('内容为空，请先上传文档或输入文字', 'error');
    return;
  }

  var accountId = document.getElementById('account-selector').value;
  console.log('[DEBUG] accountId:', accountId);
  if (!accountId) {
    toast('请选择账号', 'error');
    return;
  }

  var taskId = uuid();
  var style = document.getElementById('dr-style').value;
  var wordCount = parseInt(document.getElementById('dr-wordcount').value, 10);
  var ending = document.getElementById('dr-ending').value.trim();
  var noEnding = document.getElementById('dr-no-ending').checked;
  console.log('[DEBUG] taskId:', taskId, 'style:', style, 'wordCount:', wordCount, 'ending:', ending);

  DR.state = 'rewriting';
  updateUI();

  var logEl = document.getElementById('dr-log');
  logEl.innerHTML = '<div class="log-line log-info">🚀 正在启动改写...</div>';
  document.getElementById('dr-log-section').classList.remove('dr-hidden');

  try {
    console.log('[DEBUG] fetching /api/document/rewrite');
    var resp = await fetch('/api/document/rewrite', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        content: content,
        style: style,
        word_count: wordCount,
        ending_text: ending || '',
        no_ending: no_ending,
        task_id: taskId,
        account_id: accountId,
      }),
    });
    console.log('[DEBUG] response status:', resp.status);
    var data = await resp.json();
    console.log('[DEBUG] response data:', data);
    if (!data.ok) {
      toast(data.error || '启动改写失败', 'error');
      DR.state = 'preview';
      updateUI();
      return;
    }

    subscribeSSE(taskId, logEl, function(result) {
      console.log('[DEBUG] SSE result:', result);
      if (result.md_content) {
        DR.parsedContent = result.md_content;
        DR.state = 'done';
        updateUI();
        document.getElementById('dr-result-textarea').value = result.md_content;
        document.getElementById('dr-result-section').classList.remove('dr-hidden');
        toast('文章生成完成！可预览或复制使用', 'success');
      }
    }, function() {
      if (DR.state === 'rewriting') {
        DR.state = 'preview';
        updateUI();
      }
    });
  } catch (e) {
    console.error('[ERROR] startRewrite failed:', e);
    toast('网络错误：' + e.message, 'error');
    DR.state = 'preview';
    updateUI();
  }
}

// ── UI 状态更新 ──────────────────────────────────────────
function updateUI() {
  var steps = document.querySelectorAll('.dr-step');
  var stepMap = { 'idle': 0, 'file_selected': 0, 'parsing': 0, 'preview': 1, 'rewriting': 2, 'done': 3 };
  var activeIdx = stepMap[DR.state] !== undefined ? stepMap[DR.state] : 0;
  steps.forEach(function(s, i) {
    s.classList.toggle('active', i === activeIdx);
  });
}
