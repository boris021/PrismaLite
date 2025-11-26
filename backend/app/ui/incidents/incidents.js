// Простая "оперативка" поверх API PrismaLite:
// /api/v1/incidents, /api/v1/incidents/{id}, /api/v1/receipts/{id}

let incidents = [];
let selectedIncidentId = null;
let selectedIndex = -1;
let currentIncident = null;
let currentEvents = [];

// --- Утилиты форматирования ---

function fmtDate(str) {
  if (!str) return "";
  try {
    const d = new Date(str);
    return d.toLocaleString();
  } catch {
    return str;
  }
}

function sevBadgeClass(sev) {
  if (sev === "A") return "badge-sev-A";
  if (sev === "B") return "badge-sev-B";
  if (sev === "C") return "badge-sev-C";
  return "badge-muted";
}

function statusBadgeClass(st) {
  if (st === "new") return "badge-st-new";
  if (st === "in_progress") return "badge-st-in_progress";
  if (st === "closed") return "badge-st-closed";
  if (st === "false_positive") return "badge-st-false_positive";
  return "badge-muted";
}

function statusRu(st) {
  switch (st) {
    case "new": return "Не обработано";
    case "in_progress": return "В работе";
    case "closed": return "Подтверждено";
    case "false_positive": return "Ложное";
    default: return st || "—";
  }
}

// --- Загрузка инцидентов ---

async function loadIncidents() {
  selectedIncidentId = null;
  currentIncident = null;
  currentEvents = [];
  selectedIndex = -1;
  renderIncidentDetails(null, []);
  renderReceipt(null, []);
  renderIncidentsTable();

  const status = document.getElementById("filterStatus").value;
  const severity = document.getElementById("filterSeverity").value;
  const shop = document.getElementById("filterShop").value.trim();
  const from = document.getElementById("filterFrom").value;
  const to = document.getElementById("filterTo").value;

  const params = new URLSearchParams();
  params.append("limit", "200");
  if (status) params.append("status", status);
  if (severity) params.append("severity", severity);
  if (shop) params.append("shop", shop);
  if (from) params.append("date_from", new Date(from).toISOString());
  if (to) params.append("date_to", new Date(to).toISOString());

  const url = "/api/v1/incidents?" + params.toString();

  const tbody = document.getElementById("incidentsTableBody");
  tbody.innerHTML = `<tr><td colspan="8" class="empty-cell">Загрузка...</td></tr>`;

  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    incidents = data.items || [];
    document.getElementById("incidentsCountBadge").textContent =
      String(data.total ?? incidents.length);
    document.getElementById("centerSubtitle").textContent =
      incidents.length
        ? "Выберите строку для просмотра деталей чека и видео."
        : "Инциденты по заданным фильтрам не найдены.";
    updateRulesList();
    renderIncidentsTable();
  } catch (e) {
    console.error("Ошибка загрузки инцидентов:", e);
    tbody.innerHTML =
      `<tr><td colspan="8" class="empty-cell">Ошибка загрузки данных</td></tr>`;
    document.getElementById("incidentsCountBadge").textContent = "—";
  }
}

function updateRulesList() {
  const rulesContainer = document.querySelector(".rules-list");
  const badge = document.getElementById("rulesCountBadge");
  const typesSet = new Set();
  incidents.forEach(inc => {
    (inc.event_types || []).forEach(t => typesSet.add(t));
  });
  const types = Array.from(typesSet);
  badge.textContent = types.length ? String(types.length) : "—";

  if (!types.length) {
    rulesContainer.innerHTML =
      `<div class="rules-placeholder">По найденным инцидентам типы событий не обнаружены.</div>`;
    return;
  }
  rulesContainer.innerHTML = types
    .sort()
    .map(t => `<div>• ${t}</div>`)
    .join("");
}

// --- Рендер таблицы ---

