"use strict";

const bloodCompatibility = {
  "O-": ["O-", "O+", "A-", "A+", "B-", "B+", "AB-", "AB+"],
  "O+": ["O+", "A+", "B+", "AB+"],
  "A-": ["A-", "A+", "AB-", "AB+"],
  "A+": ["A+", "AB+"],
  "B-": ["B-", "B+", "AB-", "AB+"],
  "B+": ["B+", "AB+"],
  "AB-": ["AB-", "AB+"],
  "AB+": ["AB+"]
};

let state = {
  donors: [],
  cases: [],
  inventory: {},
  appointments: [],
  alerts: [],
  demoMode: false
};

const titleMap = {
  overview: "Operations Overview",
  donors: "Donor Registry",
  blood: "Blood Bank Inventory",
  organs: "Organ Waitlist",
  matching: "Compatibility Matching",
  appointments: "Donation Appointments"
};

const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => Array.from(document.querySelectorAll(selector));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function icon(name, className = "inline-icon") {
  return `<svg class="${className}" aria-hidden="true"><use href="#icon-${name}"></use></svg>`;
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function apiRequest(path, options = {}) {
  const config = { headers: { Accept: "application/json" }, ...options };
  if (options.body !== undefined) {
    config.method = options.method || "POST";
    config.headers["Content-Type"] = "application/json";
    config.headers["X-CSRFToken"] = getCookie("csrftoken") || "";
    config.body = JSON.stringify(options.body);
  }

  const response = await fetch(path, config);
  let payload = null;
  try {
    payload = await response.json();
  } catch (error) {
    payload = null;
  }

  if (response.status === 401) {
    window.location.assign("/login/");
    throw new Error("Your session has expired. Redirecting to sign in.");
  }

  if (!response.ok) {
    const errors = payload && payload.errors ? Object.values(payload.errors).join(" ") : "";
    throw new Error(errors || `Request failed (${response.status}).`);
  }
  return payload;
}

async function refreshState() {
  state = await apiRequest("/api/state/");
}

function formatDate(dateValue) {
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric"
  }).format(new Date(`${dateValue}T00:00:00`));
}

function showToast(message) {
  const toast = $("#toast");
  toast.textContent = message;
  toast.classList.add("is-visible");
  window.clearTimeout(showToast.timeout);
  showToast.timeout = window.setTimeout(() => toast.classList.remove("is-visible"), 2600);
}

function setActiveView(viewId, options = {}) {
  const shouldUpdateHash = options.updateHash !== false;
  $$(".view").forEach((view) => view.classList.toggle("is-visible", view.id === viewId));
  $$(".nav-link").forEach((link) => {
    const isActive = link.dataset.view === viewId;
    link.classList.toggle("is-active", isActive);
    if (isActive) {
      link.setAttribute("aria-current", "page");
    } else {
      link.removeAttribute("aria-current");
    }
  });
  $("#view-title").textContent = titleMap[viewId] || "Operations Overview";
  document.title = `${titleMap[viewId] || "Operations Overview"} | LifeBridge`;

  if (shouldUpdateHash && window.location.hash.slice(1) !== viewId) {
    history.replaceState(null, "", `#${viewId}`);
  }

  window.scrollTo({ top: 0, behavior: "smooth" });
}

function getPriorityRank(priority) {
  return { Critical: 1, High: 2, Standard: 3 }[priority] || 4;
}

function getStockStatus(units) {
  if (units <= 5) return { label: "Critical", className: "is-critical" };
  if (units <= 10) return { label: "Low", className: "is-low" };
  return { label: "Ready", className: "is-ready" };
}

function getStatusClass(status) {
  if (status === "Available") return "is-available";
  if (status === "Contacted") return "is-contacted";
  return "is-review";
}

function getPriorityClass(priority) {
  if (priority === "Critical") return "is-critical";
  if (priority === "High") return "is-high";
  return "";
}

