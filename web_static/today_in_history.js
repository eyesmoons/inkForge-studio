// today_in_history.js - 历史上的今天

let allEvents = [];
let currentFilter = 'all';

// 页面加载
document.addEventListener('DOMContentLoaded', () => {
  loadData();
  setupFilters();
});

// 加载数据
async function loadData() {
  const container = document.getElementById('timeline-container');
  container.innerHTML = '<div class="loading">加载中...</div>';
  
  try {
    const res = await fetch('/api/today_in_history');
    const data = await res.json();
    
    if (data.ok) {
      allEvents = data.data.events || [];
      document.getElementById('current-date').textContent = 
        `${data.data.date} ${data.data.weekday}`;
      updateStats();
      renderTimeline();
    } else {
      container.innerHTML = `<div class="empty-state">${data.error || '加载失败'}</div>`;
    }
  } catch (e) {
    container.innerHTML = '<div class="empty-state">网络错误，请稍后重试</div>';
  }
}

// 刷新数据
function refreshData() {
  loadData();
}

// 更新统计
function updateStats() {
  document.getElementById('total-events').textContent = allEvents.length;
  document.getElementById('birth-count').textContent = 
    allEvents.filter(e => e.type === '出生').length;
  document.getElementById('war-count').textContent = 
    allEvents.filter(e => e.type === '战争' || e.type === '政治').length;
  document.getElementById('tech-count').textContent = 
    allEvents.filter(e => e.type === '科技' || e.type === '文化').length;
}

// 设置筛选
function setupFilters() {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      currentFilter = btn.dataset.filter;
      renderTimeline();
    });
  });
}

// 渲染时间轴
function renderTimeline() {
  const container = document.getElementById('timeline-container');
  
  let events = allEvents;
  if (currentFilter !== 'all') {
    events = allEvents.filter(e => e.type === currentFilter);
  }
  
  if (events.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📭</div>
        <div>暂无${currentFilter === 'all' ? '' : '该类型'}历史事件</div>
      </div>
    `;
    return;
  }
  
  const html = `
    <div class="timeline">
      ${events.map(event => `
        <div class="timeline-item type-${event.type}">
          <div class="timeline-year">${event.year}年
            <span class="timeline-type">${event.type}</span>
          </div>
          <div class="timeline-title">${escapeHtml(event.title)}</div>
          ${event.desc ? `<div class="timeline-desc">${escapeHtml(event.desc)}</div>` : ''}
        </div>
      `).join('')}
    </div>
  `;
  
  container.innerHTML = html;
}

// HTML转义
function escapeHtml(text) {
  if (!text) return '';
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
