// ════════════════════════════════════════════════════════════
// 工作台 · 科技感图表（状态分布饼图、发文时段热力图、月度趋势、账号排行、关键词词云）
// 全部图表支持：入场动画 / hover 交互 / Retina 高清
// ════════════════════════════════════════════════════════════

// ── 通用：创建高清 Canvas ──
function createHiDPICanvas(container) {
  const dpr = window.devicePixelRatio || 1;
  const cssW = container.offsetWidth || 300;
  const cssH = container.offsetHeight || 200;
  const canvas = document.createElement('canvas');
  canvas.width = cssW * dpr;
  canvas.height = cssH * dpr;
  canvas.style.width = cssW + 'px';
  canvas.style.height = cssH + 'px';
  container.appendChild(canvas);
  const ctx = canvas.getContext('2d');
  ctx.scale(dpr, dpr);
  return { ctx, width: cssW, height: cssH, canvas };
}

// ── 通用：easing 函数 ──
function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }
function easeOutElastic(t) {
  if (t === 0 || t === 1) return t;
  return Math.pow(2, -10 * t) * Math.sin((t - 0.075) * (2 * Math.PI) / 0.3) + 1;
}

// ── 通用：绘制科技感 tooltip ──
function showSciTooltip(canvas, e, html) {
  const rect = canvas.getBoundingClientRect();
  const tt = document.createElement('div');
  tt.className = 'sci-tooltip';
  tt.innerHTML = html;
  document.body.appendChild(tt);
  let tx = rect.left + (e.clientX - rect.left) + 14;
  let ty = rect.top + (e.clientY - rect.top) - 8;
  if (tx + tt.offsetWidth > window.innerWidth - 10) tx = e.clientX - tt.offsetWidth - 10;
  if (ty + tt.offsetHeight > window.innerHeight - 10) ty = e.clientY - tt.offsetHeight - 10;
  if (ty < 4) ty = 4;
  tt.style.left = tx + 'px';
  tt.style.top = ty + 'px';
  return tt;
}

// ── 通用：创建 Tooltip 样式（注入一次） ──
(function injectSciTooltipCSS() {
  if (document.getElementById('sci-tooltip-css')) return;
  const s = document.createElement('style');
  s.id = 'sci-tooltip-css';
  s.textContent = `
    .sci-tooltip {
      position: fixed; z-index: 99999; pointer-events: none;
      background: rgba(15,17,23,0.94);
      backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
      border: 1px solid rgba(7,193,96,0.25);
      border-radius: 10px; padding: 10px 14px;
      color: #e8eaf0; font-size: 12px; line-height: 1.6;
      box-shadow: 0 4px 24px rgba(0,0,0,0.5), 0 0 30px rgba(7,193,96,0.08);
      animation: sciTooltipIn 0.2s ease;
    }
    @keyframes sciTooltipIn {
      from { opacity: 0; transform: translateY(4px) scale(0.96); }
      to   { opacity: 1; transform: translateY(0) scale(1); }
    }
  `;
  document.head.appendChild(s);
})();