function renderMetrics() {
  const totalBlood = Object.values(state.inventory).reduce((sum, units) => sum + units, 0);
  const organDonors = state.donors.filter((donor) => donor.organs.length > 0).length;
  const criticalCases = state.cases.filter((item) => item.priority === "Critical").length;
  const availableDonors = state.donors.filter((donor) => donor.status === "Available").length;

  const metrics = [
    { label: "Blood units", value: totalBlood, helper: "Across all blood groups", icon: "droplet" },
    { label: "Available donors", value: availableDonors, helper: `${state.donors.length} registered total`, icon: "users" },
    { label: "Organ donors", value: organDonors, helper: "With consent recorded", icon: "heart-pulse" },
    { label: "Critical cases", value: criticalCases, helper: "Need active coordination", icon: "alert" }
  ];

  $("#metric-grid").innerHTML = metrics
    .map(
      (metric) => `
        <article class="metric-card">
          <div class="metric-top">
            <p>${metric.label}</p>
            ${icon(metric.icon, "metric-icon")}
          </div>
          <strong>${metric.value}</strong>
          <span>${metric.helper}</span>
        </article>
      `
    )
    .join("");
}

function renderPriorityCases() {
  const rows = [...state.cases]
    .sort((a, b) => getPriorityRank(a.priority) - getPriorityRank(b.priority))
    .slice(0, 5)
    .map(
      (item) => `
        <tr>
          <td data-label="Recipient"><strong>${escapeHtml(item.recipient)}</strong></td>
          <td data-label="Need">${escapeHtml(item.needType === "Organ" ? item.organ : item.bloodType)}</td>
          <td data-label="Priority"><span class="tag ${getPriorityClass(item.priority)}">${escapeHtml(item.priority)}</span></td>
          <td data-label="Location">${escapeHtml(item.region)}</td>
        </tr>
      `
    )
    .join("");

  $("#priority-cases").innerHTML =
    rows || `<tr><td data-label="Demand" colspan="4">No recipient cases yet.</td></tr>`;
}

function renderAlerts() {
  $("#alert-stack").innerHTML =
    state.alerts
      .slice(0, 4)
      .map(
        (alert) => `
          <article class="alert-item ${alert.level === "Critical" ? "is-critical" : ""}">
            ${icon(alert.level === "Critical" ? "alert" : "bell", "alert-card-icon")}
            <div>
              <strong>${escapeHtml(alert.title)}</strong>
              <p>${escapeHtml(alert.message)}</p>
            </div>
          </article>
        `
      )
      .join("") || `<div class="empty-state">No alerts right now.</div>`;
}

function renderBloodOverview() {
  $("#overview-blood-grid").innerHTML = Object.entries(state.inventory)
    .map(([type, units]) => {
      const status = getStockStatus(units);
      return `
        <article class="blood-card">
          <div class="blood-card-top">
            ${icon("droplet", "card-icon")}
            <div class="blood-type">${escapeHtml(type)}</div>
          </div>
          <div class="unit-count">${units} units available</div>
          <span class="stock-pill ${status.className}">${status.label}</span>
        </article>
      `;
    })
    .join("");
}

function renderDonors() {
  const search = $("#donor-search").value.trim().toLowerCase();
  const typeFilter = $("#donor-type-filter").value;
  const bloodFilter = $("#donor-blood-filter").value;

  const donors = state.donors.filter((donor) => {
    const matchesSearch =
      donor.name.toLowerCase().includes(search) || donor.region.toLowerCase().includes(search);
    const matchesType = typeFilter === "All" || donor.type === typeFilter;
    const matchesBlood = bloodFilter === "All" || donor.bloodType === bloodFilter;
    return matchesSearch && matchesType && matchesBlood;
  });

  $("#donor-table").innerHTML =
    donors
      .map(
        (donor) => `
          <tr>
            <td data-label="Name"><strong>${escapeHtml(donor.name)}</strong><br><span class="muted-text">#${escapeHtml(donor.id)}</span></td>
            <td data-label="Type">${escapeHtml(donor.type)}</td>
            <td data-label="Blood">${escapeHtml(donor.bloodType)}</td>
            <td data-label="Region">${escapeHtml(donor.region)}</td>
            <td data-label="Organs">${donor.organs.length ? escapeHtml(donor.organs.join(", ")) : "None"}</td>
            <td data-label="Status"><span class="status-pill ${getStatusClass(donor.status)}">${escapeHtml(donor.status)}</span></td>
          </tr>
        `
      )
      .join("") || `<tr><td data-label="Registry" colspan="6">No donors match the current filters.</td></tr>`;
}