function renderIncidentsTable() {
  const tbody = document.getElementById("incidentsTableBody");
  if (!incidents.length) {
    tbody.innerHTML =
      `<tr><td colspan="8" class="empty-cell">Нет данных. Измените фильтры и нажмите «Применить».</td></tr>`;
    return;
  }
  tbody.innerHTML = incidents
    .map((inc, idx) => {
      const selectedClass = inc.id === selectedIncidentId ? "selected" : "";
      const evTypes = (inc.event_types || []).join(", ");
      return `
        <tr class="${selectedClass}" data-id="${inc.id}" data-index="${idx}">
          <td>${inc.id}</td>
          <td>${inc.shop || ""}</td>
          <td>${inc.cash || ""}</td>
          <td>${inc.number || ""}</td>
          <td>${fmtDate(inc.sale_time)}</td>
          <td><span class="badge ${sevBadgeClass(inc.severity)}">${inc.severity || "-"}</span></td>
          <td><span class="badge ${statusBadgeClass(inc.status)}">${statusRu(inc.status)}</span></td>
          <td>${evTypes}</td>
        </tr>
      `;
    })
    .join("");
}

// --- Выбор инцидента ---

async function selectIncidentByIndex(index) {
  if (index < 0 || index >= incidents.length) return;
  const id = incidents[index].id;
  selectedIndex = index;
  selectedIncidentId = id;
  renderIncidentsTable();
  await selectIncident(id);
}

