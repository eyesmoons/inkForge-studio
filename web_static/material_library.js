/**
 * material_library.js — 素材库前端逻辑
 */

// ── 状态 ──────────────────────────────────────────────────
let currentTag = "";
let currentKeyword = "";
let currentGroupId = ""; // "" = 全部, "0" = 未分组, 数字 = 指定分组
let currentPage = 1;
const pageSize = 20;
let editingId = null;
let searchTimer = null;
let groups = [];
let editingGroupId = null; // 分组编辑状态
let movingMaterialId = null; // 正在移动的素材ID
let selectedMoveGroup = ""; // 移动目标分组
let uploadFile = null; // 上传文件

// ── 初始化 ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  console.log("[Material Library] DOMContentLoaded fired");
  loadGroups();
  loadTags();
  loadMaterials();
  setupDragDrop();
  initCardMenuClose();
  
  // 绑定新建分组按钮
  const newGroupBtn = document.getElementById("btn-new-group");
  console.log("[Material Library] btn-new-group element:", newGroupBtn);
  if (newGroupBtn) {
    newGroupBtn.addEventListener("click", (e) => {
      console.log("[Material Library] New group button clicked");
      e.stopPropagation();
      openGroupModal();
    });
    console.log("[Material Library] Event listener attached to btn-new-group");
  }
});

// ── 拖拽上传 ──────────────────────────────────────────────────
function setupDragDrop() {
  const zone = document.getElementById("upload-drop-zone");
  if (!zone) return;

  ["dragenter", "dragover"].forEach((evt) => {
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.add("dragover");
    });
  });

  ["dragleave", "drop"].forEach((evt) => {
    zone.addEventListener(evt, (e) => {
      e.preventDefault();
      zone.classList.remove("dragover");
    });
  });

  zone.addEventListener("drop", (e) => {
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleUploadFile(files[0]);
    }
  });
}

// ════════════════════════════════════════════════════════════
// 分组管理
// ════════════════════════════════════════════════════════════

async function loadGroups() {
  try {
    const resp = await fetch("/api/material_groups");
    const data = await resp.json();
    if (!data.ok) return;

    groups = data.data || [];
    renderGroups();
  } catch (e) {
    console.error("加载分组失败:", e);
  }
}

function renderGroups() {
  const list = document.getElementById("group-list");
  // 保留 "全部素材" 和 "未分组"
  list.innerHTML = `
    <div class="group-item ${currentGroupId === "" ? "active" : ""}" data-group-id="" onclick="filterByGroup(this)">
      <span class="group-icon">📁</span>
      <span class="group-name">全部素材</span>
    </div>
    <div class="group-item ${currentGroupId === "0" ? "active" : ""}" data-group-id="0" onclick="filterByGroup(this)">
      <span class="group-icon">📄</span>
      <span class="group-name">未分组</span>
    </div>
  `;

  groups.forEach((g) => {
    const isActive = String(currentGroupId) === String(g.id);
    const div = document.createElement("div");
    div.className = `group-item ${isActive ? "active" : ""}`;
    div.dataset.groupId = g.id;
    div.onclick = () => filterByGroup(div);
    div.innerHTML = `
      <span class="group-icon">📂</span>
      <span class="group-name">${escapeHtml(g.name)}</span>
      <span class="group-count">${g.item_count || 0}</span>
      <div class="group-item-actions">
        <button class="group-action-btn" onclick="event.stopPropagation();editGroup(${g.id},'${escapeJs(g.name)}')" title="重命名">✏️</button>
        <button class="group-action-btn" onclick="event.stopPropagation();deleteGroup(${g.id},'${escapeJs(g.name)}')" title="删除">🗑️</button>
      </div>
    `;
    list.appendChild(div);
  });

  // 同步更新编辑弹窗和上传弹窗中的分组下拉
  updateGroupSelects();
}

function updateGroupSelects() {
  const options = '<option value="">未分组</option>' +
    groups.map((g) => `<option value="${g.id}">${escapeHtml(g.name)}</option>`).join("");

  const editGroup = document.getElementById("edit-group");
  const uploadGroup = document.getElementById("upload-group");
  const moveGroupList = document.getElementById("move-group-list");

  if (editGroup) editGroup.innerHTML = options;
  if (uploadGroup) uploadGroup.innerHTML = options;

  if (moveGroupList) {
    moveGroupList.innerHTML = `
      <div class="move-group-item ${selectedMoveGroup === "" ? "selected" : ""}" data-group-id="" onclick="selectMoveGroup(this)">
        <span>📄</span> 未分组
      </div>
    ` + groups.map((g) => `
      <div class="move-group-item ${String(selectedMoveGroup) === String(g.id) ? "selected" : ""}" data-group-id="${g.id}" onclick="selectMoveGroup(this)">
        <span>📂</span> ${escapeHtml(g.name)}
      </div>
    `).join("");
  }
}

