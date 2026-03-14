
"use strict";

let currentData  = null;
let uploadedBlob = null;

const LANG_NAMES = { en: "🇬🇧 English", hi: "🇮🇳 Hindi", ta: "🇮🇳 Tamil" };
const AUDIO_SECTIONS = [
  { key: "summary_url",     label: "Medicine Summary" },
  { key: "interaction_url", label: "Interactions" },
  { key: "schedule_url",    label: "Schedule" },
];

const SAMPLES = [
  { label: "Diabetic + Cardiac",
    text: `Metformin 500mg twice daily with food\nAtorvastatin 20mg at bedtime\nLisinopril 10mg once daily in the morning\nAspirin 75mg once daily after breakfast\nOmeprazole 20mg before breakfast` },
  { label: "Complex Cardiac",
    text: `Warfarin 5mg daily\nAmlodipine 5mg once daily\nAmiodarone 200mg daily\nDigoxin 0.125mg once daily\nFurosemide 40mg in the morning` },
  { label: "Infection + Allergy",
    text: `Amoxicillin 500mg TID for 7 days\nCetirizine 10mg at night\nPrednisolone 20mg morning\nOmeprazole 20mg before breakfast\nIbuprofen 400mg TID with food` },
  { label: "Anxiety + Pain",
    text: `Sertraline 50mg once daily morning\nAlprazolam 0.5mg twice daily\nTramadol 50mg every 8 hours\nOmeprazole 20mg before breakfast\nParacetamol 500mg when needed` }
];

// ── Init ──────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  buildSamples();
  setupDragDrop();
});

function buildSamples() {
  const list = document.getElementById("sample-list");
  if (!list) return;
  SAMPLES.forEach(s => {
    const btn = document.createElement("button");
    btn.className = "sample-card";
    const preview = s.text.split("\n").slice(0, 3).join("\n") + "…";
    btn.innerHTML = `<div class="sample-card-title">${escHtml(s.label)}</div>
      <div class="sample-card-text">${escHtml(preview)}</div>`;
    btn.onclick = () => runSample(s);
    list.appendChild(btn);
  });
}

// ── Voice language toggle ─────────────────────────────────
function toggleVoiceLangs() {
  const cb  = document.getElementById("enable-voice");
  const row = document.getElementById("voice-lang-row");
  if (row) row.style.display = cb && cb.checked ? "flex" : "none";
}

function getSelectedLangs() {
  const boxes = document.querySelectorAll('input[name="voice_lang"]:checked');
  return Array.from(boxes).map(b => b.value);
}

// ── Stage management ──────────────────────────────────────
function showStage(id) {
  document.querySelectorAll(".stage").forEach(s => s.classList.remove("active"));
  document.getElementById("stage-" + id).classList.add("active");
}

function resetApp() {
  currentData = null; uploadedBlob = null;
  ["file-input","manual-text","prescription-title"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.value = "";
  });
  ["upload-error","btn-reset","sidebar-image-wrap","saved-notice"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.style.display = "none";
  });
  showStage("upload");
}

function switchMode(mode, event) {
  document.querySelectorAll(".mode-tab").forEach(t => t.classList.remove("active"));
  if (event?.currentTarget) event.currentTarget.classList.add("active");
  const up = document.getElementById("mode-upload");
  const tx = document.getElementById("mode-text");
  if (up) up.style.display = mode === "upload" ? "" : "none";
  if (tx) tx.style.display = mode === "text"   ? "" : "none";
}

function switchTab(btn, tabId) {
  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById("tab-" + tabId)?.classList.add("active");
}