function renderInventory() {
  $("#inventory-grid").innerHTML = Object.entries(state.inventory)
    .map(([type, units]) => {
      const status = getStockStatus(units);
      return `
        <article class="inventory-card">
          <div class="inventory-card-head">
            ${icon("droplet", "card-icon")}
            <div>
              <div class="blood-type">${escapeHtml(type)}</div>
              <div class="unit-count">${units} units in stock</div>
            </div>
          </div>
          <span class="stock-pill ${status.className}">${status.label}</span>
          <div class="inventory-actions">
            <button class="stepper-button" type="button" data-stock-action="decrease" data-blood="${escapeHtml(type)}" aria-label="Decrease ${escapeHtml(type)} stock">${icon("minus", "button-icon")}</button>
            <button class="reserve-button" type="button" data-stock-action="reserve" data-blood="${escapeHtml(type)}">
              ${icon("lock", "button-icon")}
              Reserve 1
            </button>
            <button class="stepper-button" type="button" data-stock-action="increase" data-blood="${escapeHtml(type)}" aria-label="Increase ${escapeHtml(type)} stock">${icon("plus", "button-icon")}</button>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderCases() {
  $("#case-list").innerHTML =
    [...state.cases]
      .sort((a, b) => getPriorityRank(a.priority) - getPriorityRank(b.priority))
      .map(
        (item) => `
          <article class="case-card">
            <div>
              <div class="record-title">
                ${icon(item.needType === "Organ" ? "heart-pulse" : "droplet", "record-icon")}
                <strong>${escapeHtml(item.recipient)}</strong>
              </div>
              <p>${escapeHtml(item.hospital)}, ${escapeHtml(item.region)}</p>
              <div class="case-meta">
                <span class="tag ${getPriorityClass(item.priority)}">${icon("alert", "tag-icon")}${escapeHtml(item.priority)}</span>
                <span class="tag">${icon(item.needType === "Organ" ? "heart-pulse" : "droplet", "tag-icon")}${escapeHtml(item.needType)}</span>
                <span class="tag">${icon("clipboard", "tag-icon")}${escapeHtml(item.needType === "Organ" ? item.organ : item.bloodType)}</span>
                <span class="tag">${icon("droplet", "tag-icon")}${escapeHtml(item.bloodType)}</span>
              </div>
            </div>
            <button class="ghost-button small" type="button" data-match-case="${escapeHtml(item.id)}">
              ${icon("network", "button-icon")}
              Match
            </button>
          </article>
        `
      )
      .join("") || `<div class="empty-state">No recipient cases have been created.</div>`;
}

function renderMatchCaseSelect() {
  const select = $("#match-case-select");
  const previous = select.value;
  select.innerHTML = state.cases
    .map(
      (item) =>
        `<option value="${escapeHtml(item.id)}">${escapeHtml(item.recipient)} - ${escapeHtml(item.priority)} ${escapeHtml(item.needType)}</option>`
    )
    .join("");
  if (previous && state.cases.some((item) => item.id === previous)) {
    select.value = previous;
  }
}

function getMatches(caseItem) {
  return state.donors
    .filter((donor) => donor.status !== "Medical Review")
    .map((donor) => {
      const bloodMatch = (bloodCompatibility[donor.bloodType] || []).includes(caseItem.bloodType);
      const organMatch =
        caseItem.needType === "Blood" || (caseItem.organ && donor.organs.includes(caseItem.organ));
      const exactRegion = donor.region.toLowerCase() === caseItem.region.toLowerCase();
      const available = donor.status === "Available";
      let score = 0;

      if (bloodMatch) score += 42;
      if (organMatch) score += 30;
      if (exactRegion) score += 18;
      if (available) score += 10;

      return {
        donor,
        score,
        reasons: [
          bloodMatch ? `${donor.bloodType} compatible with ${caseItem.bloodType}` : "Blood group not compatible",
          organMatch ? "Need type covered" : `${caseItem.organ} consent not recorded`,
          exactRegion ? "Same region" : `Located in ${donor.region}`,
          available ? "Available now" : donor.status
        ]
      };
    })
    .filter((match) => match.score >= 60)
    .sort((a, b) => b.score - a.score);
}

function runMatch(caseId = $("#match-case-select").value) {
  const caseItem = state.cases.find((item) => item.id === caseId);
  if (!caseItem) {
    $("#match-results").innerHTML = `<div class="empty-state">Create a recipient case before running a match.</div>`;
    return;
  }

  $("#match-case-select").value = caseId;
  const matches = getMatches(caseItem);

  $("#match-results").innerHTML =
    matches
      .map(
        ({ donor, score, reasons }) => `
          <article class="match-card">
            <div>
              <div class="record-title">
                ${icon("users", "record-icon")}
                <strong>${escapeHtml(donor.name)}</strong>
              </div>
              <p>${escapeHtml(donor.type)} donor, ${escapeHtml(donor.bloodType)}, ${escapeHtml(donor.region)}</p>
              <div class="match-meta">
                ${reasons.map((reason) => `<span class="tag">${icon("check", "tag-icon")}${escapeHtml(reason)}</span>`).join("")}
              </div>
            </div>
            <div class="score-block" aria-label="Match score ${score} percent">
              ${icon("activity", "score-icon")}
              <span>${score}%</span>
              Match
            </div>
          </article>
        `
      )
      .join("") ||
    `<div class="empty-state">No eligible matches found. Try broadening region outreach or updating donor eligibility.</div>`;
}

function renderAppointmentDonors() {
  $("#appointment-donor-select").innerHTML = state.donors
    .filter((donor) => donor.status !== "Medical Review")
    .map((donor) => `<option value="${escapeHtml(donor.id)}">${escapeHtml(donor.name)} - ${escapeHtml(donor.bloodType)}</option>`)
    .join("");
}

function renderAppointments() {
  $("#appointment-list").innerHTML =
    [...state.appointments]
      .sort((a, b) => `${a.date}${a.time}`.localeCompare(`${b.date}${b.time}`))
      .map((appointment) => {
        const donor = state.donors.find((item) => item.id === appointment.donorId);
        return `
          <article class="appointment-card">
            <div class="record-title">
              ${icon("calendar", "record-icon")}
              <strong>${donor ? escapeHtml(donor.name) : "Unknown donor"}</strong>
            </div>
            <p>${formatDate(appointment.date)} at ${escapeHtml(appointment.time)} - ${escapeHtml(appointment.site)}</p>
            <div class="appointment-meta">
              <span class="tag">${icon("clipboard", "tag-icon")}${escapeHtml(appointment.purpose)}</span>
              <span class="tag">${icon("clock", "tag-icon")}${donor ? escapeHtml(donor.phone) : "No phone"}</span>
            </div>
          </article>
        `;
      })
      .join("") || `<div class="empty-state">No appointments scheduled yet.</div>`;
}

function renderAll() {
  renderMetrics();
  renderPriorityCases();
  renderAlerts();
  renderBloodOverview();
  renderDonors();
  renderInventory();
  renderCases();
  renderMatchCaseSelect();
  renderAppointmentDonors();
  renderAppointments();

  $("#reset-data").hidden = !state.demoMode;

  if ($("#match-case-select").value) {
    runMatch($("#match-case-select").value);
  } else {
    $("#match-results").innerHTML = `<div class="empty-state">Create a recipient case before running a match.</div>`;
  }
}

async function mutate(action, successMessage) {
  try {
    await action();
    await refreshState();
    renderAll();
    if (successMessage) showToast(successMessage);
    return true;
  } catch (error) {
    showToast(error.message || "Something went wrong. Please try again.");
    return false;
  }
}

function bindNavigation() {
  $$(".nav-link").forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.view));
  });

  $$("[data-jump]").forEach((button) => {
    button.addEventListener("click", () => setActiveView(button.dataset.jump));
  });
}

function bindForms() {
  $("#donor-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    const ok = await mutate(
      () =>
        apiRequest("/api/donors/", {
          body: {
            name: data.get("name").trim(),
            donor_type: data.get("type"),
            blood_type: data.get("bloodType"),
            region: data.get("region").trim(),
            phone: data.get("phone").trim(),
            organs: data.getAll("organs")
          }
        }),
      "Donor registered and added to the matching pool."
    );
    if (ok) form.reset();
  });

  $("#case-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    const needType = data.get("needType");

    const ok = await mutate(
      () =>
        apiRequest("/api/cases/", {
          body: {
            recipient: data.get("recipient").trim(),
            need_type: needType,
            priority: data.get("priority"),
            blood_type: data.get("bloodType"),
            organ: needType === "Organ" ? data.get("organ") || "Kidney" : "",
            hospital: data.get("hospital").trim(),
            region: data.get("region").trim()
          }
        }),
      "Case created. Matching results are ready."
    );
    if (ok) {
      form.reset();
      setActiveView("matching");
      if (state.cases.length) {
        runMatch(state.cases[0].id);
      }
    }
  });

  $("#appointment-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);

    const ok = await mutate(
      () =>
        apiRequest("/api/appointments/", {
          body: {
            donorId: data.get("donorId"),
            date: data.get("date"),
            time: data.get("time"),
            site: data.get("site").trim(),
            purpose: data.get("purpose")
          }
        }),
      "Appointment scheduled."
    );
    if (ok) {
      form.reset();
      setDefaultAppointmentDate();
    }
  });
}

function bindFilters() {
  ["#donor-search", "#donor-type-filter", "#donor-blood-filter"].forEach((selector) => {
    $(selector).addEventListener("input", renderDonors);
  });
}

function bindInventoryActions() {
  $("#inventory-grid").addEventListener("click", (event) => {
    const button = event.target.closest("[data-stock-action]");
    if (!button) return;

    const bloodType = button.dataset.blood;
    const action = button.dataset.stockAction;
    const delta = action === "increase" ? 1 : -1;
    const message =
      action === "increase"
        ? `${bloodType} stock increased.`
        : action === "reserve"
          ? `${bloodType} unit reserved.`
          : `${bloodType} stock decreased.`;

    mutate(() => apiRequest("/api/inventory/", { body: { blood_type: bloodType, delta } }), message);
  });
}

function bindCaseActions() {
  $("#case-list").addEventListener("click", (event) => {
    const button = event.target.closest("[data-match-case]");
    if (!button) return;
    setActiveView("matching");
    runMatch(button.dataset.matchCase);
  });

  $("#run-match").addEventListener("click", () => {
    runMatch();
    showToast("Compatibility matching refreshed.");
  });
}

function bindUtilityActions() {
  $("#simulate-alert").addEventListener("click", () => {
    const entries = Object.entries(state.inventory);
    if (!entries.length) return;
    const lowestStock = entries.sort((a, b) => a[1] - b[1])[0];

    mutate(
      () =>
        apiRequest("/api/alerts/", {
          body: {
            level: lowestStock[1] <= 5 ? "Critical" : "Notice",
            title: `${lowestStock[0]} reserve check`,
            message: `${lowestStock[1]} units available after the latest stock review.`
          }
        }),
      "Network alert added."
    );
  });

  $("#reset-data").addEventListener("click", () => {
    if (!window.confirm("Reset all data back to the demo dataset?")) return;
    mutate(() => apiRequest("/api/reset/", { body: {} }), "Demo data reset.").then((ok) => {
      if (ok) setActiveView("overview");
    });
  });
}

function bindRouteSync() {
  window.addEventListener("hashchange", () => {
    const viewId = window.location.hash.slice(1);
    if (titleMap[viewId]) {
      setActiveView(viewId, { updateHash: false });
    }
  });
}

function setDefaultAppointmentDate() {
  const dateInput = $('#appointment-form input[name="date"]');
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  dateInput.min = new Date().toISOString().slice(0, 10);
  dateInput.value = tomorrow.toISOString().slice(0, 10);
}

async function init() {
  bindNavigation();
  bindForms();
  bindFilters();
  bindInventoryActions();
  bindCaseActions();
  bindUtilityActions();
  bindRouteSync();
  setDefaultAppointmentDate();

  try {
    await refreshState();
  } catch (error) {
    showToast("Could not reach the server. Please refresh the page.");
    console.error("Failed to load initial state", error);
  }

  renderAll();
  const initialView = titleMap[window.location.hash.slice(1)] ? window.location.hash.slice(1) : "overview";
  setActiveView(initialView, { updateHash: Boolean(window.location.hash) });
}

document.addEventListener("DOMContentLoaded", init);