function filterByGroup(el) {
  currentGroupId = el.dataset.groupId;
  document.querySelectorAll(".group-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.groupId === currentGroupId);
  });
  loadMaterials();
}

function openGroupModal(existingId, existingName) {
  console.log("[Material Library] openGroupModal called", { existingId, existingName });
  editingGroupId = existingId || null;
  const nameInput = document.getElementById("group-name");
  const titleEl = document.getElementById("group-modal-title");
  const saveBtn = document.getElementById("group-save-btn");
  const modal = document.getElementById("group-modal");
  
  console.log("[Material Library] Elements:", { nameInput, titleEl, saveBtn, modal });
  
  if (nameInput) nameInput.value = existingName || "";
  if (titleEl) titleEl.textContent = existingId ? "重命名分组" : "新建分组";
  if (saveBtn) saveBtn.textContent = existingId ? "保存" : "创建";
  if (modal) {
    modal.classList.add("show");
    modal.style.display = "flex";
    console.log("[Material Library] Modal display set to flex");
  } else {
    console.error("[Material Library] Modal element not found!");
  }
}

function closeGroupModal() {
  editingGroupId = null;
  const modal = document.getElementById("group-modal");
  modal.classList.remove("show");
  modal.style.display = "none";
}

async function saveGroup() {
  const name = document.getElementById("group-name").value.trim();
  if (!name) {
    showToast("分组名称不能为空", "error");
    return;
  }

  try {
    let resp;
    if (editingGroupId) {
      resp = await fetch(`/api/material_groups/${editingGroupId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
    } else {
      resp = await fetch("/api/material_groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      });
    }
    const data = await resp.json();

    if (data.ok) {
      showToast(editingGroupId ? "分组已更新" : "分组已创建", "success");
      closeGroupModal();
      loadGroups();
    } else {
      showToast(data.error || "操作失败", "error");
    }
  } catch (e) {
    showToast("操作失败", "error");
  }
}

function editGroup(id, name) {
  openGroupModal(id, name);
}

async function deleteGroup(id, name) {
  if (!confirm(`确定删除分组「${name}」？\n分组内的素材将移到"未分组"。`)) return;

  try {
    const resp = await fetch(`/api/material_groups/${id}?move=true`, {
      method: "DELETE",
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("分组已删除", "success");
      // 如果当前正在查看这个分组，切回全部
      if (String(currentGroupId) === String(id)) {
        currentGroupId = "";
      }
      loadGroups();
      loadMaterials();
    } else {
      showToast(data.error || "删除失败", "error");
    }
  } catch (e) {
    showToast("删除失败", "error");
  }
}

// ════════════════════════════════════════════════════════════
// 移动到分组
// ════════════════════════════════════════════════════════════

function openMoveModal(materialId) {
  movingMaterialId = materialId;
  selectedMoveGroup = "";
  updateGroupSelects();
  const modal = document.getElementById("move-modal");
  modal.classList.add("show");
  modal.style.display = "flex";
}

function closeMoveModal() {
  movingMaterialId = null;
  const modal = document.getElementById("move-modal");
  modal.classList.remove("show");
  modal.style.display = "none";
}

function selectMoveGroup(el) {
  selectedMoveGroup = el.dataset.groupId;
  document.querySelectorAll(".move-group-item").forEach((item) => {
    item.classList.toggle("selected", item.dataset.groupId === selectedMoveGroup);
  });
}

async function doMove() {
  if (!movingMaterialId) return;

  try {
    const resp = await fetch(`/api/material_library/${movingMaterialId}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ group_id: selectedMoveGroup || null }),
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("已移动", "success");
      closeMoveModal();
      loadMaterials();
      loadGroups();
    } else {
      showToast(data.error || "移动失败", "error");
    }
  } catch (e) {
    showToast("移动失败", "error");
  }
}

// ════════════════════════════════════════════════════════════
// 上传图片
// ════════════════════════════════════════════════════════════

