// Authentication state
let authToken = null;
let currentUser = null;

// Elements
const loginScreen = document.getElementById("loginScreen");
const mainApp = document.getElementById("mainApp");
const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const userInfo = document.getElementById("userInfo");
const userInfo2 = document.getElementById("userInfo2");
const logoutBtn = document.getElementById("logoutBtn");
const logoutBtn2 = document.getElementById("logoutBtn2");

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
const transparencyContent = document.getElementById("transparencyContent");
const auditLogContent = document.getElementById("auditLogContent");

let currentReport = null;
let currentFile = null;

const severityRank = { low: 1, medium: 2, high: 3, critical: 4 };

// Check for existing session on page load
checkSession();

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
  
  // Auto-scroll to dashboard after rendering
  setTimeout(() => {
    dashboard.scrollIntoView({ behavior: "smooth", block: "start" });
  }, 100);
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
        <strong>Financial:</strong><br />
        Sanctioned: ${formatCurrency(project.sanctioned_amount)}<br />
        Spent: ${formatCurrency(project.spent_amount)}<br />
        Physical progress: ${formatPercent(project.physical_progress_pct)}<br />
        <br />
        <strong>Timeline:</strong><br />
        Start date: ${formatDate(project.start_date)}<br />
        Planned end: ${formatDate(project.planned_end_date)}<br />
        Actual end: ${formatDate(project.actual_end_date)}<br />
        Last updated: ${formatDate(project.last_updated)}<br />
        <br />
        <strong>Project Details:</strong><br />
        Status: ${escapeHtml(project.status)}<br />
        Contractor: ${escapeHtml(project.contractor)}<br />
        Block: ${escapeHtml(project.block)}
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
  
  const num = Number(value);
  
  // If the number is less than 1000, it's likely already in Crore from the CSV
  // (e.g., 15.5 means 15.5 Crore, not 15.5 rupees)
  if (num < 1000 && num > 0) {
    return `₹${num.toFixed(2)} Crore`;
  }
  
  // Format based on magnitude for larger numbers
  if (num >= 10000000) {
    // Crore (1 crore = 10,000,000)
    return `₹${(num / 10000000).toFixed(2)} Crore`;
  } else if (num >= 100000) {
    // Lakh (1 lakh = 100,000)
    return `₹${(num / 100000).toFixed(2)} Lakh`;
  } else if (num >= 1000) {
    // Thousand
    return `₹${(num / 1000).toFixed(2)} Thousand`;
  } else {
    // Less than thousand - show as Crore for project amounts
    return `₹${num.toFixed(2)} Crore`;
  }
}

function formatPercent(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return "N/A";
  return `${Number(value).toFixed(1)}%`;
}