// ════════════════════════════════════════════════════════════
// 1. 文章状态分布饼图 — 旋转入场 + hover外弹涟漪
// ════════════════════════════════════════════════════════════
function drawStatusPieChart(data) {
  const container = document.getElementById('status-pie-chart');
  if (!container) return;
  container.innerHTML = '';

  const { ctx, width, height, canvas } = createHiDPICanvas(container);
  const centerX = width / 2, centerY = height / 2 - 6;
  const radius = Math.min(width, height) * 0.26;

  if (!data || data.length === 0) {
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', width / 2, height / 2);
    return;
  }

  const total = data.reduce((s, d) => s + d.count, 0);
  const colorMap = { published: '#4CAF50', draft: '#2196F3', failed: '#F44336' };
  const glowMap = { published: 'rgba(76,175,80,0.5)', draft: 'rgba(33,150,243,0.5)', failed: 'rgba(244,67,54,0.5)' };
  const slices = [];

  let startAngle = -Math.PI / 2;
  data.forEach(item => {
    const sliceAngle = (item.count / total) * 2 * Math.PI;
    const endAngle = startAngle + sliceAngle;
    slices.push({
      startAngle, endAngle,
      label: item.label, count: item.count,
      color: colorMap[item.status] || '#999',
      glow: glowMap[item.status] || 'rgba(153,153,153,0.5)'
    });
    startAngle = endAngle;
  });

  // ── 入场旋转动画 ──
  let animProgress = 0;
  let hoveredIdx = -1;
  let tooltip = null;
  let rafId;

  function redraw() {
    ctx.clearRect(0, 0, width, height);
    const sweepEnd = -Math.PI / 2 + easeOutCubic(Math.min(animProgress, 1)) * Math.PI * 2;

    slices.forEach((s, i) => {
      const isHovered = i === hoveredIdx;
      ctx.globalAlpha = hoveredIdx === -1 ? 1 : (isHovered ? 1 : 0.5);

      // 裁剪动画进度
      let drawStart = s.startAngle;
      let drawEnd = Math.min(s.endAngle, sweepEnd);
      if (drawStart >= sweepEnd) return;

      const r = isHovered ? radius * 1.08 : radius;

      // hover 光晕
      if (isHovered) {
        ctx.save();
        ctx.shadowColor = s.glow;
        ctx.shadowBlur = 24;
      }

      ctx.beginPath();
      ctx.moveTo(centerX, centerY);
      ctx.arc(centerX, centerY, r, drawStart, drawEnd);
      ctx.closePath();

      // 渐变填充
      const midA = (drawStart + drawEnd) / 2;
      const gx = centerX + Math.cos(midA) * r;
      const gy = centerY + Math.sin(midA) * r;
      const grad = ctx.createRadialGradient(centerX, centerY, r * 0.2, gx, gy, r);
      grad.addColorStop(0, s.color + 'cc');
      grad.addColorStop(1, s.color);
      ctx.fillStyle = grad;
      ctx.fill();

      // 科技感分隔线
      ctx.strokeStyle = 'rgba(15,17,23,0.6)';
      ctx.lineWidth = 2;
      ctx.stroke();

      if (isHovered) ctx.restore();

      // 内环装饰（科技感双环）
      if (animProgress >= 1) {
        ctx.beginPath();
        ctx.arc(centerX, centerY, r * 0.52, drawStart, drawEnd);
        ctx.strokeStyle = s.color + '33';
        ctx.lineWidth = 1;
        ctx.stroke();
      }

      ctx.globalAlpha = 1;

      // 标签（动画完成后显示）
      if (animProgress >= 1 && drawEnd - drawStart > 0.15) {
        const pct = ((s.count / total) * 100).toFixed(1);
        const labelR = radius * 1.5;
        const lx = centerX + Math.cos(midA) * labelR;
        const ly = centerY + Math.sin(midA) * labelR;
        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.font = isHovered ? 'bold 13px sans-serif' : '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${pct}%`, lx, ly);
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = '11px sans-serif';
        ctx.fillText(s.label, lx, ly + 15);
      }
    });

    // 中心装饰圆环
    if (animProgress >= 1) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius * 0.45, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255,255,255,0.06)';
      ctx.lineWidth = 1;
      ctx.stroke();

      // 中心总数
      ctx.fillStyle = 'rgba(255,255,255,0.85)';
      ctx.font = 'bold 22px sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(total, centerX, centerY - 4);
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.font = '10px sans-serif';
      ctx.fillText('总计', centerX, centerY + 16);
      ctx.textBaseline = 'alphabetic';
    }

    // 图例（底部）
    if (animProgress >= 1) {
      const legendY = height - 16;
      const legendSpacing = width / (slices.length + 1);
      slices.forEach((s, i) => {
        const lx = legendSpacing * (i + 1) - 30;
        // 图例色块带圆角
        ctx.fillStyle = s.color;
        roundRect(ctx, lx, legendY, 10, 10, 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = '11px sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`${s.label} ${s.count}`, lx + 14, legendY + 9);
      });
    }
  }

  // 圆角矩形工具
  function roundRect(c, x, y, w, h, r) {
    r = Math.max(0, Math.min(r, Math.min(w, h) / 2));
    c.beginPath();
    c.moveTo(x + r, y);
    c.lineTo(x + w - r, y);
    c.quadraticCurveTo(x + w, y, x + w, y + r);
    c.lineTo(x + w, y + h - r);
    c.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    c.lineTo(x + r, y + h);
    c.quadraticCurveTo(x, y + h, x, y + h - r);
    c.lineTo(x, y + r);
    c.quadraticCurveTo(x, y, x + r, y);
    c.closePath();
  }

  // 入场动画
  const startTime = performance.now();
  function animate(now) {
    animProgress = Math.min((now - startTime) / 900, 1);
    redraw();
    if (animProgress < 1) {
      rafId = requestAnimationFrame(animate);
    }
  }
  rafId = requestAnimationFrame(animate);

  // 鼠标交互
  canvas.addEventListener('mousemove', (e) => {
    if (animProgress < 1) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    const dx = mx - centerX, dy = my - centerY;
    const dist = Math.sqrt(dx * dx + dy * dy);
    let newIdx = -1;
    if (dist <= radius * 1.1) {
      let angle = Math.atan2(dy, dx);
      if (angle < 0) angle += 2 * Math.PI;
      slices.forEach((s, i) => {
        let sa = s.startAngle, ea = s.endAngle;
        if (sa < 0) sa += 2 * Math.PI;
        if (ea < 0) ea += 2 * Math.PI;
        if (sa > ea) { if (angle >= sa || angle < ea) newIdx = i; }
        else { if (angle >= sa && angle < ea) newIdx = i; }
      });
    }
    if (newIdx !== hoveredIdx) { hoveredIdx = newIdx; redraw(); }
    if (tooltip) { tooltip.remove(); tooltip = null; }
    if (hoveredIdx !== -1) {
      const s = slices[hoveredIdx];
      tooltip = showSciTooltip(canvas, e,
        `<div style="font-weight:600;color:${s.color}">${s.label}</div>` +
        `<div style="margin-top:4px;">${s.count} 篇 · <span style="color:${s.color}">${((s.count/total)*100).toFixed(1)}%</span></div>`
      );
    }
  });
  canvas.addEventListener('mouseleave', () => {
    hoveredIdx = -1; redraw();
    if (tooltip) { tooltip.remove(); tooltip = null; }
  });
}


