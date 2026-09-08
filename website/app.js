const uploadForm = document.getElementById("uploadForm");
const fileInput = document.getElementById("fileInput");
const dropZone = document.getElementById("dropZone");
const fileName = document.getElementById("fileName");
const statusPanel = document.getElementById("statusPanel");
const dashboard = document.getElementById("dashboard");
const summaryCards = document.getElementById("summaryCards");
const alertsList = document.getElementById("alertsList");
const riskBars = document.getElementById("riskBars");
const projectTableBody = document.getElementById("projectTableBody");
const tableSearch = document.getElementById("tableSearch");
const detailDrawer = document.getElementById("detailDrawer");
const drawerContent = document.getElementById("drawerContent");
const closeDrawerBtn = document.getElementById("closeDrawerBtn");
const loadSampleBtn = document.getElementById("loadSampleBtn");
const resetBtn = document.getElementById("resetBtn");
const downloadReportBtn = document.getElementById("downloadReportBtn");
const metadataText = document.getElementById("metadataText");

let currentReport = null;
let currentFile = null;

const severityRank = { low: 1, medium: 2, high: 3, critical: 4 };

fileInput.addEventListener("change", () => {
  currentFile = fileInput.files[0] || null;
  updateFileName();
});

["dragenter", "dragover"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });
});

["dragleave", "drop"].forEach((eventName) => {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("dragover");
  });
});

dropZone.addEventListener("drop", (event) => {
  const [file] = event.dataTransfer.files;
  if (!file) return;
  currentFile = file;
  fileName.textContent = file.name;
});

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentFile) {
    showStatus("Please select a CSV or JSON project file first.", "error");
    return;
  }

  try {
    await analyzeFile(currentFile);
  } catch (error) {
    showStatus(error.message || "Analysis failed.", "error");
  }
});