async function selectIncident(id) {
  try {
    const res = await fetch(`/api/v1/incidents/${id}`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    currentIncident = data.incident;
    currentEvents = data.events || [];
    renderIncidentDetails(currentIncident, currentEvents);
    await loadReceipt(currentIncident.receipt_id, currentEvents);
  } catch (e) {
    console.error("Ошибка загрузки инцидента:", e);
  }
}

async function loadReceipt(receiptId, incidentEvents) {
  if (!receiptId) {
    renderReceipt(null, []);
    return;
  }
  try {
    const res = await fetch(`/api/v1/receipts/${receiptId}`);
    if (!res.ok) throw new Error("HTTP " + res.status);
    const data = await res.json();
    renderReceipt(data, incidentEvents);
  } catch (e) {
    console.error("Ошибка загрузки чека:", e);
    renderReceipt(null, []);
  }
}

// --- Рендер деталей инцидента и чека ---

function renderIncidentDetails(incident, events) {
  const videoRuleName = document.getElementById("videoRuleName");
  const videoMeta = document.getElementById("videoMeta");
  const videoAmount = document.getElementById("videoAmount");
  const checkTitle = document.getElementById("checkTitle");
  const checkMeta = document.getElementById("checkMeta");
  const incidentDetails = document.getElementById("incidentDetails");
  const incidentStatusBadge = document.getElementById("incidentStatusBadge");
  const eventsCountBadge = document.getElementById("eventsCountBadge");
  const eventsList = document.getElementById("eventsList");

  if (!incident) {
    videoRuleName.textContent = "Инцидент не выбран";
    videoMeta.textContent = "Выберите строку в таблице ниже.";
    videoAmount.textContent = "—";
    checkTitle.textContent = "Чек не выбран";
    checkMeta.textContent = "Нажмите на строку в таблице слева.";
    incidentDetails.innerHTML = `<div class="placeholder">Нет выбранного инцидента.</div>`;
    eventsList.innerHTML =
      `<div class="placeholder">События появятся после выбора инцидента.</div>`;
    incidentStatusBadge.textContent = "—";
    eventsCountBadge.textContent = "0";
    return;
  }

  videoRuleName.textContent = (incident.event_types || []).join(", ") || "Инцидент";
  videoMeta.textContent =
    `Магазин ${incident.shop || "?"}, касса ${incident.cash || "?"}, смена ${incident.shift || "?"}, чек № ${incident.number || "?"}`;
  videoAmount.textContent = ""; // будет заполнено после загрузки чека

  checkTitle.textContent = `Чек № ${incident.number || "—"}`;
  checkMeta.textContent = `${fmtDate(incident.sale_time)} · магазин ${incident.shop || "?"}, касса ${incident.cash || "?"}`;

  incidentStatusBadge.textContent = statusRu(incident.status);
  incidentStatusBadge.className = `badge-muted ${statusBadgeClass(incident.status)}`;

  incidentDetails.innerHTML = `
    <div><b>Rиск:</b> <span class="badge ${sevBadgeClass(incident.severity)}">${incident.severity || "-"}</span></div>
    <div><b>Статус:</b> ${statusRu(incident.status)}</div>
    <div><b>События:</b> ${(incident.event_types || []).join(", ") || "—"}</div>
    <div><b>Кол-во событий:</b> ${incident.events_count}</div>
    <div><b>Комментарий:</b> ${incident.last_comment || "<span class='placeholder'>нет</span>"}</div>
    <div><b>Обновил:</b> ${incident.updated_by || "<span class='placeholder'>нет</span>"} (${fmtDate(incident.updated_at)})</div>
  `;

  if (!events.length) {
    eventsList.innerHTML =
      `<div class="placeholder">По этому чеку нет событий.</div>`;
    eventsCountBadge.textContent = "0";
  } else {
    eventsCountBadge.textContent = String(events.length);
    eventsList.innerHTML = events
      .map(ev => `
        <div class="event-item">
          <div class="event-title-line">
            <span>${ev.event_type}</span>
            <span class="badge ${sevBadgeClass(ev.severity)}">${ev.severity}</span>
          </div>
          <div class="event-meta">${fmtDate(ev.created_at)}</div>
          <div class="event-meta">
            ${renderDetailsPills(ev.details)}
          </div>
        </div>
      `)
      .join("");
  }
}

function renderDetailsPills(details) {
  if (!details || typeof details !== "object") {
    return "<span class='badge-muted'>нет деталей</span>";
  }
  return Object.entries(details)
    .map(([k, v]) => `<span class="badge-muted" style="margin-right:3px; font-size:10px;"><b>${k}</b>: ${v}</span>`)
    .join(" ");
}

function renderReceipt(receipt, events) {
  const wrapper = document.getElementById("center-table"); // для суммы в хедере
  const videoAmount = document.getElementById("videoAmount");
  const checkMeta = document.getElementById("checkMeta");
  const receiptAmountLine = document.getElementById("receiptAmountLine");
  const centerSubtitle = document.getElementById("centerSubtitle");

  // таблица позиций в правой панели уже рисуется в events? —
  // в этом макете позиции не выводим, только сумму и скидку. Если нужно — можно расширить.

  if (!receipt) {
    videoAmount.textContent = "—";
    return;
  }

  const amount = receipt.amount ?? 0;
  const discount = receipt.discount_amount ?? 0;
  videoAmount.textContent = amount.toFixed(2) + " ₸";
  centerSubtitle.textContent =
    `Магазин ${receipt.shop || "?"}, касса ${receipt.cash || "?"}, чек № ${receipt.number || "?"}, сумма ${amount.toFixed(2)}₸`;
}

// --- PATCH статуса ---

async function updateIncidentStatus(newStatus, commentOverride) {
  if (!currentIncident) return;
  const id = currentIncident.id;
  const commentField = document.getElementById("commentInput");
  const comment = (commentOverride !== undefined ? commentOverride : commentField.value.trim()) || null;

  const payload = {
    status: newStatus,
    comment: comment,
    updated_by: "security_ui"
  };

  try {
    const res = await fetch(`/api/v1/incidents/${id}/status`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      alert("Ошибка сохранения статуса: HTTP " + res.status);
      return;
    }
    const updated = await res.json();

    // обновляем в массиве
    const idx = incidents.findIndex(i => i.id === updated.id);
    if (idx !== -1) incidents[idx] = updated;
    currentIncident = updated;
    selectedIncIndex = idx;

    // перерисовываем
    renderIncidentDetails(currentIncident, currentEvents);
    renderIncidentsTable();
    commentField.value = "";
  } catch (e) {
    console.error("Ошибка сохранения статуса:", e);
    alert("Ошибка сохранения статуса");
  }
}

// --- Ресайз панелей ---

function initResizers() {
  const resizerLeft = document.getElementById("resizer-left");
  const resizerRight = document.getElementById("resizer-right");
  const resizerCenter = document.getElementById("resizer-center");
  const panelLeft = document.getElementById("panel-left");
  const panelRight = document.getElementById("panel-right");
  const videoArea = document.getElementById("video-area");
  const panelCenter = document.getElementById("panel-center");

  let isVLeft = false;
  let isVRight = false;
  let isHCenter = false;
  let startX = 0;
  let startWidthLeft = 0;
  let startWidthRight = 0;
  let startY = 0;
  let startVideoHeight = 0;

  function onMouseMove(e) {
    if (window.innerWidth < 900) return;

    if (isVLeft) {
      const dx = e.clientX - startX;
      let newWidth = startWidthLeft + dx;
      const min = 220;
      const max = 420;
      if (newWidth < min) newWidth = min;
      if (newWidth > max) newWidth = max;
      panelLeft.style.width = newWidth + "px";
    } else if (isVRight) {
      const dx = startX - e.clientX;
      let newWidth = startWidthRight + dx;
      const min = 260;
      const max = 420;
      if (newWidth < min) newWidth = min;
      if (newWidth > max) newWidth = max;
      panelRight.style.width = newWidth + "px";
    } else if (isHCenter) {
      const dy = e.clientY - startY;
      let newHeight = startVideoHeight + dy;
      const containerHeight = panelCenter.getBoundingClientRect().height;
      const min = 180;
      const max = containerHeight - 140;
      if (newHeight < min) newHeight = min;
      if (newHeight > max) newHeight = max;
      videoArea.style.flex = "0 0 " + newHeight + "px";
    }
  }

  function onMouseUp() {
    isVLeft = false;
    isVRight = false;
    isHCenter = false;
    document.body.style.cursor = "default";
  }

  resizerLeft.addEventListener("mousedown", (e) => {
    if (window.innerWidth < 900) return;
    isVLeft = true;
    startX = e.clientX;
    startWidthLeft = panelLeft.getBoundingClientRect().width;
    document.body.style.cursor = "col-resize";
    e.preventDefault();
  });

  resizerRight.addEventListener("mousedown", (e) => {
    if (window.innerWidth < 900) return;
    isVRight = true;
    startX = e.clientX;
    startWidthRight = panelRight.getBoundingClientRect().width;
    document.body.style.cursor = "col-resize";
    e.preventDefault();
  });

  resizerCenter.addEventListener("mousedown", (e) => {
    isHCenter = true;
    startY = e.clientY;
    startVideoHeight = videoArea.getBoundingClientRect().height;
    document.body.style.cursor = "row-resize";
    e.preventDefault();
  });

  window.addEventListener("mousemove", onMouseMove);
  window.addEventListener("mouseup", onMouseUp);
}

// --- Навигация по инцидентам (пред/след) ---

function gotoPrevIncident() {
  if (selectedIndex <= 0) return;
  selectIncidentByIndex(selectedIndex - 1);
}

function gotoNextIncident() {
  if (selectedIndex < 0) {
    if (incidents.length) selectIncidentByIndex(0);
    return;
  }
  if (selectedIndex >= incidents.length - 1) return;
  selectIncidentByIndex(selectedIndex + 1);
}

// --- Инициализация ---

function initTopbarClock() {
  const el = document.getElementById("topbarClock");
  const update = () => {
    el.textContent = new Date().toLocaleString();
  };
  update();
  setInterval(update, 15000);
}

function initEvents() {
  document
    .getElementById("btnApplyFilters")
    .addEventListener("click", loadIncidents);

  document
    .getElementById("incidentsTableBody")
    .addEventListener("click", (e) => {
      let tr = e.target.closest("tr[data-id]");
      if (!tr) return;
      const id = Number(tr.dataset.id);
      const idx = Number(tr.dataset.index);
      selectedIndex = idx;
      selectedIncidentId = id;
      renderIncidentsTable();
      selectIncident(id);
    });

  document.getElementById("btnPrevIncident").addEventListener("click", gotoPrevIncident);
  document.getElementById("btnNextIncident").addEventListener("click", gotoNextIncident);

  document.getElementById("btnConfirm").addEventListener("click", () => {
    updateIncidentStatus("closed");
  });

  document.getElementById("btnReject").addEventListener("click", () => {
    updateIncidentStatus("false_positive");
  });
}

// старт
window.addEventListener("load", () => {
  initTopbarClock();
  initEvents();
  initResizers();
});
