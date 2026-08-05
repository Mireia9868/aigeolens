/**
 * AI GeoLens — Frontend JavaScript
 * Flow: Free scan → Choose plan → PayPal checkout → Full report
 */

const API_BASE = window.location.origin;

// State
let pendingScanData = null;
let pendingPlan = "audit";
let lastReportData = null;

// Plan display info
const PLAN_INFO = {
  audit: { name: "お試し診断", price: "¥498", desc: "完全版GEO診断レポート（単発・お試し価格）" },
  pro: { name: "プロプラン", price: "¥9,800", desc: "詳細診断3回＋競合分析パック（単発）" },
  business: { name: "ビジネスプラン", price: "¥29,800", desc: "代理店向けホワイトラベルレポート（単発）" },
};

// Payment method state
let paymentMethod = "paypal";

// === URL Form Submission (Step 1: Free Scan) ===
document.addEventListener("DOMContentLoaded", () => {
  const form = document.getElementById("url-form");
  if (form) {
    form.addEventListener("submit", handleScan);
  }

  // Checkout form handler
  const checkoutForm = document.getElementById("checkout-form");
  if (checkoutForm) {
    checkoutForm.addEventListener("submit", handleCheckoutSubmit);
  }

  // Bank transfer button handler
  const bankBtn = document.getElementById("bank-transfer-btn");
  if (bankBtn) {
    bankBtn.addEventListener("click", handleBankTransfer);
  }

  // Check PayPal availability and show bank transfer option
  checkPaymentAvailability();

  // Check if returning from PayPal with report data
  const urlParams = new URLSearchParams(window.location.search);
  const reportFlag = urlParams.get("report");
  if (reportFlag === "1") {
    const reportData = sessionStorage.getItem("geo_report_data");
    if (reportData) {
      sessionStorage.removeItem("geo_report_data");
      try {
        const data = JSON.parse(reportData);
        renderFullReport(data);
      } catch (e) {
        console.error("Failed to render report:", e);
      }
    }
  }
});

// === Payment Availability Check ===
async function checkPaymentAvailability() {
  try {
    const resp = await fetch(`${API_BASE}/api/health`);
    const data = await resp.json();
    const paypalEnabled = data.paypal_enabled;
    const bankEnabled = data.bank_transfer_enabled;

    const bankBtn = document.getElementById("bank-transfer-btn");
    const submitBtn = document.querySelector(".checkout-submit");
    const btnText = document.getElementById("checkout-btn-text");

    if (bankBtn && bankEnabled) {
      bankBtn.style.display = "block";
    }

    if (submitBtn && btnText) {
      if (!paypalEnabled && bankEnabled) {
        // PayPal not available — default to bank transfer
        paymentMethod = "bank_transfer";
        btnText.textContent = "銀行振込で申し込む";
        submitBtn.type = "button";
        submitBtn.removeEventListener("submit", () => {});
        submitBtn.addEventListener("click", handleBankTransfer);
      } else if (!paypalEnabled && !bankEnabled) {
        btnText.textContent = "決済準備中";
        submitBtn.disabled = true;
      }
    }
  } catch (e) {
    console.warn("Could not check payment availability:", e);
  }
}