function openUploadModal() {
  uploadFile = null;
  document.getElementById("upload-file").value = "";
  document.getElementById("upload-title").value = "";
  document.getElementById("upload-tags").value = "";
  document.getElementById("upload-notes").value = "";
  document.getElementById("upload-preview-wrap").style.display = "none";
  document.getElementById("upload-drop-zone").style.display = "";
  document.getElementById("upload-btn").disabled = false;
  updateGroupSelects();
  const modal = document.getElementById("upload-modal");
  modal.classList.add("show");
  modal.style.display = "flex";
}

function closeUploadModal() {
  const modal = document.getElementById("upload-modal");
  modal.classList.remove("show");
  modal.style.display = "none";
}

function onFileSelected(input) {
  if (input.files && input.files[0]) {
    handleUploadFile(input.files[0]);
  }
}

function handleUploadFile(file) {
  if (!file.type.startsWith("image/")) {
    showToast("请选择图片文件", "error");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast("文件大小不能超过 10MB", "error");
    return;
  }

  uploadFile = file;

  // 预览
  const reader = new FileReader();
  reader.onload = (e) => {
    document.getElementById("upload-preview").src = e.target.result;
    document.getElementById("upload-preview-wrap").style.display = "";
    document.getElementById("upload-drop-zone").style.display = "none";
  };
  reader.readAsDataURL(file);

  // 自动填充标题
  if (!document.getElementById("upload-title").value) {
    document.getElementById("upload-title").value = file.name.replace(/\.[^.]+$/, "");
  }
}

function clearUploadFile() {
  uploadFile = null;
  document.getElementById("upload-file").value = "";
  document.getElementById("upload-preview-wrap").style.display = "none";
  document.getElementById("upload-drop-zone").style.display = "";
}