// ════════════════════════════════════════════════════════════
// 2. 发文时段热力图（24小时柱状图）— 入场生长 + hover光柱
// ════════════════════════════════════════════════════════════
function drawHeatmapChart(hourlyData) {
  const container = document.getElementById('heatmap-chart');
  if (!container) return;
  container.innerHTML = '';

  const { ctx, width, height, canvas } = createHiDPICanvas(container);
  const padding = { top: 16, right: 16, bottom: 30, left: 40 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  // 补全24小时
  const hourMap = {};
  (hourlyData || []).forEach(d => { hourMap[d.hour] = d.count; });
  const hours = Array.from({ length: 24 }, (_, i) => ({ hour: i, count: hourMap[i] || 0 }));
  const maxCount = Math.max(...hours.map(h => h.count), 1);

  // 柱子参数
  const spacing = chartW / 24;
  const barW = spacing * 0.7;

  let animProgress = 0;
  let hoveredIdx = -1;
  let tooltip = null;

  function drawGrid() {
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(width - padding.right, y); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(maxCount * (1 - i / 4)), padding.left - 6, y + 4);
    }
  }

  function redraw() {
    ctx.clearRect(0, 0, width, height);
    drawGrid();
    const ease = easeOutCubic(Math.min(animProgress, 1));

    hours.forEach((h, i) => {
      const x = padding.left + spacing * i + (spacing - barW) / 2;
      const fullH = (h.count / maxCount) * chartH;
      const barH = fullH * ease;
      const y = padding.top + chartH - barH;
      const isHovered = i === hoveredIdx;
      const ratio = h.count / maxCount;

      // 渐变色：从绿到橙（低→高），带科技感
      const grad = ctx.createLinearGradient(x, y, x, y + barH);
      if (ratio > 0.7) {
        grad.addColorStop(0, '#FFB74D');
        grad.addColorStop(0.5, '#FF9800');
        grad.addColorStop(1, '#E65100');
      } else if (ratio > 0.3) {
        grad.addColorStop(0, '#81C784');
        grad.addColorStop(0.5, '#66BB6A');
        grad.addColorStop(1, '#388E3C');
      } else {
        grad.addColorStop(0, 'rgba(76,175,80,0.6)');
        grad.addColorStop(1, 'rgba(76,175,80,0.2)');
      }

      if (isHovered) {
        ctx.save();
        ctx.shadowColor = ratio > 0.5 ? 'rgba(255,152,0,0.5)' : 'rgba(76,175,80,0.5)';
        ctx.shadowBlur = 16;
      }

      ctx.fillStyle = grad;
      // 圆角柱顶
      if (barH > 4) {
        const r = Math.min(3, barH / 2, barW / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + barW - r, y);
        ctx.quadraticCurveTo(x + barW, y, x + barW, y + r);
        ctx.lineTo(x + barW, y + barH);
        ctx.lineTo(x, y + barH);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
        ctx.fill();
      } else if (barH > 0) {
        ctx.fillRect(x, y, barW, barH);
      }

      if (isHovered) ctx.restore();

      // hover 时顶部光点
      if (isHovered && barH > 0) {
        ctx.beginPath();
        ctx.arc(x + barW / 2, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#fff';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x + barW / 2, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.fill();
      }

      // X轴标签
      if (i % 3 === 0) {
        ctx.fillStyle = isHovered ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.5)';
        ctx.font = isHovered ? 'bold 11px sans-serif' : '10px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`${String(i).padStart(2, '0')}:00`, x + barW / 2, height - padding.bottom + 16);
      }
    });
  }

  // 入场动画
  const startTime = performance.now();
  function animate(now) {
    animProgress = Math.min((now - startTime) / 800, 1);
    redraw();
    if (animProgress < 1) requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  // 鼠标交互
  canvas.addEventListener('mousemove', (e) => {
    if (animProgress < 1) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    let newIdx = -1;
    hours.forEach((h, i) => {
      const x = padding.left + spacing * i + (spacing - barW) / 2;
      if (mx >= x && mx <= x + barW) newIdx = i;
    });
    if (newIdx !== hoveredIdx) { hoveredIdx = newIdx; redraw(); }
    if (tooltip) { tooltip.remove(); tooltip = null; }
    if (hoveredIdx !== -1) {
      const h = hours[hoveredIdx];
      tooltip = showSciTooltip(canvas, e,
        `<div style="font-weight:600;">${String(h.hour).padStart(2, '0')}:00 - ${String(h.hour + 1).padStart(2, '0')}:00</div>` +
        `<div style="margin-top:4px;color:#4CAF50;">发文 <b>${h.count}</b> 篇</div>`
      );
    }
  });
  canvas.addEventListener('mouseleave', () => {
    hoveredIdx = -1; redraw();
    if (tooltip) { tooltip.remove(); tooltip = null; }
  });
}