function formatDate(value) {
  if (!value || value === "Not available" || value === "Unknown" || value === null) {
    return "Not available";
  }
  try {
    const date = new Date(value);
    if (isNaN(date.getTime())) return "Not available";
    return date.toLocaleDateString("en-IN", { 
      year: "numeric", 
      month: "short", 
      day: "numeric" 
    });
  } catch {
    return "Not available";
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}


// ==================== Authentication ====================

function checkSession() {
  // Don't auto-login on page load - always show login screen
  // This ensures fresh authentication on each browser session
  showLoginScreen();
  
  // Clear any old session data
  localStorage.removeItem("authToken");
  localStorage.removeItem("currentUser");
}

function showLoginScreen() {
  if (loginScreen) loginScreen.hidden = false;
  if (mainApp) mainApp.hidden = true;
}

function showMainApp() {
  if (loginScreen) loginScreen.hidden = true;
  if (mainApp) mainApp.hidden = false;
  updateUserDisplay();
  loadTransparencyData();

  // Scalability telemetry: first sample immediately, then every 3 seconds
  loadScalability(true);
  startScalabilityAutoRefresh();

  // Auto-load audit log for admins
  if (currentUser && currentUser.role === 'admin') {
    loadAuditLog();
  }
  
  // Automatically scroll to upload panel after login
  setTimeout(() => {
    const uploadPanel = document.getElementById("upload-panel");
    if (uploadPanel) {
      uploadPanel.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, 100);
}

function updateUserDisplay() {
  if (currentUser) {
    const displayText = `${currentUser.full_name} (${currentUser.role})`;
    if (userInfo) userInfo.textContent = displayText;
    if (userInfo2) userInfo2.textContent = displayText;
  }
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  
  const username = document.getElementById("username").value;
  const password = document.getElementById("password").value;
  
  try {
    loginError.hidden = true;
    
    const response = await fetch("/api/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    
    const data = await response.json();
    
    if (!response.ok) {
      throw new Error(data.error || "Login failed");
    }
    
    authToken = data.token;
    currentUser = data.user;
    
    // Don't save to localStorage - require login each time for security
    // localStorage.setItem("authToken", authToken);
    // localStorage.setItem("currentUser", JSON.stringify(currentUser));
    
    showMainApp();
    
  } catch (error) {
    loginError.textContent = error.message;
    loginError.hidden = false;
  }
});

logoutBtn.addEventListener("click", handleLogout);
if (logoutBtn2) logoutBtn2.addEventListener("click", handleLogout);

function handleLogout() {
  authToken = null;
  currentUser = null;

  // Stop polling the scalability telemetry for the signed-out session
  stopScalabilityAutoRefresh();
  scalData = null;
  
  // Clear any session data
  localStorage.removeItem("authToken");
  localStorage.removeItem("currentUser");
  
  showLoginScreen();
  
  // Reset form and state
  loginForm.reset();
  dashboard.hidden = true;
  statusPanel.hidden = true;
  currentReport = null;
  currentFile = null;
}

// ==================== Model Transparency ====================

async function loadTransparencyData() {
  try {
    const response = await fetch("/api/model-transparency", {
      headers: {
        "Authorization": `Bearer ${authToken}`
      }
    });
    
    if (!response.ok) throw new Error("Failed to load transparency data");
    
    const data = await response.json();
    renderTransparencyData(data);
    
  } catch (error) {
    transparencyContent.innerHTML = `<p class="error">Failed to load model documentation: ${error.message}</p>`;
  }
}

function renderTransparencyData(data) {
  transparencyContent.innerHTML = `
    <div class="model-section">
      <h3>${escapeHtml(data.model_name)}</h3>
      <p><strong>Type:</strong> ${escapeHtml(data.model_type)}</p>
      <p>${escapeHtml(data.description)}</p>
      
      <div class="model-info">
        <strong>Score Range:</strong> ${escapeHtml(data.total_score_range)}
      </div>
    </div>

    <div class="model-section">
      <h3>Risk Score Components</h3>
      <div class="component-list">
        ${data.risk_components.map(comp => `
          <div class="component-card">
            <div class="component-header">
              <h4>${escapeHtml(comp.component)}</h4>
              <span class="weight-badge">Weight: ${comp.weight}%</span>
            </div>
            <p>${escapeHtml(comp.description)}</p>
            <div class="formula-box">${escapeHtml(comp.formula)}</div>
            <div class="threshold-grid">
              ${Object.entries(comp.thresholds).map(([level, value]) => `
                <div class="threshold-item ${level}">
                  <strong>${level}</strong>
                  <span>${escapeHtml(value)}</span>
                </div>
              `).join('')}
            </div>
            <p><strong>Points:</strong> ${escapeHtml(comp.points_awarded)}</p>
          </div>
        `).join('')}
      </div>
    </div>

    <div class="model-section">
      <h3>Fraud Score Components</h3>
      <div class="component-list">
        ${data.fraud_score_components.map(comp => `
          <div class="component-card">
            <h4>${escapeHtml(comp.component)}</h4>
            <p>${escapeHtml(comp.description)}</p>
            <div class="points">${comp.points} points</div>
          </div>
        `).join('')}
      </div>
    </div>

    <div class="model-section">
      <h3>Risk Level Classification</h3>
      <div class="threshold-grid">
        ${Object.entries(data.risk_level_classification).map(([level, range]) => `
          <div class="threshold-item ${level.toLowerCase()}">
            <strong>${level}</strong>
            <span>${escapeHtml(range)}</span>
          </div>
        `).join('')}
      </div>
    </div>

    <div class="model-section">
      <h3>Key Principles</h3>
      <div class="principle-list">
        ${data.key_principles.map(principle => `
          <div class="principle-item">${escapeHtml(principle)}</div>
        `).join('')}
      </div>
    </div>

    <div class="example-card">
      <h4>Example Calculation</h4>
      <p><strong>Scenario:</strong> Road construction project with cost overrun and delay</p>
      <div class="calculation-steps">
        <div class="calculation-step">
          <span>Cost overrun of 36%</span>
          <span class="points">25 points</span>
        </div>
        <div class="calculation-step">
          <span>Schedule delay of 120 days</span>
          <span class="points">10 points</span>
        </div>
        <div class="calculation-step">
          <span>Stale reporting (45 days)</span>
          <span class="points">8 points</span>
        </div>
        <div class="calculation-step">
          <strong>Total Risk Score</strong>
          <span class="points">43/100 (Medium Risk)</span>
        </div>
      </div>
    </div>
  `;
}

// Load audit log
async function loadAuditLog() {
  if (!currentUser || currentUser.role !== 'admin') {
    auditLogContent.innerHTML = `<p>Audit log is only available to administrators.</p>`;
    return;
  }

  try {
    const response = await fetch("/api/audit-log?limit=50", {
      headers: {
        "Authorization": `Bearer ${authToken}`
      }
    });
    
    if (!response.ok) throw new Error("Failed to load audit log");
    
    const logs = await response.json();
    renderAuditLog(logs);
    
  } catch (error) {
    auditLogContent.innerHTML = `<p class="error">Failed to load audit log: ${error.message}</p>`;
  }
}

function renderAuditLog(logs) {
  if (!logs.length) {
    auditLogContent.innerHTML = `<p>No audit log entries found.</p>`;
    return;
  }

  auditLogContent.innerHTML = `
    <div class="audit-table">
      <table>
        <thead>
          <tr>
            <th>Timestamp</th>
            <th>User</th>
            <th>Action</th>
            <th>Resource</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          ${logs.map(log => `
            <tr>
              <td>${new Date(log.timestamp).toLocaleString()}</td>
              <td>${escapeHtml(log.username || 'System')}</td>
              <td><span class="action-badge ${log.action.toLowerCase()}">${escapeHtml(log.action)}</span></td>
              <td>${escapeHtml(log.resource || '-')}</td>
              <td>${escapeHtml(log.details || '-')}</td>
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

// Navigation
document.getElementById("navAudit").addEventListener("click", (e) => {
  e.preventDefault();
  loadAuditLog();
  document.getElementById("audit-log").scrollIntoView({ behavior: "smooth" });
});

document.getElementById("navTransparency").addEventListener("click", (e) => {
  e.preventDefault();
  document.getElementById("transparency").scrollIntoView({ behavior: "smooth" });
});

// ==================== Modified Upload with Auth ====================

async function analyzeFile(file) {
  if (!authToken) {
    showStatus("Please login first.", "error");
    return;
  }

  showStatus("AI engine is cleaning data, detecting anomalies and generating explanations...", "loading");
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch("/api/analyze", {
    method: "POST",
    headers: {
      "Authorization": `Bearer ${authToken}`
    },
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



// ==================== CHATBOT FUNCTIONALITY ====================

const chatbotToggle = document.getElementById("chatbotToggle");
const chatbotWindow = document.getElementById("chatbotWindow");
const chatbotBackdrop = document.getElementById("chatbotBackdrop");
const chatbotClose = document.getElementById("chatbotClose");
const chatbotMessages = document.getElementById("chatbotMessages");
const chatbotInput = document.getElementById("chatbotInput");
const chatbotSend = document.getElementById("chatbotSend");
const quickActions = document.getElementById("quickActions");

let chatbotOpen = false;

// Toggle chatbot window
function toggleChatbot() {
  chatbotOpen = !chatbotOpen;
  chatbotWindow.classList.toggle("open", chatbotOpen);
  chatbotBackdrop.classList.toggle("open", chatbotOpen);
  chatbotToggle.classList.toggle("open", chatbotOpen);
  
  if (chatbotOpen) {
    chatbotInput.focus();
    // Show welcome message if no messages yet
    if (chatbotMessages.children.length === 0) {
      sendChatbotMessage("", true);
    }
  }
}

// Add message to chat
function addChatMessage(message, isUser = false) {
  const messageDiv = document.createElement("div");
  messageDiv.className = `chatbot-message ${isUser ? "user" : "bot"}`;
  
  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  
  // Convert markdown-style formatting to HTML
  let formattedMessage = message
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")  // Bold
    .replace(/```(.*?)```/gs, "<pre>$1</pre>")  // Code blocks
    .replace(/•/g, "•")  // Bullet points
    .replace(/\n/g, "<br>");  // Line breaks
  
  bubble.innerHTML = formattedMessage;
  messageDiv.appendChild(bubble);
  chatbotMessages.appendChild(messageDiv);
  
  // Scroll to bottom
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

// Show typing indicator
function showTypingIndicator() {
  const typingDiv = document.createElement("div");
  typingDiv.className = "chatbot-message bot";
  typingDiv.id = "typingIndicator";
  
  const typingBubble = document.createElement("div");
  typingBubble.className = "chatbot-typing";
  typingBubble.innerHTML = `
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
    <span class="typing-dot"></span>
  `;
  
  typingDiv.appendChild(typingBubble);
  chatbotMessages.appendChild(typingDiv);
  chatbotMessages.scrollTop = chatbotMessages.scrollHeight;
}

// Remove typing indicator
function removeTypingIndicator() {
  const indicator = document.getElementById("typingIndicator");
  if (indicator) {
    indicator.remove();
  }
}

// Send message to chatbot API
async function sendChatbotMessage(query, isInitial = false) {
  if (!isInitial && query.trim()) {
    addChatMessage(query, true);
    chatbotInput.value = "";
  }
  
  showTypingIndicator();
  chatbotSend.disabled = true;
  
  try {
    const response = await fetch("/api/chatbot", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${localStorage.getItem("authToken") || ""}`,
      },
      body: JSON.stringify({
        query: query,
        context: {}
      }),
    });
    
    removeTypingIndicator();
    
    if (!response.ok) {
      if (response.status === 401) {
        addChatMessage("⚠️ Please login to use the chatbot.", false);
        return;
      }
      throw new Error(`HTTP ${response.status}`);
    }
    
    const data = await response.json();
    addChatMessage(data.response, false);
    
  } catch (error) {
    removeTypingIndicator();
    console.error("Chatbot error:", error);
    addChatMessage("❌ Sorry, I encountered an error. Please try again or check your connection.", false);
  } finally {
    chatbotSend.disabled = false;
  }
}

// Event listeners
chatbotToggle.addEventListener("click", toggleChatbot);
chatbotClose.addEventListener("click", toggleChatbot);
chatbotBackdrop.addEventListener("click", toggleChatbot);

chatbotSend.addEventListener("click", () => {
  const query = chatbotInput.value.trim();
  if (query) {
    sendChatbotMessage(query);
  }
});

chatbotInput.addEventListener("keypress", (e) => {
  if (e.key === "Enter") {
    const query = chatbotInput.value.trim();
    if (query) {
      sendChatbotMessage(query);
    }
  }
});

// Quick action buttons
quickActions.addEventListener("click", (e) => {
  if (e.target.classList.contains("quick-action-btn")) {
    const query = e.target.dataset.query;
    if (query) {
      chatbotInput.value = query;
      sendChatbotMessage(query);
    }
  }
});


// ==================== Scalability & Traffic Control ====================
// Live fleet telemetry, load-balancer view, traffic-control policy and the
// built-in load generator. Every number comes from /api/scalability, which is
// aggregated from the real request path of each replica.

const scalSummary = document.getElementById("scalSummary");
const scalBanner = document.getElementById("scalBanner");
const scalNodes = document.getElementById("scalNodes");
const scalChart = document.getElementById("scalChart");
const scalLegend = document.getElementById("scalChartLegend");
const scalRecommendation = document.getElementById("scalRecommendation");
const scalRequests = document.getElementById("scalRequests");
const scalEvents = document.getElementById("scalEvents");
const scalEnforcement = document.getElementById("scalEnforcement");
const scalUpdated = document.getElementById("scalUpdated");
const scalLiveDot = document.getElementById("scalLiveDot");
const scalAutoRefresh = document.getElementById("scalAutoRefresh");
const scalRefreshBtn = document.getElementById("scalRefreshBtn");
const scalLbBadge = document.getElementById("scalLbBadge");
const scalTopologyText = document.getElementById("scalTopologyText");
const scalFeedMeta = document.getElementById("scalFeedMeta");
const policyRoleBadge = document.getElementById("policyRoleBadge");
const policyFeedback = document.getElementById("policyFeedback");
const applyPolicyBtn = document.getElementById("applyPolicyBtn");
const flushCacheBtn = document.getElementById("flushCacheBtn");
const resetMetricsBtn = document.getElementById("resetMetricsBtn");
const runLoadTestBtn = document.getElementById("runLoadTestBtn");
const ltResult = document.getElementById("ltResult");

const POLICY_FIELDS = {
  rate_limit_rps: "policyRps",
  rate_limit_burst: "policyBurst",
  max_concurrent: "policyMaxConcurrent",
  lb_algorithm: "policyLbAlgorithm",
  autoscale_target_p95_ms: "policyTargetP95",
  autoscale_rps_per_node: "policyRpsPerNode",
  autoscale_min_nodes: "policyMinNodes",
  autoscale_max_nodes: "policyMaxNodes",
  rate_limit_enabled: "policyRateEnabled",
  load_shed_enabled: "policyShed",
  autoscale_enabled: "policyAutoscale",
};

const POLICY_PRESETS = {
  demo: {
    label: "Hackathon demo",
    values: { rate_limit_enabled: true, rate_limit_rps: 25, rate_limit_burst: 60, max_concurrent: 64, load_shed_enabled: true, autoscale_enabled: true, autoscale_target_p95_ms: 250, autoscale_rps_per_node: 40, autoscale_min_nodes: 2, autoscale_max_nodes: 12, lb_algorithm: "least_conn" },
  },
  district: {
    label: "District pilot",
    values: { rate_limit_enabled: true, rate_limit_rps: 150, rate_limit_burst: 400, max_concurrent: 160, load_shed_enabled: true, autoscale_enabled: true, autoscale_target_p95_ms: 300, autoscale_rps_per_node: 120, autoscale_min_nodes: 3, autoscale_max_nodes: 8, lb_algorithm: "least_conn" },
  },
  state: {
    label: "State scale",
    values: { rate_limit_enabled: true, rate_limit_rps: 800, rate_limit_burst: 2000, max_concurrent: 512, load_shed_enabled: true, autoscale_enabled: true, autoscale_target_p95_ms: 400, autoscale_rps_per_node: 400, autoscale_min_nodes: 6, autoscale_max_nodes: 40, lb_algorithm: "round_robin" },
  },
  lockdown: {
    label: "Under attack",
    values: { rate_limit_enabled: true, rate_limit_rps: 8, rate_limit_burst: 16, max_concurrent: 32, load_shed_enabled: true, autoscale_enabled: true, autoscale_target_p95_ms: 200, autoscale_rps_per_node: 40, autoscale_min_nodes: 4, autoscale_max_nodes: 20, lb_algorithm: "ip_hash" },
  },
};

let scalData = null;
let scalTimer = null;
let scalLastSuccess = 0;
let scalBusy = false;

const LB_LABELS = {
  round_robin: "round robin",
  least_conn: "least connections",
  ip_hash: "ip hash (sticky)",
  weighted: "weighted",
};

function isAdmin() {
  return Boolean(currentUser && currentUser.role === "admin");
}

async function loadScalability(showErrors = false) {
  if (!authToken || scalBusy) return;
  scalBusy = true;
  try {
    const response = await fetch("/api/scalability", {
      headers: { "Authorization": `Bearer ${authToken}` },
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    scalData = await response.json();
    scalLastSuccess = Date.now();
    renderScalability(scalData);
    scalLiveDot.className = "live-dot";
    scalLiveDot.title = "Live - auto-refreshing";
  } catch (error) {
    if (showErrors || !scalData) {
      scalLiveDot.className = "live-dot error";
      scalLiveDot.title = `Telemetry unavailable: ${error.message}`;
      scalUpdated.textContent = `Telemetry unavailable (${error.message})`;
    }
  } finally {
    scalBusy = false;
  }
}

function scalPctClass(value, warnAt, badAt) {
  if (value >= badAt) return "metric-bad";
  if (value >= warnAt) return "metric-warn";
  return "metric-good";
}

function renderScalability(data) {
  const cluster = data.cluster;
  const local = data.metrics;
  const policy = data.traffic_control;
  const assets = data.caches.static_assets;
  const analysis = data.caches.analysis_results;
  const rec = data.recommendation;

  scalUpdated.textContent =
    `Live · updated ${new Date().toLocaleTimeString()} · this replica ${data.instance.instance_id} · ` +
    `${cluster.nodes_healthy}/${cluster.nodes_total} replicas healthy`;
  scalFeedMeta.textContent = `${data.instance.instance_id} · last ${local.recent_requests.length} requests`;

  const cards = [
    {
      label: "Replicas healthy",
      value: `${cluster.nodes_healthy} / ${cluster.nodes_total}`,
      sub: cluster.nodes_down ? `${cluster.nodes_down} replica(s) failing health checks` : "all health checks passing",
      cls: cluster.nodes_down ? "metric-bad" : "metric-good",
    },
    {
      label: "Fleet throughput",
      value: `${cluster.requests_per_sec.toFixed(1)} req/s`,
      sub: `${cluster.requests_total.toLocaleString()} requests served · this replica ${local.requests_per_sec.toFixed(1)} req/s`,
      cls: "metric-good",
    },
    {
      label: "p95 latency (fleet)",
      value: `${cluster.p95_ms.toFixed(0)} ms`,
      sub: `target ${policy.autoscale_target_p95_ms.toFixed(0)} ms · p99 ${local.latency.p99_ms.toFixed(0)} ms local`,
      cls: cluster.p95_ms > policy.autoscale_target_p95_ms ? "metric-warn" : "metric-good",
    },
    {
      label: "Concurrency",
      value: `${cluster.in_flight} / ${cluster.capacity_concurrent}`,
      sub: `fleet saturation ${cluster.saturation_pct.toFixed(1)}% · ceiling ${policy.max_concurrent}/node`,
      cls: scalPctClass(cluster.saturation_pct, 55, 80),
    },
    {
      label: "Throttled (429)",
      value: cluster.throttled_total.toLocaleString(),
      sub: `${cluster.shed_total.toLocaleString()} shed (503) · limit ${policy.rate_limit_rps.toFixed(0)} req/s/ip`,
      cls: cluster.throttled_total ? "metric-warn" : "metric-good",
    },
    {
      label: "Cache hit ratio",
      value: `${(assets.hit_ratio * 100).toFixed(1)}%`,
      sub: `${assets.hits.toLocaleString()} asset hits · analysis cache ${(analysis.hit_ratio * 100).toFixed(0)}% (${analysis.hits}/${analysis.hits + analysis.misses})`,
      cls: "metric-good",
    },
    {
      label: "Errors (5xx)",
      value: cluster.server_errors_total.toLocaleString(),
      sub: `error rate ${(local.error_rate * 100).toFixed(2)}% on this replica`,
      cls: cluster.server_errors_total ? "metric-bad" : "metric-good",
    },
    {
      label: "Autoscaler",
      value: rec.action === "scale_out" ? `scale out → ${rec.desired_nodes}` : rec.action === "scale_in" ? `scale in → ${rec.desired_nodes}` : `hold at ${rec.desired_nodes}`,
      sub: `utilisation ${(rec.utilisation * 100).toFixed(0)}% of policy target`,
      cls: rec.action === "scale_out" ? "metric-warn" : rec.action === "scale_in" ? "metric-warn" : "metric-good",
    },
  ];

  scalSummary.innerHTML = cards.map(card => `
    <article class="summary-card">
      <span>${escapeHtml(card.label)}</span>
      <strong>${escapeHtml(card.value)}</strong>
      <span class="metric-sub ${card.cls}">${escapeHtml(card.sub)}</span>
    </article>
  `).join("");

  scalLbBadge.textContent = LB_LABELS[policy.lb_algorithm] || policy.lb_algorithm;
  const topology = data.topology;
  scalTopologyText.innerHTML =
    `Edge tier: <strong>${escapeHtml(topology.proxy_layer_label)}</strong> · ` +
    `balancing policy <strong>${escapeHtml(LB_LABELS[policy.lb_algorithm] || policy.lb_algorithm)}</strong> · ` +
    `proxied requests seen: ${local.proxied_requests.toLocaleString()} ` +
    `(the app reads <code>X-Forwarded-For</code> so per-client limits stay accurate behind a proxy).`;

  renderScalNodes(cluster);
  renderScalChart(cluster.series);
  renderScalRecommendation(rec, cluster);
  renderScalEnforcement(topology.enforcement_chain);
  renderScalRequests(local.recent_requests);
  renderScalEvents(data.events);
  renderScalBanner(data);
  fillPolicyForm(policy, data.instance.instance_id);
}

function renderScalNodes(cluster) {
  const rows = cluster.nodes.map(node => {
    const status = node.status === "healthy" ? "status-healthy" : node.status === "down" ? "status-down" : "status-unknown";
    const uptime = node.uptime_seconds ? `${Math.floor(node.uptime_seconds / 60)}m ${Math.round(node.uptime_seconds % 60)}s` : "-";
    const p95 = node.p95_ms ? `${node.p95_ms.toFixed(0)} ms` : "-";
    const satClass = scalPctClass(node.saturation_pct, 55, 80);
    return `
      <tr>
        <td>
          <span class="node-name">${escapeHtml(node.instance_id)}${node.is_self ? '<span class="node-self">this node</span>' : ""}</span>
          <span class="share-label">${escapeHtml(node.url || "-")}${node.error ? ` · ${escapeHtml(String(node.error).slice(0, 48))}` : ""}</span>
        </td>
        <td><span class="status-pill ${status}">${escapeHtml(node.status)}</span></td>
        <td>
          <div class="share-track"><div class="share-fill" style="width:${Math.min(node.traffic_share_pct, 100)}%"></div></div>
          <span class="share-label">${node.traffic_share_pct.toFixed(1)}% · ${node.requests_total.toLocaleString()} req</span>
        </td>
        <td>${node.requests_per_sec.toFixed(1)}</td>
        <td>${p95}</td>
        <td><span class="${satClass}">${node.in_flight} / ${node.max_concurrent}</span></td>
        <td>${escapeHtml(uptime)}</td>
      </tr>
    `;
  });
  scalNodes.innerHTML = rows.join("") || `<tr><td colspan="7">No replicas reported.</td></tr>`;
}

function renderScalBanner(data) {
  const cluster = data.cluster;
  const rec = data.recommendation;
  const messages = [];
  let level = "info";

  if (cluster.nodes_down > 0) {
    level = "danger";
    messages.push(`${cluster.nodes_down} replica(s) failing the health probe - the balancer has taken them out of rotation.`);
  }
  if (cluster.saturation_pct >= 80) {
    level = "danger";
    messages.push(`Fleet saturation ${cluster.saturation_pct.toFixed(0)}% - requests will start being shed (503) at ${data.traffic_control.max_concurrent} concurrent per node.`);
  }
  if (cluster.throttled_total > 0) {
    if (level !== "danger") level = "";
    messages.push(`${cluster.throttled_total.toLocaleString()} request(s) throttled by the per-client token bucket (HTTP 429).`);
  }
  if (cluster.p95_ms > data.traffic_control.autoscale_target_p95_ms) {
    if (level !== "danger") level = "";
    messages.push(`p95 ${cluster.p95_ms.toFixed(0)} ms is above the ${data.traffic_control.autoscale_target_p95_ms.toFixed(0)} ms target - see the autoscaler recommendation.`);
  }
  if (rec.action !== "hold") {
    messages.push(`${rec.action === "scale_out" ? "Scale out" : "Scale in"} recommended: ${rec.desired_nodes} replicas. ${rec.reason}`);
  }

  if (!messages.length) {
    scalBanner.hidden = true;
    scalBanner.textContent = "";
    return;
  }
  scalBanner.hidden = false;
  scalBanner.className = `scal-banner ${level}`.trim();
  scalBanner.textContent = messages.join(" ");
}

function renderScalRecommendation(rec, cluster) {
  scalRecommendation.className = `recommendation-card ${rec.action}`;
  scalRecommendation.innerHTML = `
    <strong>Autoscaler: ${escapeHtml(rec.action.replace("_", " "))} → ${rec.desired_nodes} replica(s)</strong>
    ${escapeHtml(rec.reason)}
    <div class="metric-sub">
      Policy: scale out when p95 &gt; ${rec.target_p95_ms.toFixed(0)} ms or throughput &gt; ${rec.capacity_rps.toFixed(0)} req/s per replica ·
      current ${cluster.requests_per_sec.toFixed(1)} req/s over ${cluster.nodes_healthy} replica(s)
    </div>
  `;
}

function renderScalEnforcement(chain) {
  scalEnforcement.innerHTML = chain.map(layer => `
    <tr>
      <td><strong>${escapeHtml(layer.layer)}</strong></td>
      <td>${escapeHtml(layer.what)}</td>
      <td><code>${escapeHtml(layer.where)}</code></td>
      <td><span class="status-pill ${layer.status === "active" ? "status-healthy" : "status-unknown"}">${escapeHtml(layer.status)}</span></td>
    </tr>
  `).join("");
}

function renderScalRequests(requests) {
  const ordered = [...requests].reverse();
  if (!ordered.length) {
    scalRequests.innerHTML = `<tr><td colspan="8">No requests recorded yet.</td></tr>`;
    return;
  }
  scalRequests.innerHTML = ordered.map(item => {
    const statusClass = item.status >= 500 ? "status-5xx" : item.status === 429 ? "status-429" : item.status >= 400 ? "status-4xx" : "status-2xx";
    return `
      <tr>
        <td>${escapeHtml(item.time)}</td>
        <td>${escapeHtml(item.method)}</td>
        <td><code>${escapeHtml(item.path)}</code></td>
        <td><span class="status-chip ${statusClass}">${item.status}</span></td>
        <td>${item.latency_ms.toFixed(1)} ms</td>
        <td>${escapeHtml(item.node)}</td>
        <td>${escapeHtml(item.decision)}</td>
        <td>${escapeHtml(item.client)}</td>
      </tr>
    `;
  }).join("");
}

function renderScalEvents(events) {
  const ordered = [...events].reverse();
  if (!ordered.length) {
    scalEvents.innerHTML = `<p class="panel-note">No scaling or traffic-control events yet.</p>`;
    return;
  }
  scalEvents.innerHTML = ordered.map(event => `
    <div class="event-item ${escapeHtml(event.level)}">
      <div class="event-head">
        <span>${escapeHtml(event.kind)}</span>
        <span>${escapeHtml(event.time)}</span>
      </div>
      <div class="event-message">${escapeHtml(event.message)}</div>
    </div>
  `).join("");
}

function renderScalChart(series) {
  if (!scalChart || !series.length) return;
  const ctx = scalChart.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const width = scalChart.clientWidth || 720;
  const height = 260;
  scalChart.width = width * dpr;
  scalChart.height = height * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);

  const padLeft = 44;
  const padRight = 44;
  const padTop = 18;
  const padBottom = 26;
  const plotW = width - padLeft - padRight;
  const plotH = height - padTop - padBottom;

  const maxRps = Math.max(10, ...series.map(point => point.requests));
  const maxMs = Math.max(20, ...series.map(point => point.avg_ms));
  const step = plotW / Math.max(series.length, 1);

  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  ctx.font = "11px Inter, sans-serif";
  ctx.fillStyle = "#667085";
  for (let i = 0; i <= 4; i += 1) {
    const y = padTop + (plotH / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padLeft, y);
    ctx.lineTo(width - padRight, y);
    ctx.stroke();
    ctx.fillText(String(Math.round(maxRps - (maxRps / 4) * i)), 8, y + 4);
  }

  series.forEach((point, index) => {
    const x = padLeft + index * step;
    const barH = (point.requests / maxRps) * plotH;
    ctx.fillStyle = "#2154d4";
    ctx.globalAlpha = 0.85;
    ctx.fillRect(x + 1, padTop + plotH - barH, Math.max(step - 2, 1), barH);
    ctx.globalAlpha = 1;

    if (point.limited) {
      const limH = (point.limited / maxRps) * plotH;
      ctx.fillStyle = "#e11d48";
      ctx.fillRect(x + 1, padTop + plotH - limH, Math.max(step - 2, 1), limH);
    }
  });

  ctx.strokeStyle = "#14b8a6";
  ctx.lineWidth = 2;
  ctx.beginPath();
  series.forEach((point, index) => {
    const x = padLeft + index * step + step / 2;
    const y = padTop + plotH - (point.avg_ms / maxMs) * plotH;
    if (index === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  });
  ctx.stroke();

  ctx.fillStyle = "#667085";
  for (let i = 0; i < series.length; i += 10) {
    const point = series[i];
    ctx.fillText(point.time.slice(0, 5), padLeft + i * step, height - 8);
  }
  ctx.fillText(`${maxMs.toFixed(0)}ms`, width - padRight + 6, padTop + 6);

  scalLegend.innerHTML = `
    <span class="legend-key"><span class="legend-swatch" style="background:#2154d4"></span>requests/s (peak ${maxRps.toFixed(0)})</span>
    <span class="legend-key"><span class="legend-swatch" style="background:#e11d48"></span>throttled/shed</span>
    <span class="legend-key"><span class="legend-swatch" style="background:#14b8a6"></span>avg latency (peak ${maxMs.toFixed(0)} ms)</span>
  `;
}

// ---------------- Traffic control policy ----------------

function fillPolicyForm(policy, instanceId) {
  Object.entries(POLICY_FIELDS).forEach(([key, elementId]) => {
    const element = document.getElementById(elementId);
    if (!element || element === document.activeElement) return;
    if (element.type === "checkbox") element.checked = Boolean(policy[key]);
    else element.value = policy[key];
  });

  const admin = isAdmin();
  policyRoleBadge.textContent = admin ? `${currentUser.role} · can change` : `${currentUser ? currentUser.role : "guest"} · read-only`;
  [applyPolicyBtn, flushCacheBtn, resetMetricsBtn, runLoadTestBtn].forEach(button => {
    if (!button) return;
    button.disabled = !admin;
    button.title = admin ? "" : "Only administrators can change traffic control or run load tests.";
  });
  document.querySelectorAll(".chip-button[data-preset]").forEach(button => {
    button.disabled = !admin;
  });
}

function collectPolicyValues() {
  const payload = {};
  Object.entries(POLICY_FIELDS).forEach(([key, elementId]) => {
    const element = document.getElementById(elementId);
    if (!element) return;
    if (element.type === "checkbox") payload[key] = element.checked;
    else if (element.tagName === "SELECT") payload[key] = element.value;
    else payload[key] = Number(element.value);
  });
  return payload;
}

function showPolicyFeedback(message, isError = false) {
  if (!policyFeedback) return;
  policyFeedback.hidden = false;
  policyFeedback.innerHTML = message;
  policyFeedback.style.color = isError ? "var(--danger)" : "var(--success)";
}

async function postJson(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Authorization": `Bearer ${authToken}`,
    },
    body: JSON.stringify(body || {}),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || payload.message || `HTTP ${response.status}`);
  return payload;
}

async function applyTrafficPolicy(values, label) {
  try {
    const result = await postJson("/api/traffic-control", values);
    const changed = Object.keys(result.applied || {});
    showPolicyFeedback(
      changed.length
        ? `${label || "Policy"} applied on ${result.instance_id}: ${changed.map(key => `${key}=${result.applied[key]}`).join(", ")}. Audit log updated.`
        : `${label || "Policy"} submitted - no value changed.`
    );
    await loadScalability(true);
  } catch (error) {
    showPolicyFeedback(`Could not apply policy: ${error.message}`, true);
  }
}

if (applyPolicyBtn) {
  applyPolicyBtn.addEventListener("click", () => applyTrafficPolicy(collectPolicyValues(), "Custom policy"));
}

document.querySelectorAll(".chip-button[data-preset]").forEach(button => {
  button.addEventListener("click", () => {
    if (!isAdmin()) {
      showPolicyFeedback("Only administrators can apply a traffic profile.", true);
      return;
    }
    const preset = POLICY_PRESETS[button.dataset.preset];
    if (!preset) return;
    Object.entries(preset.values).forEach(([key, value]) => {
      const element = document.getElementById(POLICY_FIELDS[key]);
      if (!element) return;
      if (element.type === "checkbox") element.checked = Boolean(value);
      else element.value = value;
    });
    applyTrafficPolicy(preset.values, `${preset.label} profile`);
  });
});

if (flushCacheBtn) {
  flushCacheBtn.addEventListener("click", async () => {
    try {
      const result = await postJson("/api/cache/flush", {});
      showPolicyFeedback(`Flushed ${result.assets_removed} cached assets on ${result.instance_id}. Next page load repopulates the cache.`);
      await loadScalability(true);
    } catch (error) {
      showPolicyFeedback(`Cache flush failed: ${error.message}`, true);
    }
  });
}

if (resetMetricsBtn) {
  resetMetricsBtn.addEventListener("click", async () => {
    try {
      const result = await postJson("/api/metrics/reset", {});
      showPolicyFeedback(`Counters reset on ${result.instance_id}. Run a load test to fill the window again.`);
      await loadScalability(true);
    } catch (error) {
      showPolicyFeedback(`Reset failed: ${error.message}`, true);
    }
  });
}

// ---------------- Built-in load test ----------------

if (runLoadTestBtn) {
  runLoadTestBtn.addEventListener("click", async () => {
    if (!isAdmin()) {
      renderLoadTestError("Only administrators can run a load test.");
      return;
    }
    const payload = {
      scope: document.getElementById("ltScope").value,
      mode: document.getElementById("ltMode").value,
      concurrency: Number(document.getElementById("ltConcurrency").value),
      duration_seconds: Number(document.getElementById("ltDuration").value),
      path: document.getElementById("ltPath").value,
    };
    runLoadTestBtn.disabled = true;
    runLoadTestBtn.textContent = `Running ${payload.duration_seconds}s…`;
    ltResult.hidden = false;
    ltResult.innerHTML = `<p class="panel-note">Driving ${payload.concurrency} virtual users at ${escapeHtml(payload.path)} for ${payload.duration_seconds}s…</p>`;
    try {
      const result = await postJson("/api/load-test", payload);
      renderLoadTestResult(result);
      await loadScalability(true);
    } catch (error) {
      renderLoadTestError(error.message);
    } finally {
      runLoadTestBtn.disabled = false;
      runLoadTestBtn.textContent = "Run load test";
    }
  });
}

function renderLoadTestError(message) {
  ltResult.hidden = false;
  ltResult.innerHTML = `<p class="scal-error">Load test failed: ${escapeHtml(message)}</p>`;
}

function renderLoadTestResult(result) {
  const sc = result.status_counts || {};
  const statusLine = Object.entries(sc).map(([code, count]) => `<span class="status-chip ${code === "200" ? "status-2xx" : code === "429" ? "status-429" : code === "503" ? "status-5xx" : "status-4xx"}">${code}: ${count}</span>`).join(" ");
  const dist = (result.node_distribution || []).map(node => `
    <div class="node-dist-row">
      <span>${escapeHtml(node.node)}</span>
      <div class="dist-track"><div class="dist-fill" style="width:${Math.min(node.share_pct, 100)}%"></div></div>
      <span>${node.share_pct.toFixed(1)}%</span>
    </div>
  `).join("");

  ltResult.hidden = false;
  ltResult.innerHTML = `
    <h4>Load test result · ${escapeHtml(result.mode)} mode · ${escapeHtml(result.scope)} scope</h4>
    <div class="loadtest-grid">
      <div class="loadtest-stat"><span>Throughput</span><strong>${result.requests_per_sec.toFixed(1)}</strong> req/s</div>
      <div class="loadtest-stat"><span>Requests</span><strong>${result.requests_total.toLocaleString()}</strong> in ${result.duration_seconds}s</div>
      <div class="loadtest-stat"><span>Success</span><strong>${(result.success_rate * 100).toFixed(1)}%</strong></div>
      <div class="loadtest-stat"><span>p50 / p95 / p99</span><strong>${result.latency.p50_ms.toFixed(0)} / ${result.latency.p95_ms.toFixed(0)} / ${result.latency.p99_ms.toFixed(0)}</strong> ms</div>
      <div class="loadtest-stat"><span>Virtual users</span><strong>${result.concurrency}</strong></div>
      <div class="loadtest-stat"><span>Balancer policy</span><strong>${escapeHtml(LB_LABELS[result.lb_algorithm] || result.lb_algorithm)}</strong></div>
    </div>
    <div>${statusLine}</div>
    <div>
      <p class="panel-note">Traffic distribution across replicas (each should land near ${result.expected_node_share_pct}%):</p>
      ${dist || "<p class='panel-note'>No per-node header observed.</p>"}
    </div>
    ${result.throttling_verified ? `<p class="panel-note metric-good">Rate limiter verified: ${sc["429"] || 0} requests received HTTP 429 with Retry-After.</p>` : ""}
    ${result.mode === "capacity" && result.limiter_armed_nodes.length ? `<p class="panel-note">Limiter paused for loopback on: ${result.limiter_armed_nodes.map(escapeHtml).join(", ")} (coordinated capacity test).</p>` : ""}
  `;
}

// ---------------- Refresh control + wiring ----------------

function startScalabilityAutoRefresh() {
  stopScalabilityAutoRefresh();
  scalTimer = setInterval(() => {
    if (scalAutoRefresh && !scalAutoRefresh.checked) return;
    if (document.hidden) return;
    if (!authToken) return;
    loadScalability();
  }, 3000);
}

function stopScalabilityAutoRefresh() {
  if (scalTimer) {
    clearInterval(scalTimer);
    scalTimer = null;
  }
}

if (scalRefreshBtn) scalRefreshBtn.addEventListener("click", () => loadScalability(true));

if (scalAutoRefresh) {
  scalAutoRefresh.addEventListener("change", () => {
    if (scalAutoRefresh.checked) {
      startScalabilityAutoRefresh();
      loadScalability(true);
    } else {
      stopScalabilityAutoRefresh();
      scalLiveDot.className = "live-dot stale";
      scalLiveDot.title = "Auto-refresh paused";
    }
  });
}

window.addEventListener("resize", () => {
  if (scalData) renderScalChart(scalData.cluster.series);
});

document.getElementById("navScalability").addEventListener("click", (event) => {
  event.preventDefault();
  loadScalability(true);
  document.getElementById("scalability").scrollIntoView({ behavior: "smooth" });
});

const navScalabilityCompact = document.getElementById("navScalability2");
if (navScalabilityCompact) {
  navScalabilityCompact.addEventListener("click", (event) => {
    event.preventDefault();
    loadScalability(true);
    document.getElementById("scalability").scrollIntoView({ behavior: "smooth" });
  });
}