// === Bank Transfer Handler ===
async function handleBankTransfer() {
  if (!pendingScanData) {
    alert("まず無料スキャンを実行してください。");
    document.getElementById("url-form").scrollIntoView({ behavior: "smooth" });
    return;
  }

  const email = document.getElementById("checkout-email").value.trim();
  const company = document.getElementById("checkout-company").value.trim();

  if (!email || !company) {
    alert("メールアドレスと会社名を入力してください。");
    return;
  }

  const btn = document.getElementById("bank-transfer-btn") || document.querySelector(".checkout-submit");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "処理中...";
  }

  try {
    const resp = await fetch(`${API_BASE}/api/bank-transfer-order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: pendingPlan,
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

    // Show bank transfer instructions
    closeCheckoutModal();
    renderBankTransferInstructions(data);
  } catch (err) {
    alert("銀行振込の申し込み中にエラーが発生しました: " + err.message);
    if (btn) {
      btn.disabled = false;
      btn.textContent = "銀行振込で支払う";
    }
  }
}

// === Bank Transfer Instructions Display ===
function renderBankTransferInstructions(data) {
  const section = document.getElementById("report-section");
  if (!section) return;

  const bank = data.bank_details || {};
  const instructions = data.instructions || [];

  section.innerHTML = `
    <div class="container">
      <div class="scan-result-card" style="text-align:center;">
        <div style="font-size:48px;margin-bottom:16px;">🏦</div>
        <h2 style="margin-bottom:8px;">銀行振込のお申し込みを受け付けました</h2>
        <p style="color:var(--text-soft);margin-bottom:24px;">以下の口座へお振込みください。入金確認後、レポート生成リンクをメールでお送りします。</p>

        <div style="background:var(--card);border-radius:12px;padding:24px;margin:20px 0;text-align:left;max-width:500px;margin-left:auto;margin-right:auto;">
          <div style="display:grid;grid-template-columns:auto 1fr;gap:12px 20px;font-size:15px;">
            <div style="color:var(--text-soft);">銀行名</div>
            <div style="font-weight:700;">${bank.bank_name || '-'}</div>
            <div style="color:var(--text-soft);">支店</div>
            <div style="font-weight:700;">${bank.branch || '-'}</div>
            <div style="color:var(--text-soft);">口座種別</div>
            <div style="font-weight:700;">${bank.account_type || '-'}</div>
            <div style="color:var(--text-soft);">口座番号</div>
            <div style="font-weight:700;font-size:18px;">${bank.account_number || '-'}</div>
            <div style="color:var(--text-soft);">名義人</div>
            <div style="font-weight:700;">${bank.account_holder || '-'}</div>
          </div>
          <div style="border-top:1px solid var(--border);margin-top:16px;padding-top:16px;">
            <div style="color:var(--text-soft);font-size:13px;">振込金額</div>
            <div style="font-weight:800;font-size:28px;color:var(--primary);">¥${data.amount.toLocaleString()}</div>
          </div>
        </div>

        <div style="background:rgba(255,200,0,0.1);border-radius:8px;padding:16px;max-width:500px;margin:16px auto;text-align:left;">
          <div style="font-weight:700;margin-bottom:8px;">振込時のご注意</div>
          ${instructions.map(i => `<div style="font-size:13px;margin:4px 0;">・${i}</div>`).join("")}
        </div>

        <div style="background:var(--card);border-radius:8px;padding:12px;max-width:500px;margin:16px auto;">
          <span style="font-size:13px;color:var(--text-soft);">注文番号:</span>
          <span style="font-weight:700;font-family:monospace;">${data.order_ref}</span>
        </div>

        <a href="/" style="display:inline-block;background:var(--gradient);color:#fff;padding:14px 32px;border-radius:10px;text-decoration:none;font-weight:700;margin-top:16px;">ホームに戻る</a>
      </div>
    </div>
  `;

  section.classList.add("active");
  section.scrollIntoView({ behavior: "smooth" });
}

async function handleScan(e) {
  e.preventDefault();
  const urlInput = document.getElementById("url-input");
  const brandInput = document.getElementById("brand-input");
  const url = urlInput.value.trim();
  const brand = brandInput ? brandInput.value.trim() : "";

  if (!url) {
    alert("URLを入力してください。");
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
    alert("スキャン中にエラーが発生しました: " + err.message);
  } finally {
    hideLoading();
  }
}

// === Step 1 Result: Show Partial Score + Plan Selection ===
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
              基建チェック: ${data.passed_checks || 0}/${data.total_checks || 15} 項目合格<br>
              ${crawl.title ? 'タイトル: ' + crawl.title : ''} ${crawl.word_count ? '\u00b7 文字数: ' + crawl.word_count : ''}
            </p>
          </div>
        </div>

        <!-- Top 3 Issues -->
        ${issues.length ? `
          <div class="issues-section">
            <h3>主要な問題点 (TOP ${issues.length})</h3>
            ${issuesHtml}
          </div>
        ` : '<p class="no-issues">重要な問題点は見つかりませんでした。しかし、AI可視性の詳細分析が必要です。</p>'}

        <!-- Locked Full Report Preview -->
        <div class="locked-preview">
          <div class="locked-header">
            <h3>\ud83d\udd12 完全版GEO診断レポート</h3>
            <span class="locked-tag">\u00a5498\u301c</span>
          </div>
          <div class="preview-list">${previewHtml}</div>
        </div>

        <!-- Plan Selection -->
        <div class="lead-capture-section" id="lead-capture">
          <h3>完全版レポートを取得</h3>
          <p class="lead-desc">以下のプランから選択して、PayPal決済ページに進みます。</p>

          <div style="display:flex; gap:12px; justify-content:center; flex-wrap:wrap; margin-bottom:20px;">
            <button class="plan-select-btn" onclick="openCheckoutModal('audit')" style="background:#fff;color:var(--primary);border:none;padding:16px 28px;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;flex:1;min-width:180px;">
              <div style="font-size:13px;opacity:0.7;">単発</div>
              <div style="font-size:20px;margin:4px 0;">\u00a5498</div>
              <div style="font-size:12px;opacity:0.7;">完全版レポート</div>
            </button>
            <button class="plan-select-btn" onclick="openCheckoutModal('pro')" style="background:rgba(255,255,255,0.15);color:#fff;border:1px solid rgba(255,255,255,0.3);padding:16px 28px;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;flex:1;min-width:180px;">
              <div style="font-size:13px;opacity:0.8;">単発</div>
              <div style="font-size:20px;margin:4px 0;">\u00a59,800</div>
              <div style="font-size:12px;opacity:0.8;">詳細診断3回分</div>
            </button>
            <button class="plan-select-btn" onclick="openCheckoutModal('business')" style="background:rgba(255,255,255,0.15);color:#fff;border:1px solid rgba(255,255,255,0.3);padding:16px 28px;border-radius:10px;font-size:15px;font-weight:700;cursor:pointer;transition:all 0.2s;flex:1;min-width:180px;">
              <div style="font-size:13px;opacity:0.8;">単発</div>
              <div style="font-size:20px;margin:4px 0;">\u00a529,800</div>
              <div style="font-size:12px;opacity:0.8;">ホワイトラベル</div>
            </button>
          </div>

          <p class="lead-note">
            <span class="lock-icon">\ud83d\udd12</span> PayPal決済で安全に処理 &nbsp;
            \u2713 クレジットカード / デビットカード / PayPal残高 &nbsp;
            \u2713 SSL暗号化通信
          </p>
        </div>
      </div>
    </div>
  `;

  section.classList.add("active");
  section.scrollIntoView({ behavior: "smooth" });
}

// === Plan Selection & Checkout Modal ===
function setPendingPlan(plan) {
  pendingPlan = plan;
}

function openCheckoutModal(plan) {
  pendingPlan = plan;

  if (!pendingScanData) {
    alert("まず無料スキャンを実行してください。");
    document.getElementById("url-form").scrollIntoView({ behavior: "smooth" });
    return;
  }

  const info = PLAN_INFO[plan] || PLAN_INFO.audit;
  const modal = document.getElementById("checkout-modal");
  const desc = document.getElementById("checkout-plan-desc");
  const summary = document.getElementById("checkout-summary");

  if (desc) desc.textContent = `${info.name} \u2014 ${info.desc}`;
  if (summary) {
    summary.innerHTML = `
      <div>
        <div style="font-size:13px;color:var(--text-soft);">プラン</div>
        <div style="font-weight:700;font-size:15px;">${info.name}</div>
      </div>
      <div style="text-align:right;">
        <div style="font-size:13px;color:var(--text-soft);">金額</div>
        <div style="font-weight:800;font-size:20px;color:var(--primary);">${info.price}</div>
      </div>
    `;
  }

  if (modal) modal.classList.add("active");
}

function closeCheckoutModal() {
  const modal = document.getElementById("checkout-modal");
  if (modal) modal.classList.remove("active");
}

async function handleCheckoutSubmit(e) {
  e.preventDefault();

  if (!pendingScanData) {
    alert("スキャンデータが見つかりません。再度診断してください。");
    return;
  }

  const email = document.getElementById("checkout-email").value.trim();
  const company = document.getElementById("checkout-company").value.trim();
  const btn = e.target.querySelector(".checkout-submit");
  const btnText = document.getElementById("checkout-btn-text");

  if (!email || !company) {
    alert("メールアドレスと会社名を入力してください。");
    return;
  }

  btn.disabled = true;
  if (btnText) btnText.textContent = "PayPal決済ページを準備中...";

  try {
    const resp = await fetch(`${API_BASE}/api/create-paypal-order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        plan: pendingPlan,
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

    // Redirect to PayPal approval page
    window.location.href = data.approval_url;
  } catch (err) {
    alert("決済の準備中にエラーが発生しました: " + err.message);
    btn.disabled = false;
    if (btnText) btnText.textContent = "PayPal決済ページへ進む";
  }
}

// === Loading ===
function showLoading(mode) {
  const overlay = document.getElementById("loading-overlay");
  if (overlay) {
    overlay.classList.add("active");
    const title = overlay.querySelector("h3");
    const desc = overlay.querySelector(".loading-box > p");
    const steps = overlay.querySelectorAll(".loading-steps div");
    if (mode === "scan") {
      if (title) title.textContent = "スキャン中...";
      if (desc) desc.textContent = "サイトの基建をチェックしています";
      if (steps[0]) steps[0].textContent = "サイトコンテンツを取得中";
      if (steps[1]) steps[1].textContent = "構造化データをチェック中";
      if (steps[2]) steps[2].style.display = "none";
      if (steps[3]) steps[3].style.display = "none";
    } else {
      if (title) title.textContent = "AI診断中...";
      if (desc) desc.textContent = "DeepSeek AIが詳細分析を実行しています";
      if (steps[0]) { steps[0].textContent = "サイトコンテンツを取得中"; steps[0].style.display = ""; }
      if (steps[1]) { steps[1].textContent = "構造化データをチェック中"; steps[1].style.display = ""; }
      if (steps[2]) { steps[2].textContent = "AI可視性をシミュレーション中"; steps[2].style.display = ""; }
      if (steps[3]) { steps[3].textContent = "改善提案を生成中"; steps[3].style.display = ""; }
    }
  }

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
      <div class="rec-cat">${r.category || ''} \u00b7 ${r.priority === 'high' ? '高優先' : '中優先'}</div>
      <div class="rec-title">${r.title}</div>
      <div class="rec-desc">${r.description}</div>
      <div class="rec-meta">想定インパクト: ${r.impact || '-'} \u00b7 工数: ${r.effort || '-'}</div>
    </div>
  `).join("");

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

  let citedQueriesHtml = "";
  if (s2.likely_cited_queries && s2.likely_cited_queries.length) {
    citedQueriesHtml = s2.likely_cited_queries.map(q => `<span class="query-tag positive">${q}</span>`).join("");
  }

  const mode = s4.mode === "live" ? '<span style="color:#22c55e;font-size:12px;">\u25cf Live AI Analysis</span>' : '<span style="color:#f59e0b;font-size:12px;">\u25cf Demo Mode</span>';

  const paymentInfo = data.payment ? `<div style="font-size:12px;color:var(--text-soft);margin-top:8px;">決済プラン: ${data.payment.plan} \u00b7 \u00a5${data.payment.amount.toLocaleString()} ${data.payment.currency?.toUpperCase()} (${data.payment.method || 'paypal'})</div>` : '';

  // Store report data safely (no JSON in DOM)
  lastReportData = data;

  section.innerHTML = `
    <div class="container">
      <div class="report-card">
        <div class="report-header">
          ${mode}
          <div class="score-circle ${scoreClass}">${score}</div>
          <h2>GEO 完全診断レポート</h2>
          <div class="url">${data.url || ''}</div>
          <div class="level-badge" style="background: ${levelColor}20; color: ${levelColor};">${level}</div>
          ${paymentInfo}
        </div>

        <h3 class="section-h3">AIVOスコア（AI可視性総合評価）</h3>
        <div class="dim-grid">${aivoDimsHtml}</div>

        ${aiDimsHtml ? `
          <h3 class="section-h3">AI可視性詳細分析（DeepSeek AI）</h3>
          <div class="dim-grid">${aiDimsHtml}</div>
        ` : ''}

        ${citedQueriesHtml ? `
          <h3 class="section-h3">AIが参照する可能性のある検索クエリ</h3>
          <div class="query-list">${citedQueriesHtml}</div>
        ` : ''}

        ${compsHtml ? `
          <h3 class="section-h3">競合GEO強度比較</h3>
          <div class="comp-grid">${compsHtml}</div>
        ` : ''}

        ${checks.length ? `
          <h3 class="section-h3">基建チェック結果 (${s1.passed_checks || 0}/${s1.total_checks || 0})</h3>
          <div class="checks-list">${checksHtml}</div>
        ` : ''}

        ${recs.length ? `
          <h3 class="section-h3">改善推奨事項</h3>
          <div class="recs-list">${recsHtml}</div>
        ` : ''}

        <div class="report-actions">
          <a href="#url-form" onclick="resetForm()">再診断</a>
          <a href="#" class="secondary" id="download-report-btn">レポートダウンロード</a>
        </div>
      </div>
    </div>
  `;

  section.classList.add("active");
  section.scrollIntoView({ behavior: "smooth" });

  // Attach download handler safely (no JSON in DOM attributes)
  const dlBtn = document.getElementById("download-report-btn");
  if (dlBtn) {
    dlBtn.addEventListener("click", (e) => {
      e.preventDefault();
      downloadReport(lastReportData);
    });
  }
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