async function doUpload() {
  if (!uploadFile) {
    showToast("请先选择图片", "error");
    return;
  }

  const btn = document.getElementById("upload-btn");
  btn.disabled = true;
  btn.textContent = "上传中...";

  try {
    const formData = new FormData();
    formData.append("file", uploadFile);
    formData.append("title", document.getElementById("upload-title").value.trim());
    formData.append("tags", document.getElementById("upload-tags").value.trim());
    formData.append("group_id", document.getElementById("upload-group").value || "");
    formData.append("notes", document.getElementById("upload-notes").value.trim());

    const resp = await fetch("/api/material_library/upload", {
      method: "POST",
      body: formData,
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("上传成功", "success");
      closeUploadModal();
      loadMaterials();
      loadTags();
      loadGroups();
    } else {
      showToast(data.error || "上传失败", "error");
    }
  } catch (e) {
    showToast("上传失败", "error");
  } finally {
    btn.disabled = false;
    btn.textContent = "上传";
  }
}

// ════════════════════════════════════════════════════════════
// 标签 & 素材列表
// ════════════════════════════════════════════════════════════

async function loadTags() {
  try {
    const resp = await fetch("/api/material_library/tags");
    const data = await resp.json();

    if (!data.ok) return;

    const container = document.getElementById("filter-tags");
    // 保留"全部"按钮
    container.innerHTML = '<button class="filter-tag active" data-tag="" onclick="filterByTag(this)">全部</button>';

    data.tags.forEach((tag) => {
      const btn = document.createElement("button");
      btn.className = "filter-tag";
      btn.dataset.tag = tag;
      btn.textContent = tag;
      btn.onclick = () => filterByTag(btn);
      container.appendChild(btn);
    });
  } catch (e) {
    console.error("加载标签失败:", e);
  }
}

async function loadMaterials(reset = true) {
  if (reset) {
    currentPage = 1;
  }

  try {
    const params = new URLSearchParams({
      page: currentPage,
      page_size: pageSize,
    });
    if (currentTag) params.append("tag", currentTag);
    if (currentKeyword) params.append("keyword", currentKeyword);
    // 分组筛选
    if (currentGroupId !== "") {
      params.append("group_id", currentGroupId);
    }

    const resp = await fetch(`/api/material_library?${params}`);
    const data = await resp.json();

    const grid = document.getElementById("material-grid");
    const empty = document.getElementById("material-empty");
    const countEl = document.getElementById("material-count");
    const loadMoreBtn = document.getElementById("load-more");

    if (!data.ok || !data.data || data.data.length === 0) {
      if (reset) {
        grid.innerHTML = "";
        empty.style.display = "";
      }
      loadMoreBtn.style.display = "none";
      countEl.textContent = data.total || 0;
      return;
    }

    empty.style.display = "none";
    countEl.textContent = data.total;

    if (reset) {
      grid.innerHTML = "";
    }

    data.data.forEach((item) => {
      grid.appendChild(createMaterialCard(item));
    });

    // 是否还有更多
    const loaded = currentPage * pageSize;
    loadMoreBtn.style.display = loaded < data.total ? "" : "none";
  } catch (e) {
    console.error("加载素材失败:", e);
  }
}

// ── 创建素材卡片 ──────────────────────────────────────────
function createMaterialCard(item) {
  const card = document.createElement("div");
  card.className = "material-card";
  card.dataset.id = item.id;

  const sourceLabels = { cover: "封面", upload: "上传", other: "其他" };
  const sourceLabel = sourceLabels[item.source_type] || item.source_type;

  // 标签
  let tagsHtml = "";
  if (item.tags) {
    const tags = item.tags.split(",").filter((t) => t.trim());
    tagsHtml = tags
      .map((t) => `<span class="material-card-tag">${escapeHtml(t.trim())}</span>`)
      .join("");
  }

  // 分组标记
  const groupHtml = item.group_name
    ? `<span class="material-card-group">${escapeHtml(item.group_name)}</span>`
    : "";

  // 图片缺失提示
  const missingHtml = item.image_missing
    ? '<span class="material-card-missing">文件缺失</span>'
    : "";

  card.innerHTML = `
    <div class="material-card-img-wrap">
      <img class="material-card-img" src="${item.image_url}?t=${Date.now()}" alt="${escapeHtml(item.title || "素材")}" loading="lazy">
      <div class="material-card-actions">
        <button class="material-card-more-btn" data-action="toggle-menu" title="更多操作">⋮</button>
        <div class="material-card-menu" id="card-menu-${item.id}">
          <div class="card-menu-item" data-action="preview">
            <span>👁️</span> 预览
          </div>
          <div class="card-menu-item" data-action="download">
            <span>⬇️</span> 下载
          </div>
          <div class="card-menu-item" data-action="move">
            <span>📂</span> 移动
          </div>
          <div class="card-menu-item" data-action="edit">
            <span>✏️</span> 编辑
          </div>
          <div class="card-menu-divider"></div>
          <div class="card-menu-item card-menu-item-danger" data-action="delete">
            <span>🗑️</span> 删除
          </div>
        </div>
      </div>
      ${missingHtml}
    </div>
    <div class="material-card-info">
      <div class="material-card-title">${escapeHtml(item.title || "未命名素材")}</div>
      ${tagsHtml ? `<div class="material-card-tags">${tagsHtml}</div>` : ""}
      <div class="material-card-meta">
        <div style="display:flex;gap:4px;align-items:center;">
          <span class="material-card-source">${sourceLabel}</span>
          ${groupHtml}
        </div>
        <span>${item.created_at || ""}</span>
      </div>
    </div>
  `;

  // 绑定卡片内的事件
  const moreBtn = card.querySelector('[data-action="toggle-menu"]');
  const menu = card.querySelector('.material-card-menu');
  
  moreBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleCardMenu(item.id, moreBtn);
  });

  // 菜单项点击事件
  menu.querySelectorAll('.card-menu-item').forEach(menuItem => {
    menuItem.addEventListener('click', (e) => {
      e.stopPropagation();
      const action = menuItem.dataset.action;
      hideCardMenu(item.id);
      
      switch(action) {
        case 'preview': previewMaterial(item.id); break;
        case 'download': downloadMaterial(item.image_url, item.filename); break;
        case 'move': openMoveModal(item.id); break;
        case 'edit': openEditModal(item.id); break;
        case 'delete': deleteMaterial(item.id); break;
      }
    });
  });

  // 点击卡片预览
  card.addEventListener('click', () => previewMaterial(item.id));
  return card;
}

// ── 卡片下拉菜单 ──────────────────────────────────────────
function toggleCardMenu(materialId, btn) {
  const menu = document.getElementById(`card-menu-${materialId}`);
  if (!menu) return;

  // 关闭其他已打开的菜单
  document.querySelectorAll('.material-card-menu.active').forEach(m => {
    if (m !== menu) m.classList.remove('active');
  });

  menu.classList.toggle('active');
}

function hideCardMenu(materialId) {
  const menu = document.getElementById(`card-menu-${materialId}`);
  if (menu) menu.classList.remove('active');
}

// 点击页面其他地方关闭菜单（在DOM加载后绑定）
function initCardMenuClose() {
  document.addEventListener('click', (e) => {
    if (!e.target.closest('.material-card-actions')) {
      document.querySelectorAll('.material-card-menu.active').forEach(m => {
        m.classList.remove('active');
      });
    }
  });
}

