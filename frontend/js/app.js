/**
 * GEO MVP - Frontend JavaScript
 * Two-step funnel: Free scan -> Lead capture -> Unlock full report
 */

const API_BASE = window.location.origin;

// State
let pendingScanData = null;

// === URL Form Submission (Step 1: Free Scan) ===
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("url-form");
  if (form) {
    form.addEventListener("submit", handleScan);
  }
});

async function handleScan(e) {
  e.preventDefault();
  const urlInput = document.getElementById("url-input");
  const brandInput = document.getElementById("brand-input");
  const url = urlInput.value.trim();
  const brand = brandInput ? brandInput.value.trim() : "";

  if (!url) {
    alert("URL\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002");
    return;
  }

  showLoading("scan");

  try {
    const resp = await fetch(`${API_BASE}/api/scan`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, brand_name: brand }),
    });

    const data = await resp.json();

    if (data.error) {
      throw new Error(data.message || data.error);
    }

    pendingScanData = { url, brand, ...data };
    renderScanResult(pendingScanData);
  } catch (err) {
    alert("\u30b9\u30ad\u30e3\u30f3\u4e2d\u306b\u30a8\u30e9\u30fc\u304c\u767a\u751f\u3057\u307e\u3057\u305f: " + err.message);
  } finally {
    hideLoading();
  }
}

// === Step 1 Result: Show Partial Score + Lead Capture Form ===
function renderScanResult(data) {
  const section = document.getElementById("report-section");
  if (!section) return;

  const score = data.score || 0;
  const level = data.level || "";
  const scoreClass = score >= 75 ? "good" : score >= 60 ? "average" : "poor";
  const scoreColor = score >= 75 ? "#22c55e" : score >= 60 ? "#f59e0b" : "#ef4444";

  const issues = data.top_issues || [];
  const preview = data.full_report_preview || [];

  let issuesHtml = issues.map(iss => `
    <div class="issue-item">
      <span class="issue-icon">\u26a0</span>
      <div>
        <div class="issue-name">${iss.name}</div>
        <div class="issue-msg">${iss.message}</div>
      </div>
    </div>
  `).join("");

  let previewHtml = preview.map(p => `
    <div class="preview-item">
      <span class="lock-icon">\ud83d\udd12</span>
      <span class="preview-text">${p}</span>
    </div>
  `).join("");

  const crawl = data.crawl_summary || {};

  section.innerHTML = `
    <div class="container">
      <div class="scan-result-card">
        <!-- Score Section -->
        <div class="scan-header">
          <div class="score-circle ${scoreClass}">${score}</div>
          <div class="scan-header-info">
            <div class="scan-url">${data.url || ''}</div>
            <div class="level-badge" style="background: ${scoreColor}20; color: ${scoreColor};">${level}</div>
            <p class="scan-summary">
              \u57fa\u5efa\u30c1\u30a7\u30c3\u30af: ${data.passed_checks || 0}/${data.total_checks || 15} \u9805\u76ee\u5408\u683c<br>
              ${crawl.title ? '\u30bf\u30a4\u30c8\u30eb: ' + crawl.title : ''} ${crawl.word_count ? '\u00b7 \u6587\u5b57\u6570: ' + crawl.word_count : ''}
            </p>
          </div>
        </div>

        <!-- Top 3 Issues -->
        ${issues.length ? `
          <div class="issues-section">
            <h3>\u4e3b\u8981\u306a\u554f\u984c\u70b9 (TOP ${issues.length})</h3>
            ${issuesHtml}
          </div>
        ` : '<p class="no-issues">\u91cd\u8981\u306a\u554f\u984c\u70b9\u306f\u898b\u3064\u304b\u308a\u307e\u305b\u3093\u3067\u3057\u305f\u3002\u3057\u304b\u3057\u3001AI\u53ef\u8996\u6027\u306e\u8a73\u7d30\u5206\u6790\u304c\u5fc5\u8981\u3067\u3059\u3002</p>'}

        <!-- Locked Full Report Preview -->
        <div class="locked-preview">
          <div class="locked-header">
            <h3>\ud83d\udd10 \u5b8c\u5168\u7248GEO\u8a3a\u65ad\u30ec\u30dd\u30fc\u30c8</h3>
            <span class="locked-tag">\u30e1\u30fc\u30eb\u767b\u9332\u3067\u89e3\u9664</span>
          </div>
          <div class="preview-list">${previewHtml}</div>
        </div>

        <!-- Lead Capture Form -->
        <div class="lead-capture-section" id="lead-capture">
          <h3>\u5b8c\u5168\u7248\u30ec\u30dd\u30fc\u30c8\u3092\u53d6\u5f97</h3>
          <p class="lead-desc">\u4ee5\u4e0b\u3092\u5165\u529b\u3057\u3066\u300125+\u56e0\u5b50\u306e\u8a73\u7d30\u5206\u6790\u3001AI\u53ef\u8996\u6027\u30b9\u30b3\u30a2\u3001\u7af6\u5408\u6bd4\u8f03\u3001\u6539\u5584\u63d0\u6848\u3092\u89e3\u9664\u3057\u307e\u3059\u3002</p>
          
          <form id="lead-form" class="lead-form">
            <div class="form-row">
              <input type="email" id="email-input" placeholder="\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9" required autocomplete="email">
              <input type="text" id="company-input" placeholder="\u4f1a\u793e\u540d" required autocomplete="organization">
            </div>
            <button type="submit" class="lead-submit">
              \u5b8c\u5168\u7248\u30ec\u30dd\u30fc\u30c8\u3092\u89e3\u9664 \u2192
            </button>
            <p class="lead-note">
              \u2713 \u30af\u30ec\u30b8\u30c3\u30c8\u30ab\u30fc\u30c9\u4e0d\u8981 &nbsp;
              \u2713 \u30b9\u30d1\u30e0\u306a\u3057 &nbsp;
              \u2713 \u3044\u3064\u3067\u3082\u89e3\u7d04\u53ef\u80fd
            </p>
          </form>
        </div>
      </div>
    </div>
  `;

  section.classList.add("active");
  section.scrollIntoView({ behavior: "smooth" });

  // Attach lead form handler
  const leadForm = document.getElementById("lead-form");
  if (leadForm) {
    leadForm.addEventListener("submit", handleUnlock);
  }
}

