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