loadSampleBtn.addEventListener("click", async () => {
  try {
    showStatus("Loading sample government project data...", "loading");
    const response = await fetch("/sample.csv");
    if (!response.ok) throw new Error("Could not load sample data.");
    const blob = await response.blob();
    const file = new File([blob], "sample_projects.csv", { type: "text/csv" });
    currentFile = file;
    fileName.textContent = file.name;
    await analyzeFile(file);
    document.getElementById("dashboard").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (error) {
    showStatus(error.message, "error");
  }
});

resetBtn.addEventListener("click", () => {
  uploadForm.reset();
  currentFile = null;
  currentReport = null;
  fileName.textContent = "No file selected";
  dashboard.hidden = true;
  statusPanel.hidden = true;
});

tableSearch.addEventListener("input", () => {
  if (currentReport) renderProjectTable(currentReport.projects, tableSearch.value);
});

closeDrawerBtn.addEventListener("click", closeDrawer);
detailDrawer.addEventListener("click", (event) => {
  if (event.target === detailDrawer) closeDrawer();
});

downloadReportBtn.addEventListener("click", () => {
  if (!currentReport) return;
  const blob = new Blob([JSON.stringify(currentReport, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `jan-drishti-report-${new Date().toISOString().slice(0, 10)}.json`;
  link.click();
  URL.revokeObjectURL(url);
});

async function analyzeFile(file) {
  showStatus("AI engine is cleaning data, detecting anomalies and generating explanations...", "loading");
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/analyze", {
    method: "POST",
    body: formData,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || payload.details || "Analysis failed.");
  }

  currentReport = payload;
  renderReport(payload);
  showStatus("Analysis complete. Review high-priority alerts below.", "success");
}

function renderReport(report) {
  dashboard.hidden = false;
  metadataText.textContent = `${report.metadata.raw_rows_received} rows analyzed from ${report.metadata.source_file} on ${report.metadata.analysis_date}.`;
  renderSummary(report.summary);
  renderAlerts(report.alerts);
  renderRiskBars(report.summary);
  renderProjectTable(report.projects, tableSearch.value);
}

function renderSummary(summary) {
  const highPriority = (summary.critical_risk_count || 0) + (summary.high_risk_count || 0);
  const cards = [
    ["Projects analyzed", summary.projects_analyzed],
    ["Average risk score", `${summary.average_risk_score}/100`],
    ["High priority", highPriority],
    ["Duplicate alerts", summary.duplicate_alert_count],
    ["Delay alerts", summary.delay_alert_count],
    ["Cost overrun alerts", summary.cost_overrun_alert_count],
    ["Financial mismatch", summary.financial_mismatch_count],
    ["Total sanctioned", formatCurrency(summary.total_sanctioned_amount)],
  ];

  summaryCards.innerHTML = cards
    .map(
      ([label, value]) => `
        <article class="summary-card">
          <span>${escapeHtml(label)}</span>
          <strong>${escapeHtml(String(value))}</strong>
        </article>
      `,
    )
    .join("");
}

function renderAlerts(alerts) {
  if (!alerts.length) {
    alertsList.innerHTML = `<div class="alert-item"><strong>No urgent alerts</strong><p>No project crossed high-priority thresholds in this upload.</p></div>`;
    return;
  }

  alertsList.innerHTML = alerts
    .map(
      (alert) => `
        <article class="alert-item">
          <strong>${escapeHtml(alert.project_name)} <span class="level-pill ${levelClass(alert.risk_level)}">${escapeHtml(alert.risk_level)}</span></strong>
          <p>${escapeHtml(alert.reason)} • ${escapeHtml(alert.district)} • Risk ${alert.risk_score}/100 • Fraud ${alert.fraud_score}/100</p>
        </article>
      `,
    )
    .join("");
}

function renderRiskBars(summary) {
  const levels = [
    ["Critical", summary.critical_risk_count || 0],
    ["High", summary.high_risk_count || 0],
    ["Medium", summary.medium_risk_count || 0],
    ["Low", summary.low_risk_count || 0],
  ];
  const total = Math.max(1, summary.projects_analyzed || 0);
  riskBars.innerHTML = levels
    .map(([level, count]) => {
      const pct = Math.round((count / total) * 100);
      return `
        <div class="risk-bar-row">
          <div class="risk-bar-label"><span>${level}</span><span>${count} project(s)</span></div>
          <div class="risk-track"><div class="risk-fill" style="width:${pct}%"></div></div>
        </div>
      `;
    })
    .join("");
}

function renderProjectTable(projects, query = "") {
  const search = query.trim().toLowerCase();
  const filtered = projects.filter(({ project, top_drivers }) => {
    const haystack = [
      project.project_id,
      project.project_name,
      project.department,
      project.district,
      project.block,
      project.contractor,
      ...(top_drivers || []),
    ]
      .join(" ")
      .toLowerCase();
    return haystack.includes(search);
  });

  if (!filtered.length) {
    projectTableBody.innerHTML = `<tr><td colspan="6">No projects match your search.</td></tr>`;
    return;
  }

  projectTableBody.innerHTML = filtered
    .map((result, index) => {
      const { project } = result;
      return `
        <tr>
          <td class="project-cell">
            <strong>${escapeHtml(project.project_name)}</strong>
            <small>${escapeHtml(project.project_id)} • ${escapeHtml(project.department)}</small>
          </td>
          <td>${escapeHtml(project.district)}<br /><small>${escapeHtml(project.block)}</small></td>
          <td><span class="level-pill ${levelClass(result.risk_level)}">${escapeHtml(result.risk_level)}</span><div class="score">${result.risk_score}/100</div></td>
          <td><div class="score">${result.fraud_score}/100</div></td>
          <td class="driver-list">${escapeHtml((result.top_drivers || []).join(", "))}</td>
          <td><button class="view-button" type="button" data-index="${index}">Explain</button></td>
        </tr>
      `;
    })
    .join("");

  projectTableBody.querySelectorAll(".view-button").forEach((button) => {
    button.addEventListener("click", () => {
      const result = filtered[Number(button.dataset.index)];
      openDrawer(result);
    });
  });
}

function openDrawer(result) {
  const { project } = result;
  const findings = [...(result.findings || [])].sort(
    (left, right) => (severityRank[right.severity] || 0) - (severityRank[left.severity] || 0),
  );

  drawerContent.innerHTML = `
    <span class="level-pill ${levelClass(result.risk_level)}">${escapeHtml(result.risk_level)} risk</span>
    <h2>${escapeHtml(project.project_name)}</h2>
    <p>${escapeHtml(project.project_id)} • ${escapeHtml(project.department)} • ${escapeHtml(project.district)}</p>

    <div class="drawer-section">
      <h3>AI explanation</h3>
      <p>${escapeHtml(result.explanation)}</p>
    </div>

    <div class="drawer-section">
      <h3>Risk signals</h3>
      ${findings.length ? findings.map(renderFinding).join("") : "<p>No major finding detected.</p>"}
    </div>

    <div class="drawer-section">
      <h3>Recommended officer actions</h3>
      <ol>${(result.recommendations || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ol>
    </div>

    <div class="drawer-section">
      <h3>Key metrics</h3>
      <div class="evidence">
        Sanctioned: ${formatCurrency(project.sanctioned_amount)}<br />
        Spent: ${formatCurrency(project.spent_amount)}<br />
        Physical progress: ${formatPercent(project.physical_progress_pct)}<br />
        Planned end: ${escapeHtml(project.planned_end_date || "Not available")}<br />
        Last updated: ${escapeHtml(project.last_updated || "Not available")}
      </div>
    </div>
  `;
  detailDrawer.classList.add("open");
  detailDrawer.setAttribute("aria-hidden", "false");
}

function renderFinding(finding) {
  return `
    <article class="finding-card">
      <strong>
        ${escapeHtml(finding.title)}
        <span class="severity-pill severity-${escapeHtml(finding.severity)}">${escapeHtml(finding.severity)}</span>
      </strong>
      <p>${escapeHtml(finding.message)}</p>
      <pre class="evidence">${escapeHtml(JSON.stringify(finding.evidence || {}, null, 2))}</pre>
    </article>
  `;
}

function closeDrawer() {
  detailDrawer.classList.remove("open");
  detailDrawer.setAttribute("aria-hidden", "true");
}

function updateFileName() {
  fileName.textContent = currentFile ? currentFile.name : "No file selected";
}

function showStatus(message, type) {
  statusPanel.hidden = false;
  statusPanel.textContent = message;
  statusPanel.className = `status-panel ${type}`;
}

function levelClass(level = "low") {
  return `level-${String(level).toLowerCase()}`;
}

function formatCurrency(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(Number(value));
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}