// ════════════════════════════════════════════════════════════
// 3. 月度发文趋势 — 依次生长 + hover发光柱 + 趋势线动画
// ════════════════════════════════════════════════════════════
function drawMonthlyChart(monthlyData) {
  const container = document.getElementById('monthly-chart');
  if (!container) return;
  container.innerHTML = '';

  const { ctx, width, height, canvas } = createHiDPICanvas(container);
  const padding = { top: 20, right: 16, bottom: 36, left: 40 };
  const chartW = width - padding.left - padding.right;
  const chartH = height - padding.top - padding.bottom;

  if (!monthlyData || monthlyData.length === 0) {
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', width / 2, height / 2);
    return;
  }

  const maxCount = Math.max(...monthlyData.map(d => d.count), 1);
  const n = monthlyData.length;
  const barW = Math.min(chartW / n * 0.6, 50);
  const spacing = chartW / n;
  const colors = ['#4CAF50', '#66BB6A', '#81C784', '#A5D6A7', '#2196F3', '#42A5F5'];

  let animProgress = 0;
  let hoveredIdx = -1;
  let tooltip = null;

  function drawGrid() {
    ctx.strokeStyle = 'rgba(255,255,255,0.06)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = padding.top + (chartH / 4) * i;
      ctx.beginPath(); ctx.moveTo(padding.left, y); ctx.lineTo(width - padding.right, y); ctx.stroke();
      ctx.fillStyle = 'rgba(255,255,255,0.4)';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(Math.round(maxCount * (1 - i / 4)), padding.left - 6, y + 4);
    }
  }

  function redraw() {
    ctx.clearRect(0, 0, width, height);
    drawGrid();
    const ease = easeOutCubic(Math.min(animProgress, 1));

    monthlyData.forEach((d, i) => {
      const x = padding.left + spacing * i + (spacing - barW) / 2;
      const fullBarH = (d.count / maxCount) * chartH;
      const barH = fullBarH * ease;
      const y = padding.top + chartH - barH;
      const isHovered = i === hoveredIdx;

      // 逐柱延迟入场
      const delay = i * 0.08;
      const barEase = easeOutCubic(Math.max(0, Math.min((animProgress - delay) / (1 - delay), 1)));
      const animH = fullBarH * barEase;
      const animY = padding.top + chartH - animH;

      const c = colors[i % colors.length];
      const grad = ctx.createLinearGradient(x, animY, x, animY + animH);
      grad.addColorStop(0, isHovered ? '#fff' : c);
      grad.addColorStop(0.4, c);
      grad.addColorStop(1, c + '88');

      if (isHovered) {
        ctx.save();
        ctx.shadowColor = c + '66';
        ctx.shadowBlur = 20;
      }

      ctx.fillStyle = grad;
      if (animH > 4) {
        const r = Math.min(4, animH / 2, barW / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, animY);
        ctx.lineTo(x + barW - r, animY);
        ctx.quadraticCurveTo(x + barW, animY, x + barW, animY + r);
        ctx.lineTo(x + barW, animY + animH);
        ctx.lineTo(x, animY + animH);
        ctx.lineTo(x, animY + r);
        ctx.quadraticCurveTo(x, animY, x + r, animY);
        ctx.closePath();
        ctx.fill();
      } else if (animH > 0) {
        ctx.fillRect(x, animY, barW, animH);
      }

      if (isHovered) ctx.restore();

      // 数值标签
      if (d.count > 0 && barEase > 0.8) {
        ctx.fillStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.8)';
        ctx.font = isHovered ? 'bold 12px sans-serif' : '11px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(d.count, x + barW / 2, animY - 6);
      }

      // X轴月份
      ctx.fillStyle = isHovered ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.5)';
      ctx.font = '10px sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText(d.month.slice(2), x + barW / 2, height - padding.bottom + 16);
    });

    // 趋势线（延迟动画）
    if (n >= 2 && animProgress > 0.5) {
      const lineProgress = easeOutCubic(Math.min((animProgress - 0.5) / 0.5, 1));
      ctx.beginPath();
      ctx.strokeStyle = '#FF9800';
      ctx.lineWidth = 2;
      ctx.setLineDash([6, 4]);

      const drawCount = Math.ceil(n * lineProgress);
      monthlyData.slice(0, drawCount).forEach((d, i) => {
        const x = padding.left + spacing * i + spacing / 2;
        const y = padding.top + chartH - (d.count / maxCount) * chartH;
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
      });
      ctx.stroke();
      ctx.setLineDash([]);

      // 趋势线上的数据点
      monthlyData.slice(0, drawCount).forEach((d, i) => {
        const x = padding.left + spacing * i + spacing / 2;
        const y = padding.top + chartH - (d.count / maxCount) * chartH;
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.fillStyle = '#FF9800';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(x, y, 6, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,152,0,0.2)';
        ctx.fill();
      });
    }
  }

  // 入场动画
  const startTime = performance.now();
  function animate(now) {
    animProgress = Math.min((now - startTime) / 1200, 1);
    redraw();
    if (animProgress < 1) requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  // 鼠标交互
  canvas.addEventListener('mousemove', (e) => {
    if (animProgress < 1) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    let newIdx = -1;
    monthlyData.forEach((d, i) => {
      const x = padding.left + spacing * i + (spacing - barW) / 2;
      if (mx >= x - 4 && mx <= x + barW + 4) newIdx = i;
    });
    if (newIdx !== hoveredIdx) { hoveredIdx = newIdx; redraw(); }
    if (tooltip) { tooltip.remove(); tooltip = null; }
    if (hoveredIdx !== -1) {
      const d = monthlyData[hoveredIdx];
      tooltip = showSciTooltip(canvas, e,
        `<div style="font-weight:600;">${d.month}</div>` +
        `<div style="margin-top:4px;color:#4CAF50;">发文 <b>${d.count}</b> 篇</div>`
      );
    }
  });
  canvas.addEventListener('mouseleave', () => {
    hoveredIdx = -1; redraw();
    if (tooltip) { tooltip.remove(); tooltip = null; }
  });
}