// ── 筛选 ──────────────────────────────────────────────────
function filterByTag(btn) {
  currentTag = btn.dataset.tag;
  document.querySelectorAll(".filter-tag").forEach((el) => {
    el.classList.toggle("active", el.dataset.tag === currentTag);
  });
  loadMaterials();
}

function onSearchInput() {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentKeyword = document.getElementById("search-keyword").value.trim();
    loadMaterials();
  }, 300);
}

// ── 加载更多 ──────────────────────────────────────────────────
function loadMore() {
  currentPage++;
  loadMaterials(false);
}

// ── 预览素材 ──────────────────────────────────────────────────
function previewMaterial(id) {
  const card = document.querySelector(`.material-card[data-id="${id}"]`);
  if (!card) return;

  const img = card.querySelector(".material-card-img");
  const title = card.querySelector(".material-card-title").textContent;

  document.getElementById("preview-title").textContent = title;
  document.getElementById("preview-image").src = img.src;
  const modal = document.getElementById("preview-modal");
  modal.classList.add("show");
  modal.style.display = "flex";
}

function closePreviewModal() {
  const modal = document.getElementById("preview-modal");
  modal.classList.remove("show");
  modal.style.display = "none";
}

// ── 编辑素材 ──────────────────────────────────────────────────
async function openEditModal(id) {
  try {
    const resp = await fetch(`/api/material_library/${id}`);
    const data = await resp.json();

    if (!data.ok) {
      showToast(data.error || "获取素材信息失败", "error");
      return;
    }

    editingId = id;
    document.getElementById("edit-title").value = data.title || "";
    document.getElementById("edit-tags").value = data.tags || "";
    document.getElementById("edit-notes").value = data.notes || "";

    // 设置分组
    updateGroupSelects();
    const groupSelect = document.getElementById("edit-group");
    if (data.group_id) {
      groupSelect.value = data.group_id;
    } else {
      groupSelect.value = "";
    }

    const modal = document.getElementById("edit-modal");
    modal.classList.add("show");
    modal.style.display = "flex";
  } catch (e) {
    showToast("获取素材信息失败", "error");
  }
}

function closeEditModal() {
  editingId = null;
  const modal = document.getElementById("edit-modal");
  modal.classList.remove("show");
  modal.style.display = "none";
}

async function saveEdit() {
  if (!editingId) return;

  const title = document.getElementById("edit-title").value.trim();
  const tags = document.getElementById("edit-tags").value.trim();
  const notes = document.getElementById("edit-notes").value.trim();
  const groupId = document.getElementById("edit-group").value;

  try {
    const resp = await fetch(`/api/material_library/${editingId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        title,
        tags,
        notes,
        group_id: groupId || null,
      }),
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("保存成功", "success");
      closeEditModal();
      loadMaterials();
      loadTags();
      loadGroups();
    } else {
      showToast(data.error || "保存失败", "error");
    }
  } catch (e) {
    showToast("保存失败", "error");
  }
}

// ── 删除素材 ──────────────────────────────────────────────────
async function deleteMaterial(id) {
  if (!confirm("确定删除这个素材？")) return;

  try {
    const resp = await fetch(`/api/material_library/${id}`, {
      method: "DELETE",
    });
    const data = await resp.json();

    if (data.ok) {
      showToast("已删除", "success");
      loadMaterials();
      loadTags();
      loadGroups();
    } else {
      showToast(data.error || "删除失败", "error");
    }
  } catch (e) {
    showToast("删除失败", "error");
  }
}

// ── 下载素材 ──────────────────────────────────────────────────
function downloadMaterial(url, filename) {
  const link = document.createElement("a");
  link.href = url;
  link.download = filename || "material.png";
  link.target = "_blank";
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
}

// ── 工具函数 ──────────────────────────────────────────────────
function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

// 转义JS字符串中的单引号，用于onclick属性
function escapeJs(str) {
  return (str || "").replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

function showToast(msg, type = "info") {
  if (window.showToastGlobal) {
    window.showToastGlobal(msg, type);
    return;
  }
  const toast = document.createElement("div");
  toast.style.cssText = `
    position: fixed; top: 20px; right: 20px; z-index: 9999;
    padding: 12px 20px; border-radius: 8px; font-size: 14px;
    color: #fff; max-width: 400px;
    background: ${type === "error" ? "#e74c3c" : type === "success" ? "#07c160" : "#333"};
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
  `;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = "0";
    toast.style.transition = "opacity 0.3s";
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}