function switchLangTab(btn, lang) {
  document.querySelectorAll(".lang-tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".lang-panel").forEach(p => p.classList.remove("active"));
  btn.classList.add("active");
  document.getElementById("lang-panel-" + lang)?.classList.add("active");
}

// ── Drag & drop ───────────────────────────────────────────
function setupDragDrop() {
  const dz = document.getElementById("drop-zone");
  if (!dz) return;
  dz.addEventListener("dragover",  e => { e.preventDefault(); dz.classList.add("dragover"); });
  dz.addEventListener("dragleave", () => dz.classList.remove("dragover"));
  dz.addEventListener("drop", e => {
    e.preventDefault(); dz.classList.remove("dragover");
    const f = e.dataTransfer.files[0];
    if (f?.type?.startsWith("image/")) submitFile(f);
    else showError("Please drop an image file.");
  });
}

function handleFileSelect(input) {
  if (input.files[0]) submitFile(input.files[0]);
}

// ── Submit ────────────────────────────────────────────────
function submitFile(file) {
  uploadedBlob = URL.createObjectURL(file);
  const voice  = document.getElementById("enable-voice")?.checked;
  const langs  = getSelectedLangs();
  const title  = document.getElementById("prescription-title")?.value.trim() || "";
  const fd = new FormData();
  fd.append("image", file);
  if (voice && langs.length) { fd.append("voice", "true"); fd.append("langs", langs.join(",")); }
  if (title) fd.append("title", title);
  sendAnalysis(fd);
}

function analyzeText() {
  const text  = document.getElementById("manual-text")?.value.trim();
  const title = document.getElementById("prescription-title")?.value.trim() || "";
  if (!text) return showError("Please enter some prescription text.");
  uploadedBlob = null;
  sendAnalysis(JSON.stringify({ text, title }), "application/json");
}

function runSample(sample) {
  uploadedBlob = null;
  sendAnalysis(JSON.stringify({ text: sample.text, title: sample.label }), "application/json");
}

// ── API ───────────────────────────────────────────────────
function sendAnalysis(body, contentType) {
  hideError(); showStage("scanning"); setProgress(5, "Initializing…");
  const isForm = body instanceof FormData;
  const steps  = [
    [15, "Running EasyOCR + OpenCV…"],
    [40, "Extracting prescription text…"],
    [62, "Matching medicines in database…"],
    [78, "Checking drug interactions…"],
    [90, "Generating AI explanations…"],
  ];
  let si = 0;
  const timer = setInterval(() => {
    if (si < steps.length) setProgress(...steps[si++]);
    else clearInterval(timer);
  }, 700);

  const opts = { method: "POST", body };
  if (!isForm) opts.headers = { "Content-Type": contentType };

  fetch("/analyze", opts)
    .then(r => { if (r.redirected || r.status === 302) { window.location.href="/login"; throw new Error("redirect"); } return r.json(); })
    .then(data => {
      clearInterval(timer);
      if (data.error) { showError(data.error); showStage("upload"); return; }
      setProgress(100, "Done!");
      setTimeout(() => renderResults(data), 300);
    })
    .catch(err => {
      clearInterval(timer);
      if (err.message !== "redirect") { showError("Network error: " + err.message); showStage("upload"); }
    });
}

function setProgress(pct, step) {
  const pb = document.getElementById("progress-bar");
  const pp = document.getElementById("progress-pct");
  const ps = document.getElementById("scan-step");
  if (pb) pb.style.width = pct + "%";
  if (pp) pp.textContent = pct + "%";
  if (ps) ps.textContent = step;
}

// ── Render ────────────────────────────────────────────────
function renderResults(data) {
  currentData = data;
  showStage("results");
  const br = document.getElementById("btn-reset");
  if (br) br.style.display = "";

  renderSummary(data);
  renderCriticalBanner(data.interactions);
  renderMedicines(data.medicines);
  renderInteractions(data.interactions);
  renderSafety(data.safety_alerts);
  renderSchedule(data.schedules, data.timeline);
  renderOCR(data.ocr);
  renderSidebar(data);

  const sn = document.getElementById("saved-notice");
  if (sn && data.prescription_id) sn.style.display = "flex";

  document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
  document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
  document.querySelector('.tab[data-tab="medicines"]')?.classList.add("active");
  document.getElementById("tab-medicines")?.classList.add("active");
}

function renderSummary(data) {
  const crit   = data.interactions.filter(i => i.severity==="CRITICAL").length;
  const safety = Object.values(data.safety_alerts).flat().length;
  const cards  = [
    { label: "Medicines Found", value: data.medicines.length, color: "#06b6d4" },
    { label: "Interactions",    value: data.interactions.length, color: data.interactions.length ? "#ef4444":"#10b981" },
    { label: "Critical Alerts", value: crit,   color: crit   ? "#dc2626":"#10b981" },
    { label: "Safety Warnings", value: safety, color: safety ? "#f59e0b":"#10b981" },
  ];
  const grid = document.getElementById("summary-grid");
  if (grid) grid.innerHTML = cards.map(c => `
    <div class="summary-card">
      <div class="s-label">${c.label}</div>
      <div class="s-value" style="color:${c.color}">${c.value}</div>
    </div>`).join("");
}

function renderCriticalBanner(interactions) {
  const crits  = interactions.filter(i => i.severity==="CRITICAL");
  const banner = document.getElementById("critical-banner");
  if (!banner) return;
  if (!crits.length) { banner.style.display="none"; return; }
  banner.style.display = "flex";
  banner.innerHTML = `🚨 ${crits.length} critical interaction${crits.length>1?"s":""} detected: ` +
    crits.map(c=>`<strong>${escHtml(c.drug_a)} + ${escHtml(c.drug_b)}</strong>`).join(", ") +
    " — consult your doctor immediately.";
}

function renderMedicines(medicines) {
  const panel = document.getElementById("tab-medicines");
  if (!panel) return;
  if (!medicines.length) {
    panel.innerHTML = `<div class="no-issues green">
      <div class="no-issues-icon">🔍</div>
      <div class="no-issues-title">No medicines detected</div>
      <div class="no-issues-sub">Check the OCR Text tab to see what was extracted, or try a clearer image.</div>
    </div>`; return;
  }
  panel.innerHTML = `<div class="med-cards">${medicines.map(m => medCardHTML(m)).join("")}</div>`;
}

function medCardHTML(m) {
  const badges = [
    m.warnings.pregnancy ? `<span class="badge badge-preg">Preg</span>` : "",
    m.warnings.liver     ? `<span class="badge badge-liver">Liver</span>` : "",
    m.warnings.kidney    ? `<span class="badge badge-kidney">Kidney</span>` : "",
  ].join("");
  const sePills = (m.side_effects||[]).map(s=>`<span class="se-pill">${escHtml(s)}</span>`).join("");
  const expl = m.explanation
    ? `<div class="ai-expl-box"><div class="ai-expl-label">✨ AI PLAIN-LANGUAGE EXPLANATION</div><div class="ai-expl-text">${escHtml(m.explanation)}</div></div>`
    : `<button class="btn-ai" onclick="loadExplanation('${m.key}',this)">✨ Get AI Explanation</button>`;
  return `
    <div class="med-card" id="medcard-${m.key}">
      <button class="med-card-header" onclick="toggleMedCard('${m.key}')">
        <div class="med-dot-wrap" style="background:${m.color}22"><div class="med-dot" style="background:${m.color}"></div></div>
        <div class="med-info">
          <div class="med-name">${escHtml(m.generic)}</div>
          <div class="med-sub">${escHtml((m.brand||[]).slice(0,2).join(", "))} · ${escHtml(m.category)}</div>
        </div>
        <div class="med-badges">${badges}</div>
        <svg class="chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>
      </button>
      <div class="med-card-body">
        <div class="med-grid">
          <div class="med-info-cell"><div class="cell-label">Uses</div><div class="cell-text">${escHtml(m.uses)}</div></div>
          <div class="med-info-cell"><div class="cell-label">Dosage</div><div class="cell-text">${escHtml(m.dosage)}</div></div>
        </div>
        <div class="side-effects-row">
          <div class="se-label">Side Effects</div>
          <div class="se-pills">${sePills}</div>
        </div>
        <div id="expl-${m.key}">${expl}</div>
      </div>
    </div>`;
}

function toggleMedCard(key) { document.getElementById("medcard-"+key)?.classList.toggle("open"); }

function loadExplanation(key, btn) {
  btn.disabled = true; btn.textContent = "Loading…";
  const wrap = document.getElementById("expl-"+key);
  if (wrap) wrap.innerHTML = `<div class="ai-loading"><div class="mini-spinner"></div> Generating AI explanation…</div>`;
  fetch(`/explain/${key}`,{method:"POST"}).then(r=>r.json()).then(d=>{
    if (wrap) wrap.innerHTML = `<div class="ai-expl-box"><div class="ai-expl-label">✨ AI PLAIN-LANGUAGE EXPLANATION</div><div class="ai-expl-text">${escHtml(d.explanation||"Explanation unavailable.")}</div></div>`;
  }).catch(()=>{ if(wrap) wrap.innerHTML=`<div class="ai-expl-box"><div class="ai-expl-text">Could not load explanation.</div></div>`; });
}

function renderInteractions(interactions) {
  const panel = document.getElementById("tab-interactions");
  if (!panel) return;
  if (!interactions.length) {
    panel.innerHTML=`<div class="no-issues green"><div class="no-issues-icon">✅</div><div class="no-issues-title">No dangerous interactions detected</div><div class="no-issues-sub">The detected medicines appear safe to take together.</div></div>`;
    return;
  }
  panel.innerHTML=`<div class="int-cards">${interactions.map(i=>`
    <div class="int-card ${i.severity}">
      <div class="int-header">
        <span class="severity-badge ${i.severity}">${i.severity==="CRITICAL"?"🚨":i.severity==="HIGH"?"⚠️":"💛"} ${i.severity}</span>
        <span class="int-drugs">${escHtml(i.drug_a)} + ${escHtml(i.drug_b)}</span>
      </div>
      <div class="int-msg">${escHtml(i.message)}</div>
    </div>`).join("")}</div>`;
}

function renderSafety(alerts) {
  const panel = document.getElementById("tab-safety");
  if (!panel) return;
  const groups=[
    {key:"pregnancy",cls:"pregnancy",icon:"🤰",title:"Pregnant Women",         sub:"These medicines may be unsafe during pregnancy."},
    {key:"liver",    cls:"liver",    icon:"🫀",title:"Liver Disease Patients",  sub:"Requires extra caution or dose adjustment."},
    {key:"kidney",   cls:"kidney",   icon:"🫘",title:"Kidney Disease Patients", sub:"May accumulate or worsen kidney function."},
  ];
  panel.innerHTML=`<div class="safety-cards">${groups.map(g=>{
    const names=(alerts[g.key]||[]);
    const inner=names.length?names.map(n=>`<span class="safety-pill">⚠️ ${escHtml(n)}</span>`).join(""):`<span class="safe-label">✅ No flagged medicines for this group</span>`;
    return `<div class="safety-card ${g.cls}">
      <div class="safety-header"><span class="safety-icon">${g.icon}</span>
        <div><div class="safety-title">${g.title}</div><div class="safety-sub">${g.sub}</div></div>
      </div>
      <div class="safety-pills">${inner}</div>
    </div>`;
  }).join("")}</div>`;
}

function renderSchedule(schedules, timeline) {
  const panel = document.getElementById("tab-schedule");
  if (!panel) return;
  if (!schedules?.length) { panel.innerHTML=`<p style="color:var(--text-secondary);font-size:14px">No schedule information could be extracted.</p>`; return; }
  const cards=schedules.map(s=>{
    const med=(currentData?.medicines||[]).find(m=>m.key===s.key)||{};
    const color=med.color||"#06b6d4";
    const tags=[
      s.times_per_day>0?`<span class="sched-tag times">${s.times_per_day}×/day</span>`:"",
      s.food?`<span class="sched-tag food">${escHtml(s.food)}</span>`:"",
      s.duration?`<span class="sched-tag dur">${escHtml(s.duration)}</span>`:"",
    ].join("");
    return `<div class="sched-card">
      <div class="sched-dot-wrap" style="background:${color}22"><div class="med-dot" style="background:${color}"></div></div>
      <div><div class="sched-name">${escHtml(s.medicine)} ${s.dose?`<span style="color:var(--text-secondary);font-weight:400">${escHtml(s.dose)}</span>`:""}</div>
      <div class="sched-meta">${(s.schedule||[]).join(", ")}</div><div>${tags}</div></div>
    </div>`;
  }).join("");
  const tlRows=(timeline||[]).map(slot=>`
    <div class="timeline-row">
      <div class="t-time">${escHtml(slot.time)}</div>
      <div class="t-meds">${(slot.medicines||[]).map(m=>`
        <div class="t-med-chip">
          <div class="t-med-name">${escHtml(m.name)}</div>
          <div class="t-med-dose">${escHtml(m.dose||"")}</div>
          ${m.food?`<div class="t-med-food">${escHtml(m.food)}</div>`:""}
        </div>`).join("")}</div>
    </div>`).join("");
  panel.innerHTML=`<div class="sched-cards">${cards}</div>
    <p class="section-label" style="margin-bottom:12px">Daily Timeline</p>
    <div class="timeline">${tlRows}</div>`;
}

function renderOCR(ocr) {
  const panel=document.getElementById("tab-ocr");
  if (!panel) return;
  panel.innerHTML=`<div class="ocr-box">
    <div class="ocr-meta">Engine: <strong>${escHtml(ocr.engine)}</strong>${ocr.confidence?` · Confidence: <strong>${(ocr.confidence*100).toFixed(0)}%</strong>`:""}</div>
    <pre class="ocr-pre">${escHtml(ocr.text||"(No text extracted)")}</pre>
  </div>`;
}

function renderSidebar(data) {
  if (uploadedBlob) {
    const img=document.getElementById("sidebar-image");
    const wrap=document.getElementById("sidebar-image-wrap");
    if (img) img.src=uploadedBlob;
    if (wrap) wrap.style.display="";
  }
  const container=document.getElementById("sidebar-med-items");
  if (container) {
    container.innerHTML=!data.medicines.length
      ?`<p style="font-size:13px;color:var(--text-tertiary)">None detected</p>`
      :data.medicines.map(m=>`
        <div class="sb-med-item">
          <div class="sb-dot" style="background:${m.color}"></div>
          <div><div class="sb-med-name">${escHtml(m.generic)}</div><div class="sb-med-cat">${escHtml(m.category)}</div></div>
        </div>`).join("");
  }

  // ── Multilingual audio ───────────────────────────────────
  const audio       = data.audio || {};
  const audioSec    = document.getElementById("audio-section");
  const tabsEl      = document.getElementById("audio-lang-tabs");
  const panelsEl    = document.getElementById("audio-lang-panels");

  const isMulti = audio.en || audio.hi || audio.ta;

  if (audioSec && tabsEl && panelsEl && isMulti) {
    const langs = Object.keys(audio).filter(k => LANG_NAMES[k] && (audio[k].summary_url || audio[k].interaction_url || audio[k].schedule_url));
    if (langs.length) {
      audioSec.style.display = "";
      tabsEl.innerHTML = langs.map((l, i) =>
        `<button class="lang-tab${i===0?" active":""}" onclick="switchLangTab(this,'${l}')">${LANG_NAMES[l]}</button>`
      ).join("");
      panelsEl.innerHTML = langs.map((l, i) => {
        const ld = audio[l];
        const players = AUDIO_SECTIONS
          .filter(s => ld[s.key])
          .map(s => `<div class="audio-player-wrap">
            <div class="audio-player-label">${s.label}</div>
            <audio controls src="${ld[s.key]}"></audio>
          </div>`).join("");
        return `<div class="lang-panel${i===0?" active":""}" id="lang-panel-${l}">${players||"<p style='font-size:12px;color:var(--text-tertiary)'>Audio unavailable for this language.</p>"}</div>`;
      }).join("");
    } else {
      audioSec.style.display = "none";
    }
  } else if (audioSec && !isMulti && (audio.summary_url || audio.interaction_url)) {
    // Legacy single-language
    audioSec.style.display = "";
    if (tabsEl) tabsEl.innerHTML = `<button class="lang-tab active">🇬🇧 English</button>`;
    if (panelsEl) panelsEl.innerHTML = `<div class="lang-panel active">` +
      AUDIO_SECTIONS.filter(s=>audio[s.key]).map(s=>`<div class="audio-player-wrap">
        <div class="audio-player-label">${s.label}</div>
        <audio controls src="${audio[s.key]}"></audio>
      </div>`).join("") + `</div>`;
  } else if (audioSec) {
    audioSec.style.display = "none";
  }
}

function showError(msg) { const b=document.getElementById("upload-error"); if(b){b.textContent="⚠️ "+msg;b.style.display="";} }
function hideError()    { const b=document.getElementById("upload-error"); if(b) b.style.display="none"; }
function escHtml(str)   {
  if (str==null) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}