// ════════════════════════════════════════════════════════════
// 4. 账号发文排行 — 条形滑入 + hover流光 + 光效
// ════════════════════════════════════════════════════════════
function drawAccountRankChart(accountData) {
  const container = document.getElementById('account-rank-chart');
  if (!container) return;
  container.innerHTML = '';

  const { ctx, width, height, canvas } = createHiDPICanvas(container);

  if (!accountData || accountData.length === 0) {
    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('暂无数据', width / 2, height / 2);
    return;
  }

  const padding = { top: 12, right: 14, bottom: 12, left: 14 };
  const chartH = height - padding.top - padding.bottom;
  const chartW = width - padding.left - padding.right;
  const n = Math.min(accountData.length, 8);
  const maxCount = Math.max(...accountData.slice(0, n).map(d => d.count), 1);
  const barH = Math.min(chartH / n * 0.6, 20);
  const rowH = chartH / n;
  const colors = ['#4CAF50', '#2196F3', '#FF9800', '#9C27B0', '#F44336', '#00BCD4', '#FF5722', '#607D8B'];

  // 名称宽度计算
  ctx.font = '12px sans-serif';
  const nameW = Math.max(...accountData.slice(0, n).map(d => {
    const name = d.account_name && d.account_name.length > 8 ? d.account_name.slice(0, 8) + '…' : (d.account_name || '未知');
    return ctx.measureText(name).width;
  }), 50);
  const rankW = 24;
  const numW = 36;
  const barAreaW = chartW - rankW - nameW - numW - 12;

  let animProgress = 0;
  let hoveredIdx = -1;
  let tooltip = null;

  function redraw() {
    ctx.clearRect(0, 0, width, height);

    accountData.slice(0, n).forEach((d, i) => {
      const y = padding.top + rowH * i + (rowH - barH) / 2;
      const isHovered = i === hoveredIdx;

      // 逐行延迟入场
      const delay = i * 0.06;
      const rowEase = easeOutCubic(Math.max(0, Math.min((animProgress - delay) / (1 - delay), 1)));

      // 排名
      const rankText = i < 3 ? ['🥇', '🥈', '🥉'][i] : `${i + 1}`;
      ctx.globalAlpha = rowEase;
      ctx.fillStyle = isHovered ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.4)';
      ctx.font = '11px sans-serif';
      ctx.textAlign = 'left';
      ctx.fillText(rankText, padding.left, y + barH / 2 + 4);

      // 条形
      const barStartX = padding.left + rankW;
      const fullBarW = barAreaW > 10 ? Math.max((d.count / maxCount) * barAreaW, 4) : 4;
      const animBarW = fullBarW * rowEase;
      const c = colors[i % colors.length];

      if (isHovered) {
        ctx.save();
        ctx.shadowColor = c + '88';
        ctx.shadowBlur = 14;
      }

      const grad = ctx.createLinearGradient(barStartX, y, barStartX + animBarW, y);
      grad.addColorStop(0, c);
      grad.addColorStop(0.7, c + 'bb');
      grad.addColorStop(1, c + '44');
      ctx.fillStyle = grad;

      if (animBarW > 4) {
        const r = Math.min(barH / 2, 4);
        ctx.beginPath();
        ctx.moveTo(barStartX, y);
        ctx.lineTo(barStartX + animBarW - r, y);
        ctx.quadraticCurveTo(barStartX + animBarW, y, barStartX + animBarW, y + r);
        ctx.lineTo(barStartX + animBarW, y + barH - r);
        ctx.quadraticCurveTo(barStartX + animBarW, y + barH, barStartX + animBarW - r, y + barH);
        ctx.lineTo(barStartX, y + barH);
        ctx.closePath();
        ctx.fill();
      } else if (animBarW > 0) {
        ctx.fillRect(barStartX, y, animBarW, barH);
      }

      if (isHovered) ctx.restore();

      // 流光效果（hover时）
      if (isHovered && animBarW > 20) {
        const shineX = barStartX + (animBarW * 0.3);
        const shineGrad = ctx.createLinearGradient(shineX - 15, y, shineX + 15, y);
        shineGrad.addColorStop(0, 'rgba(255,255,255,0)');
        shineGrad.addColorStop(0.5, 'rgba(255,255,255,0.15)');
        shineGrad.addColorStop(1, 'rgba(255,255,255,0)');
        ctx.fillStyle = shineGrad;
        ctx.fillRect(barStartX, y, animBarW, barH);
      }

      // 账号名
      const nameStartX = barStartX + animBarW + 6;
      ctx.fillStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.8)';
      ctx.font = isHovered ? 'bold 12px sans-serif' : '12px sans-serif';
      ctx.textAlign = 'left';
      const name = d.account_name && d.account_name.length > 8 ? d.account_name.slice(0, 8) + '…' : (d.account_name || '未知');
      ctx.fillText(name, nameStartX, y + barH / 2 + 4);

      // 数值
      ctx.fillStyle = isHovered ? '#fff' : 'rgba(255,255,255,0.9)';
      ctx.font = 'bold 12px sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(d.count, width - padding.right, y + barH / 2 + 4);

      ctx.globalAlpha = 1;
    });
  }

  // 入场动画
  const startTime = performance.now();
  function animate(now) {
    animProgress = Math.min((now - startTime) / 800, 1);
    redraw();
    if (animProgress < 1) requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);

  // 鼠标交互
  canvas.addEventListener('mousemove', (e) => {
    if (animProgress < 1) return;
    const rect = canvas.getBoundingClientRect();
    const my = e.clientY - rect.top;
    let newIdx = -1;
    accountData.slice(0, n).forEach((d, i) => {
      const y = padding.top + rowH * i;
      if (my >= y && my <= y + rowH) newIdx = i;
    });
    if (newIdx !== hoveredIdx) { hoveredIdx = newIdx; redraw(); }
    if (tooltip) { tooltip.remove(); tooltip = null; }
    if (hoveredIdx !== -1) {
      const d = accountData[hoveredIdx];
      const c = colors[hoveredIdx % colors.length];
      tooltip = showSciTooltip(canvas, e,
        `<div style="font-weight:600;color:${c}">${d.account_name || '未知'}</div>` +
        `<div style="margin-top:4px;">发文 <b>${d.count}</b> 篇</div>`
      );
    }
  });
  canvas.addEventListener('mouseleave', () => {
    hoveredIdx = -1; redraw();
    if (tooltip) { tooltip.remove(); tooltip = null; }
  });
}