// === Step 2: Lead Capture -> Unlock Full Report ===
async function handleUnlock(e) {
  e.preventDefault();

  if (!pendingScanData) {
    alert("\u30b9\u30ad\u30e3\u30f3\u30c7\u30fc\u30bf\u304c\u898b\u3064\u304b\u308a\u307e\u305b\u3093\u3002\u518d\u8a3a\u65ad\u3057\u3066\u304f\u3060\u3055\u3044\u3002");
    return;
  }

  const email = document.getElementById("email-input").value.trim();
  const company = document.getElementById("company-input").value.trim();

  if (!email || !company) {
    alert("\u30e1\u30fc\u30eb\u30a2\u30c9\u30ec\u30b9\u3068\u4f1a\u793e\u540d\u3092\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002");
    return;
  }

  showLoading("analyze");

  try {
    const resp = await fetch(`${API_BASE}/api/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: pendingScanData.url,
        brand_name: pendingScanData.brand || "",
        email: email,
        company_name: company,
      }),
    });

    const data = await resp.json();

    if (data.error) {
      throw new Error(data.message || data.error);
    }

    renderFullReport(data);
  } catch (err) {
    alert("\u8a3a\u65ad\u4e2d\u306b\u30a8\u30e9\u30fc\u304c\u767a\u751f\u3057\u307e\u3057\u305f: " + err.message);
  } finally {
    hideLoading();
  }
}

// === Loading ===
function showLoading(mode) {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) {
    overlay.classList.add("active");
    // Update loading text based on mode
    const title = overlay.querySelector("h3");
    const desc = overlay.querySelector(".loading-box > p");
    const steps = overlay.querySelectorAll(".loading-steps div");
    if (mode === "scan") {
      if (title) title.textContent = "\u30b9\u30ad\u30e3\u30f3\u4e2d...";
      if (desc) desc.textContent = "\u30b5\u30a4\u30c8\u306e\u57fa\u5efa\u3092\u30c1\u30a7\u30c3\u30af\u3057\u3066\u3044\u307e\u3059";
      if (steps[0]) steps[0].textContent = "\u30b5\u30a4\u30c8\u30b3\u30f3\u30c6\u30f3\u30c4\u3092\u53d6\u5f97\u4e2d";
      if (steps[1]) steps[1].textContent = "\u69cb\u9020\u5316\u30c7\u30fc\u30bf\u3092\u30c1\u30a7\u30c3\u30af\u4e2d";
      if (steps[2]) steps[2].style.display = "none";
      if (steps[3]) steps[3].style.display = "none";
    } else {
      if (title) title.textContent = "AI\u8a3a\u65ad\u4e2d...";
      if (desc) desc.textContent = "DeepSeek AI\u304c\u8a73\u7d30\u5206\u6790\u3092\u5b9f\u884c\u3057\u3066\u3044\u307e\u3059";
      if (steps[0]) { steps[0].textContent = "\u30b5\u30a4\u30c8\u30b3\u30f3\u30c6\u30f3\u30c4\u3092\u53d6\u5f97\u4e2d"; steps[0].style.display = ""; }
      if (steps[1]) { steps[1].textContent = "\u69cb\u9020\u5316\u30c7\u30fc\u30bf\u3092\u30c1\u30a7\u30c3\u30af\u4e2d"; steps[1].style.display = ""; }
      if (steps[2]) { steps[2].textContent = "AI\u53ef\u8996\u6027\u3092\u30b7\u30df\u30e5\u30ec\u30fc\u30b7\u30e7\u30f3\u4e2d"; steps[2].style.display = ""; }
      if (steps[3]) { steps[3].textContent = "\u6539\u5584\u63d0\u6848\u3092\u751f\u6210\u4e2d"; steps[3].style.display = ""; }
    }
  }

  // Animate steps
  const steps = document.querySelectorAll(".loading-steps div");
  const visibleSteps = Array.from(steps).filter(s => s.style.display !== "none");
  steps.forEach((s, i) => {
    setTimeout(() => {
      visibleSteps.forEach((x, j) => {
        x.classList.remove("active", "done");
        if (j < i) x.classList.add("done");
        if (j === i) x.classList.add("active");
      });
    }, i * 1500);
  });
}

function hideLoading() {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) overlay.classList.remove("active");
}

// === Full Report Rendering ===
function renderFullReport(data) {
  const section = document.getElementById("report-section");
  if (!section) return;

  const score = data.overall_score || 0;
  const level = data.score_level || "";
  const scoreClass = score >= 90 ? "excellent" : score >= 75 ? "good" : score >= 60 ? "average" : "poor";
  const levelColor = score >= 90 ? "#22c55e" : score >= 75 ? "#3b82f6" : score >= 60 ? "#f59e0b" : "#ef4444";

  const s1 = data.stages?.stage1_infrastructure || {};
  const s2 = data.stages?.stage2_ai_visibility || {};
  const s3 = data.stages?.stage3_competitive || {};
  const s4 = data.stages?.stage4_scoring || {};
  const aivo = s4.aivo_score || {};
  const dims = aivo.dimensions || [];
  const checks = s1.checks || [];
  const recs = s4.recommendations || [];

  // AI Visibility dimensions
  let aiDimsHtml = "";
  if (s2.dimensions) {
    aiDimsHtml = Object.entries(s2.dimensions).map(([key, val]) => `
      <div class="dim-item">
        <div class="dim-name">${key.replace(/_/g, ' ')}</div>
        <div class="dim-score">${val.score || 0}</div>
        <div class="dim-bar"><div class="dim-bar-fill" style="width: ${val.score || 0}%; background: ${(val.score||0) >= 75 ? '#22c55e' : (val.score||0) >= 60 ? '#f59e0b' : '#ef4444'}"></div></div>
        <div class="dim-comment">${val.comment || ''}</div>
      </div>
    `).join("");
  }

  let aivoDimsHtml = dims.map(d => `
    <div class="dim-item">
      <div class="dim-name">${d.name} (${Math.round(d.weight * 100)}%)</div>
      <div class="dim-score">${d.score}</div>
      <div class="dim-bar"><div class="dim-bar-fill" style="width: ${d.score}%; background: ${d.score >= 75 ? '#22c55e' : d.score >= 60 ? '#f59e0b' : '#ef4444'}"></div></div>
      <div class="dim-comment">${d.comment || ''}</div>
    </div>
  `).join("");

  let checksHtml = checks.map(c => `
    <div class="check-row ${c.passed ? 'pass' : 'fail'}">
      <span class="icon">${c.passed ? '\u2713' : '\u2717'}</span>
      <div>
        <div class="name">${c.name}</div>
        <div class="msg">${c.message}</div>
      </div>
    </div>
  `).join("");

  let recsHtml = recs.map(r => `
    <div class="rec-item ${r.priority || 'medium'}">
      <div class="rec-cat">${r.category || ''} \u00b7 ${r.priority === 'high' ? '\u9ad8\u512a\u5148' : '\u4e2d\u512a\u5148'}</div>
      <div class="rec-title">${r.title}</div>
      <div class="rec-desc">${r.description}</div>
      <div class="rec-meta">\u4e88\u60f3\u30a4\u30f3\u30d1\u30af\u30c8: ${r.impact || '-'} \u00b7 \u5de5\u6570: ${r.effort || '-'}</div>
    </div>
  `).join("");

  // Competitors
  let compsHtml = "";
  if (s3.competitors && s3.competitors.length) {
    compsHtml = s3.competitors.map(c => `
      <div class="comp-item">
        <div class="comp-name">${c.name || '?'}</div>
        <div class="comp-score">GEO: ${c.geo_strength || 0}</div>
        <div class="comp-adv">${c.advantage || ''}</div>
      </div>
    `).join("");
  }

  // AI cited queries
  let citedQueriesHtml = "";
  if (s2.likely_cited_queries && s2.likely_cited_queries.length) {
    citedQueriesHtml = s2.likely_cited_queries.map(q => `<span class="query-tag positive">${q}</span>`).join("");
  }

  const mode = s4.mode === "live" ? '<span style="color:#22c55e;font-size:12px;">\u25cf Live AI Analysis</span>' : '<span style="color:#f59e0b;font-size:12px;">\u25cf Demo Mode</span>';

  section.innerHTML = `
    <div class="container">
      <div class="report-card">
        <div class="report-header">
          ${mode}
          <div class="score-circle ${scoreClass}">${score}</div>
          <h2>GEO \u5b8c\u5168\u8a3a\u65ad\u30ec\u30dd\u30fc\u30c8</h2>
          <div class="url">${data.url || ''}</div>
          <div class="level-badge" style="background: ${levelColor}20; color: ${levelColor};">${level}</div>
        </div>

        <!-- AIVO Score -->
        <h3 class="section-h3">AIVO\u30b9\u30b3\u30a2\uff08AI\u53ef\u8996\u6027\u7dcf\u5408\u8a55\u4fa1\uff09</h3>
        <div class="dim-grid">${aivoDimsHtml}</div>

        <!-- AI Visibility Detail -->
        ${aiDimsHtml ? `
          <h3 class="section-h3">AI\u53ef\u8996\u6027\u8a73\u7d30\u5206\u6790\uff08DeepSeek AI\uff09</h3>
          <div class="dim-grid">${aiDimsHtml}</div>
        ` : ''}

        <!-- Cited Queries -->
        ${citedQueriesHtml ? `
          <h3 class="section-h3">AI\u304c\u53c2\u7167\u3059\u308b\u53ef\u80fd\u6027\u306e\u3042\u308b\u691c\u7d22\u30af\u30a8\u30ea</h3>
          <div class="query-list">${citedQueriesHtml}</div>
        ` : ''}

        <!-- Competitors -->
        ${compsHtml ? `
          <h3 class="section-h3">\u7af6\u5408GEO\u5f37\u5ea6\u6bd4\u8f03</h3>
          <div class="comp-grid">${compsHtml}</div>
        ` : ''}

        <!-- Infrastructure Checks -->
        ${checks.length ? `
          <h3 class="section-h3">\u57fa\u5efa\u30c1\u30a7\u30c3\u30af\u7d50\u679c (${s1.passed_checks || 0}/${s1.total_checks || 0})</h3>
          <div class="checks-list">${checksHtml}</div>
        ` : ''}

        <!-- Recommendations -->
        ${recs.length ? `
          <h3 class="section-h3">\u6539\u5584\u63a8\u5968\u4e8b\u9805</h3>
          <div class="recs-list">${recsHtml}</div>
        ` : ''}

        <div class="report-actions">
          <a href="#url-form" onclick="resetForm()">\u518d\u8a3a\u65ad</a>
          <a href="#" class="secondary" onclick="downloadReport(${JSON.stringify(data).replace(/"/g, '&quot;')}); return false;">\u30ec\u30dd\u30fc\u30c8\u30c0\u30a6\u30f3\u30ed\u30fc\u30c9</a>
        </div>
      </div>
    </div>
  `;

  section.classList.add("active");
  section.scrollIntoView({ behavior: "smooth" });
}

function resetForm() {
  const section = document.getElementById("report-section");
  if (section) {
    section.classList.remove("active");
    section.innerHTML = "";
  }
  document.getElementById("url-input").value = "";
  pendingScanData = null;
}

function downloadReport(data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = `geo-report-${data.analysis_id || Date.now()}.json`;
  a.click();
  URL.revokeObjectURL(a.href);
}