// ════════════════════════════════════════════════════════════
// 5. 标题关键词词云 — 浮动呼吸 + hover发光放大
// ════════════════════════════════════════════════════════════
function drawKeywordCloud(data) {
  const container = document.getElementById('keyword-cloud-chart');
  if (!container) return;
  container.innerHTML = '';

  if (!data || data.length === 0) {
    container.innerHTML = '<div style="text-align:center;padding:40px 0;color:var(--text2);font-size:14px;">暂无数据</div>';
    return;
  }

  const { ctx, width, height, canvas } = createHiDPICanvas(container);
  const maxCount = Math.max(...data.map(d => d.count), 1);
  const minCount = Math.min(...data.map(d => d.count), 0);
  const range = maxCount - minCount || 1;

  // 螺旋布局放置词汇
  const placed = [];
  const colors = ['#4CAF50', '#66BB6A', '#81C784', '#2196F3', '#42A5F5',
                  '#64B5F6', '#FF9800', '#FFA726', '#FFB74D', '#E0E0E0',
                  '#BDBDBD', '#9E9E9E'];

  // 每个词汇的位置和大小
  const wordItems = [];

  data.forEach((item, idx) => {
    const ratio = (item.count - minCount) / range;
    const fontSize = Math.round(14 + ratio * 22);
    ctx.font = `${ratio > 0.6 ? 'bold' : 'normal'} ${fontSize}px sans-serif`;
    const textW = ctx.measureText(item.word).width;
    const textH = fontSize * 1.2;

    let cx = width / 2, cy = height / 2;
    let placed_ok = false;
    for (let t = 0; t < 500 && !placed_ok; t++) {
      const r = 2 + t * 1.5;
      const angle = t * 0.7;
      const px = cx + r * Math.cos(angle) - textW / 2;
      const py = cy + r * Math.sin(angle) * 0.6 - textH / 2;

      if (px < 4 || px + textW > width - 4 || py < 4 || py + textH > height - 4) continue;

      let collision = false;
      for (const p of placed) {
        if (px < p.x + p.w + 6 && px + textW + 6 > p.x && py < p.y + p.h + 4 && py + textH + 4 > p.y) {
          collision = true; break;
        }
      }
      if (!collision) {
        placed.push({ x: px, y: py, w: textW, h: textH });
        wordItems.push({
          x: px, y: py, w: textW, h: textH,
          word: item.word, count: item.count,
          fontSize, bold: ratio > 0.6,
          color: colors[idx % colors.length],
          ratio,
          floatOffset: Math.random() * Math.PI * 2 // 随机浮动相位
        });
        placed_ok = true;
      }
    }
  });

  // 动画状态
  let animProgress = 0;
  let hoveredIdx = -1;
  let tooltip = null;
  let floatTime = 0;
  let rafId;

  function redraw(timestamp) {
    ctx.clearRect(0, 0, width, height);
    floatTime = (timestamp || 0) / 1000;

    const alpha = Math.min(animProgress, 1);

    wordItems.forEach((item, i) => {
      const isHovered = i === hoveredIdx;

      // 浮动微动（±2px）
      const floatY = Math.sin(floatTime * 0.8 + item.floatOffset) * 2;
      const floatX = Math.cos(floatTime * 0.5 + item.floatOffset) * 1;

      const drawX = item.x + floatX;
      const drawY = item.y + floatY;
      const drawSize = isHovered ? item.fontSize * 1.25 : item.fontSize;

      ctx.globalAlpha = alpha * (isHovered ? 1 : (0.7 + item.ratio * 0.3));

      // hover 发光
      if (isHovered) {
        ctx.save();
        ctx.shadowColor = item.color + '88';
        ctx.shadowBlur = 16;
      }

      ctx.fillStyle = isHovered ? '#fff' : item.color;
      ctx.font = `${(isHovered || item.bold) ? 'bold' : 'normal'} ${drawSize}px sans-serif`;
      ctx.textAlign = 'left';
      ctx.fillText(item.word, drawX, drawY + drawSize);

      if (isHovered) ctx.restore();

      ctx.globalAlpha = 1;
    });

    // 持续浮动
    rafId = requestAnimationFrame(redraw);
  }

  // 入场动画
  const startTime = performance.now();
  function animateIn(now) {
    animProgress = Math.min((now - startTime) / 600, 1);
    redraw(now);
    if (animProgress < 1) {
      // cancelAnimationFrame 由 redraw 的 rafId 接管
    }
  }
  requestAnimationFrame(animateIn);

  // 鼠标交互
  canvas.addEventListener('mousemove', (e) => {
    if (animProgress < 1) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left, my = e.clientY - rect.top;
    let newIdx = -1;
    wordItems.forEach((item, i) => {
      if (mx >= item.x && mx <= item.x + item.w &&
          my >= item.y && my <= item.y + item.h) {
        newIdx = i;
      }
    });
    if (newIdx !== hoveredIdx) { hoveredIdx = newIdx; }
    if (tooltip) { tooltip.remove(); tooltip = null; }
    if (hoveredIdx !== -1) {
      const item = wordItems[hoveredIdx];
      tooltip = showSciTooltip(canvas, e,
        `<div style="font-weight:600;color:${item.color}">${item.word}</div>` +
        `<div style="margin-top:4px;">出现 <b>${item.count}</b> 次</div>`
      );
    }
  });
  canvas.addEventListener('mouseleave', () => {
    hoveredIdx = -1;
    if (tooltip) { tooltip.remove(); tooltip = null; }
  });
}
