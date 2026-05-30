// ════════════════════════════════════════
// SHARED DATA LAYER
// Persists across all pages via localStorage
// ════════════════════════════════════════


// ── API Key management ────────────────────────────────────────────────────────
// Key is stored in localStorage so users only enter it once.
// On GitHub Pages, each user provides their own free key.
function getGeminiKey() {
  var key = localStorage.getItem("jt_gemini_key") || "";
  return key;
}

function promptForKey() {
  var existing = getGeminiKey();
  var key = window.prompt(
    "Enter your Gemini API key to use AI features.\n\n" +
    "Get a FREE key at: aistudio.google.com\n" +
    "(No credit card needed — free tier is plenty)\n\n" +
    "Your key is saved locally in your browser only.",
    existing
  );
  if(key && key.trim()) {
    localStorage.setItem("jt_gemini_key", key.trim());
    return key.trim();
  }
  return existing;
}

function clearGeminiKey() {
  localStorage.removeItem("jt_gemini_key");
  showToast("API key cleared");
}

// Legacy support — some code uses GEMINI_KEY directly
var GEMINI_KEY = getGeminiKey();

// ── PDF config ───────────────────────────────────────────────────────────────
// On Vercel: calls /api/generate-pdf (same origin, no CORS issues)
// Locally:   calls http://localhost:5050 (run pdf_server.py)
function getPDFServerURL() {
  var isLocal = window.location.hostname === "localhost" ||
                window.location.hostname === "127.0.0.1";
  return isLocal ? "http://localhost:5050" : "/api/generate-pdf";
}

async function checkPDFServer() {
  try {
    var url = getPDFServerURL();
    // On Vercel, always available — just check local
    if(!url.startsWith("http://localhost")) return true;
    var res = await fetch(url.replace("/generate-pdf","") + "/health", {
      signal: AbortSignal.timeout(3000)
    });
    return res.ok;
  } catch(e) {
    return false;
  }
}

// ── Storage ───────────────────────────────────────────────────────────────────
var Store = {
  get: function(key) {
    try { var v = localStorage.getItem(key); return v ? JSON.parse(v) : null; } catch(e) { return null; }
  },
  set: function(key, val) {
    try { localStorage.setItem(key, JSON.stringify(val)); return true; } catch(e) { return false; }
  },
  // Save all data as one JSON blob for file export
  exportAll: function() {
    return {
      jobs:          Store.get("jt_jobs")       || [],
      jobIdCounter:  Store.get("jt_jobCounter") || 0,
      resume:        Store.get("jt_resume")     || {},
      coverLetter:   Store.get("jt_cl")         || {},
      resumeStyle:   Store.get("jt_resumeStyle") || {},
      clStyle:       Store.get("jt_clStyle")    || {},
    };
  },
  importAll: function(data) {
    if(data.jobs)         Store.set("jt_jobs",        data.jobs);
    if(data.jobIdCounter) Store.set("jt_jobCounter",  data.jobIdCounter);
    if(data.resume)       Store.set("jt_resume",      data.resume);
    if(data.coverLetter)  Store.set("jt_cl",          data.coverLetter);
    if(data.resumeStyle)  Store.set("jt_resumeStyle", data.resumeStyle);
    if(data.clStyle)      Store.set("jt_clStyle",     data.clStyle);
  }
};

// ── Gemini helpers ────────────────────────────────────────────────────────────
// ── Model fallback chain ──────────────────────────────────────────────────────
// Models tried in order when rate limits are hit (429).
// Primary is highest RPD; fallbacks used automatically.
var GEMINI_MODELS = [
  "gemini-3.1-flash-lite",   // Primary:  15 RPM, 500 RPD
  "gemini-2.5-flash-lite",   // Fallback: 10 RPM, 20 RPD
  "gemini-2.5-flash",        // Fallback:  5 RPM, 20 RPD
  "gemini-3-flash",          // Fallback:  5 RPM, 20 RPD
];

// Track which model is currently active (resets on page reload)
var GEMINI_MODEL = GEMINI_MODELS[0];
var _currentModelIndex = 0;

function getCurrentModelName() {
  return GEMINI_MODEL;
}

async function callGeminiWithModel(model, prompt, useSearch, key) {
  var body = { contents: [{ parts: [{ text: prompt }] }] };
  if(useSearch) body.tools = [{ url_context: {} }];
  var res = await fetch(
    "https://generativelanguage.googleapis.com/v1beta/models/" + model + ":generateContent?key=" + key,
    { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }
  );
  return res;
}

async function callGemini(prompt, useSearch) {
  var key = getGeminiKey();
  if(!key) {
    key = promptForKey();
    if(!key) throw new Error("No API key — enter your Gemini key to use AI features.");
  }

  // Try each model in the fallback chain
  for(var i = _currentModelIndex; i < GEMINI_MODELS.length; i++) {
    var model = GEMINI_MODELS[i];
    try {
      var res = await callGeminiWithModel(model, prompt, useSearch, key);

      // Bad API key
      if(res.status === 400 || res.status === 403) {
        localStorage.removeItem("jt_gemini_key");
        throw new Error("Invalid API key. Click any AI button to re-enter your key.");
      }

      // Rate limited — try next model
      if(res.status === 429) {
        console.warn("Rate limit hit on " + model + ", trying next model...");
        if(i + 1 < GEMINI_MODELS.length) {
          // Update active model for future calls this session
          _currentModelIndex = i + 1;
          GEMINI_MODEL = GEMINI_MODELS[_currentModelIndex];
          showToast("Rate limit reached — switching to " + GEMINI_MODEL, false);
          continue;
        } else {
          throw new Error("All models rate limited. Try again in a few minutes.");
        }
      }

      // Other error
      if(!res.ok) {
        throw new Error("Gemini error " + res.status + " on model " + model);
      }

      // Success — if we advanced models, stay on this one for the session
      if(i !== _currentModelIndex) {
        _currentModelIndex = i;
        GEMINI_MODEL = model;
      }

      var d = await res.json();
      return d.candidates?.[0]?.content?.parts?.[0]?.text || "";

    } catch(e) {
      // Re-throw non-rate-limit errors immediately
      if(!e.message.includes("Rate limit") && !e.message.includes("rate limit")) {
        throw e;
      }
    }
  }

  throw new Error("All models rate limited. Try again in a few minutes.");
}

function parseJSON(raw) {
  var clean = raw.replace(/```json|```/g, "").trim();
  try { return JSON.parse(clean); } catch(e) {
    var m = clean.match(/\{[\s\S]*\}/);
    if(m) return JSON.parse(m[0]);
    throw new Error("Could not parse JSON");
  }
}

// ── Shared helpers ────────────────────────────────────────────────────────────
function esc(s) { return (s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function el(id)  { return document.getElementById(id); }
function v(id)   { return (el(id)?.value||"").trim(); }

function showToast(msg, err) {
  var t = el("toast");
  if(!t) return;
  t.textContent = msg;
  t.className = "toast" + (err ? " err" : "");
  void t.offsetWidth;
  t.classList.add("show");
  setTimeout(function(){ t.classList.remove("show"); }, 3000);
}

// ── Resume plain text (for scoring) ──────────────────────────────────────────
function buildResumePlainText(r) {
  r = r || Store.get("jt_resume") || {};
  var expText = (r.expEntries||[]).map(function(e){
    return (e.title||"") + " at " + (e.company||"") + ": " + (e.bullets||"");
  }).join("\n");
  return "NAME: "+(r.fname||"")+" "+(r.lname||"")+
    "\nSUMMARY:\n"+(r.summary||"")+
    "\nEXPERIENCE:\n"+expText+
    "\nEDUCATION:\n"+(r.eduEntries||[]).map(function(e){ return (e.degree||"")+" — "+(e.school||""); }).join("\n")+
    "\nSKILLS:\n"+(r.skills||"")+
    "\nCERTIFICATIONS:\n"+(r.certs||"");
}

// ── Shared CSS variables ──────────────────────────────────────────────────────
var SHARED_CSS = `
  *,*::before,*::after{box-sizing:border-box;margin:0;padding:0}
  :root{
    --bg:#f0ede8;--surface:#fff;--border:#e5e5e5;--border2:#d0d0d0;
    --ink:#1a1a1a;--ink2:#444;--ink3:#888;--ink4:#aaa;
    --accent:#e91e8c;--accent-bg:#fff0f7;--accent2:#c41678;
    --blue:#2563eb;--green:#16a34a;--orange:#d97706;--red:#dc2626;
    --radius:10px;--sidebar:220px;
  }
  body{font-family:'Inter',sans-serif;background:var(--bg);color:var(--ink);margin:0}
  a{text-decoration:none;color:inherit}

  /* Sidebar */
  .sidebar{position:fixed;left:0;top:0;bottom:0;width:var(--sidebar);background:var(--surface);
    border-right:1px solid var(--border);display:flex;flex-direction:column;z-index:50;padding:16px 12px}
  .sidebar-logo{display:flex;align-items:center;gap:10px;padding:8px 8px 20px;margin-bottom:4px}
  .sidebar-logo .logo-icon{width:36px;height:36px;background:linear-gradient(135deg,#e91e8c,#fc6767);
    border-radius:10px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:18px;font-weight:800}
  .sidebar-logo .logo-text{font-size:16px;font-weight:700;color:var(--ink)}
  .sidebar-logo .logo-text span{color:var(--accent)}
  .sidebar-nav{display:flex;flex-direction:column;gap:2px;flex:1}
  .sidebar-item{display:flex;align-items:center;gap:10px;padding:9px 12px;border-radius:8px;
    font-size:14px;font-weight:500;color:var(--ink2);cursor:pointer;transition:.15s;border:none;background:none;width:100%;text-align:left}
  .sidebar-item:hover{background:var(--bg);color:var(--ink)}
  .sidebar-item.active{background:#f3f4f6;color:var(--ink);font-weight:600}
  .sidebar-item svg{width:18px;height:18px;flex-shrink:0}
  .sidebar-bottom{margin-top:auto;padding-top:12px;border-top:1px solid var(--border);display:flex;flex-direction:column;gap:4px}

  /* Main content area */
  .main{margin-left:var(--sidebar);min-height:100vh;display:flex;flex-direction:column}

  /* Top nav */
  .topnav{height:52px;background:var(--surface);border-bottom:1px solid var(--border);
    display:flex;align-items:center;padding:0 20px;gap:4px;position:sticky;top:0;z-index:40}
  .topnav-tab{display:flex;align-items:center;gap:6px;padding:6px 16px;border-radius:8px;
    border:none;background:none;font:500 13px 'Inter',sans-serif;color:var(--ink3);cursor:pointer;transition:.15s}
  .topnav-tab:hover{background:var(--bg);color:var(--ink)}
  .topnav-tab.active{background:var(--accent-bg);color:var(--accent)}
  .topnav-right{margin-left:auto;display:flex;gap:8px;align-items:center}
  .btn{height:34px;padding:0 14px;border-radius:8px;font:500 13px 'Inter',sans-serif;cursor:pointer;
    display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);
    background:var(--surface);color:var(--ink2);transition:.15s;white-space:nowrap}
  .btn:hover{border-color:var(--ink4);color:var(--ink)}
  .btn:disabled{opacity:.4;cursor:not-allowed}
  .btn-accent{background:var(--accent);color:#fff;border-color:var(--accent)}
  .btn-accent:hover{background:var(--accent2);border-color:var(--accent2);color:#fff}
  .btn-sm{height:28px;padding:0 10px;font-size:12px}
  .btn-ghost{background:none;border:none;color:var(--ink3);padding:0 8px;border-radius:6px;cursor:pointer;font:400 12px 'Inter',sans-serif;height:28px}
  .btn-ghost:hover{background:var(--bg)}

  /* Content area */
  .content-area{flex:1;overflow-y:auto;padding:24px}
  .content-area::-webkit-scrollbar{width:4px}
  .content-area::-webkit-scrollbar-thumb{background:var(--border);border-radius:4px}

  /* Cards */
  .card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:16px}
  .card-title{font-size:18px;font-weight:700;margin-bottom:16px;color:var(--ink)}

  /* Form fields */
  .field{display:flex;flex-direction:column;gap:4px;margin-bottom:12px}
  .field label{font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--ink3)}
  .field input,.field select,.field textarea{border:1px solid var(--border);border-radius:8px;
    padding:8px 10px;font:400 13px 'Inter',sans-serif;color:var(--ink);background:var(--surface);width:100%}
  .field input:focus,.field select:focus,.field textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(233,30,140,.08)}
  .field textarea{resize:vertical;min-height:80px;line-height:1.6}
  .field-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}
  .hint{font-size:11px;color:var(--ink3);line-height:1.5;margin-top:-6px}

  /* Entry cards */
  .entry-card{border:1px solid var(--border);border-radius:8px;margin-bottom:10px;overflow:visible}
  .entry-card-head{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:#fafafa;border-bottom:1px solid var(--border)}
  .entry-title{font-size:13px;font-weight:600;color:var(--ink)}
  .entry-sub{font-size:11px;color:var(--ink3);margin-top:1px}
  .entry-fields{padding:14px;display:flex;flex-direction:column;gap:10px}
  .add-entry-btn{display:flex;align-items:center;justify-content:center;gap:6px;padding:10px;
    border:1.5px dashed var(--border2);border-radius:8px;background:none;
    font:500 12px 'Inter',sans-serif;color:var(--ink3);cursor:pointer;width:100%;transition:.15s;margin-top:4px}
  .add-entry-btn:hover{border-color:var(--accent);color:var(--accent);background:var(--accent-bg)}
  .simple-textarea{border:1px solid var(--border);border-radius:8px;width:100%;padding:9px;
    font:400 13px 'Inter',sans-serif;color:var(--ink);line-height:1.7;resize:vertical;min-height:80px}
  .simple-textarea:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(233,30,140,.08)}

  /* AI Panel */
  .ai-panel{background:linear-gradient(135deg,#fff0f7,#f0f4ff);border:1px solid #f0c0dd;
    border-radius:var(--radius);padding:16px;display:flex;flex-direction:column;gap:10px}
  .ai-panel-title{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--accent)}
  .ai-panel textarea,.ai-panel select{border:1px solid #f0c0dd;border-radius:6px;padding:8px 10px;
    font:400 12px 'Inter',sans-serif;color:var(--ink);width:100%;resize:vertical;min-height:80px;line-height:1.6;background:#fff}
  .ai-panel textarea:focus,.ai-panel select:focus{outline:none;border-color:var(--accent)}
  .ai-status{font-size:12px;color:var(--accent);min-height:16px}
  .ai-status.err{color:var(--red)}
  .spinner{width:13px;height:13px;border:2px solid rgba(233,30,140,.2);border-top-color:var(--accent);
    border-radius:50%;animation:spin .6s linear infinite;display:inline-block;vertical-align:middle;margin-right:4px}
  @keyframes spin{to{transform:rotate(360deg)}}

  /* Customize controls */
  .section-block{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);overflow:visible;margin-bottom:10px}
  .section-head{display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;user-select:none;transition:.15s}
  .section-head:hover{background:#fafafa}
  .section-icon{width:28px;height:28px;border-radius:7px;display:flex;align-items:center;justify-content:center;font-size:14px;background:#f3f4f6;flex-shrink:0}
  .section-head h3{font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--ink2);flex:1}
  .chevron{font-size:10px;color:var(--ink4);transition:transform .2s}
  .section-block.open .chevron{transform:rotate(180deg)}
  .section-body{display:none;padding:0 14px 14px;flex-direction:column;gap:10px}
  .section-block.open .section-body{display:flex}
  input[type=range]{width:100%;accent-color:var(--accent);cursor:pointer}
  input[type=color]{width:100%;border:1px solid var(--border);border-radius:6px;padding:2px;background:var(--surface);cursor:pointer;height:34px}
  .template-thumb{display:flex;flex-direction:column;align-items:center;gap:5px;cursor:pointer;
    padding:6px;border-radius:8px;border:1.5px solid var(--border);transition:.15s}
  .template-thumb:hover,.template-thumb.active{border-color:var(--accent);background:var(--accent-bg)}
  .template-thumb span{font-size:10px;font-weight:500;color:var(--ink2)}

  /* Toast */
  .toast{position:fixed;bottom:20px;left:50%;transform:translateX(-50%) translateY(60px);
    background:var(--ink);color:#fff;border-radius:8px;padding:10px 18px;font-size:13px;
    font-weight:500;box-shadow:0 4px 20px rgba(0,0,0,.2);transition:transform .3s;z-index:999;white-space:nowrap}
  .toast.show{transform:translateX(-50%) translateY(0)}
  .toast.err{background:var(--red)}

  /* Icon button */
  .icon-btn{width:26px;height:26px;border:none;background:none;cursor:pointer;border-radius:6px;
    display:flex;align-items:center;justify-content:center;color:var(--ink3);font-size:14px;transition:.15s}
  .icon-btn:hover{background:var(--bg);color:var(--ink)}
  .icon-btn.del:hover{background:#fee2e2;color:var(--red)}

  /* Resume paper */
  .paper-wrap{background:#888;padding:28px 20px;min-height:100%;display:flex;justify-content:center;align-items:flex-start}
  .paper{width:210mm;background:#fff;box-shadow:0 4px 40px rgba(0,0,0,.25);flex-shrink:0}
  .rv{padding:10mm 12mm;font-family:'Inter',sans-serif;color:#111;font-size:10px}
  .rv-name{font-size:22px;font-weight:800;text-align:center;margin-bottom:6px}
  .rv-contacts{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:2px 14px;margin-bottom:10px}
  .rv-contact-item{display:flex;align-items:center;gap:4px;font-size:9px;color:#444}
  .rv-contact-item svg{width:10px;height:10px;color:#888;flex-shrink:0}
  .rv-divider{border:none;border-top:1.5px solid #111;margin-bottom:8px}
  .rv-section{margin-bottom:8px}
  .rv-section-title{font-size:9.5px;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#111;margin-bottom:4px;padding-bottom:2px;border-bottom:.5px solid #ddd}
  .rv-summary{font-size:9.5px;line-height:1.7;color:#222}
  .rv-entry{margin-bottom:7px}
  .rv-entry-head{display:flex;align-items:baseline;justify-content:space-between;gap:8px}
  .rv-entry-company{font-size:10px;font-weight:700;color:#111}
  .rv-entry-dates{font-size:9px;color:#555;white-space:nowrap;flex-shrink:0}
  .rv-entry-title{font-size:9.5px;font-style:italic;color:#333;margin-bottom:3px}
  .rv-bullets{margin-top:3px;padding-left:12px}
  .rv-bullets li{font-size:9.5px;line-height:1.6;color:#222;margin-bottom:1px}
  .rv-edu-head{display:flex;justify-content:space-between;align-items:baseline}
  .rv-edu-school{font-size:10px;font-weight:700}
  .rv-edu-dates{font-size:9px;color:#555}
  .rv-edu-degree{font-size:9.5px;font-style:italic;color:#333}
  .rv-edu-note{font-size:9.5px;color:#222;margin-top:2px}
  .rv-skills,.rv-certs{font-size:9.5px;line-height:1.8;color:#222}

  /* Cover letter paper */
  .cl-paper{width:210mm;background:#fff;box-shadow:0 4px 40px rgba(0,0,0,.25);flex-shrink:0;padding:18mm 20mm;font-family:'Inter',sans-serif}
  .cl-header-name{font-size:20px;font-weight:800;text-align:center;color:#111;margin-bottom:5px}
  .cl-header-contacts{display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:2px 14px;margin-bottom:8px}
  .cl-header-contact-item{display:flex;align-items:center;gap:4px;font-size:9px;color:#444}
  .cl-header-contact-item svg{width:10px;height:10px;color:#888;flex-shrink:0}
  .cl-header-divider{border:none;border-top:1.5px solid #111;margin-bottom:14px}
  .cl-date{font-size:10px;color:#444;margin-bottom:14px}
  .cl-recipient-block{margin-bottom:16px}
  .cl-recipient-company{font-size:10.5px;font-weight:700;color:#111}
  .cl-recipient-addr{font-size:10px;color:#555;line-height:1.6}
  .cl-para{font-size:10.5px;line-height:1.85;color:#222;margin-bottom:12px;text-align:justify}
  .cl-body-paragraphs{margin-bottom:20px}
  .cl-signoff{font-size:10.5px;color:#222;margin-bottom:32px}
  .cl-sig-line{width:80px;border-top:1.5px solid #111;margin:4px 0 4px}
  .cl-sign-name{font-size:12px;font-weight:700;color:#111}

  @media print{
    .sidebar,.topnav{display:none!important}
    .main{margin-left:0}
    .paper-wrap{background:#fff;padding:0}
    .paper,.cl-paper{box-shadow:none;width:100%}
  }
`;

// ── Sidebar HTML ──────────────────────────────────────────────────────────────

// ── Supabase Auth & Data ──────────────────────────────────────────────────────

async function getSupabase() {
  // Strict singleton — one client per browser tab, ever
  if(window.__jt_sb) return window.__jt_sb;

  // Load SDK if not already present
  if(!window.supabase) {
    // Don't add a second script tag if one is already loading
    if(!window.__jt_sb_loading) {
      window.__jt_sb_loading = new Promise(function(resolve, reject) {
        if(document.querySelector('script[src*="supabase"]')) {
          var check = setInterval(function(){
            if(window.supabase){ clearInterval(check); resolve(); }
          }, 50);
          return;
        }
        var cdns = [
          "/supabase.min.js",
          "https://unpkg.com/@supabase/supabase-js@2/dist/umd/supabase.min.js",
          "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"
        ];
        function tryNext(i) {
          if(i >= cdns.length){ reject(new Error("Supabase SDK failed to load")); return; }
          var s = document.createElement("script");
          s.src = cdns[i];
          s.onload = resolve;
          s.onerror = function(){ tryNext(i+1); };
          document.head.appendChild(s);
        }
        tryNext(0);
      });
    }
    await window.__jt_sb_loading;
  }

  // Only create the client once
  if(!window.__jt_sb) {
    try {
      var res = await fetch("/api/config");
      var cfg = await res.json();
      if(cfg.supabaseUrl && cfg.supabaseAnon) {
        window.__jt_sb = window.supabase.createClient(cfg.supabaseUrl, cfg.supabaseAnon, {
          auth: { storageKey: "jt_auth", persistSession: true }
        });
      }
    } catch(e) { console.warn("Supabase config error:", e); }
  }
  return window.__jt_sb || null;
}

async function requireAuth() {
  var sb = await getSupabase();
  if(!sb) return null;

  return new Promise(function(resolve) {
    // onAuthStateChange fires immediately with current session state
    var unsub = sb.auth.onAuthStateChange(function(event, session) {
      unsub.data.subscription.unsubscribe();
      if(session) {
        resolve(session.user);
      } else {
        if(!window.location.href.includes("login.html")) {
          window.location.href = "login.html";
        }
        resolve(null);
      }
    });
  });
}

async function getUser() {
  var sb = await getSupabase();
  if(!sb) return null;
  var { data } = await sb.auth.getSession();
  return data.session ? data.session.user : null;
}

async function signOut() {
  var sb = await getSupabase();
  if(sb) await sb.auth.signOut();
  window.location.href = "login.html";
}

// ── Core db helpers ───────────────────────────────────────────────────────────
async function _dbUpsert(table, fields) {
  var sb = await getSupabase();
  var user = await getUser();
  if(!sb) { console.warn("_dbUpsert: Supabase not initialized"); return false; }
  if(!user) { console.warn("_dbUpsert: No user session"); return false; }
  
  var payload = Object.assign({ updated_at: new Date().toISOString() }, fields);
  
  // Check if row exists using limit(1) — more reliable than maybeSingle()
  var checkResult = await sb.from(table).select("id").eq("user_id", user.id).limit(1);
  if(checkResult.error) {
    console.error("_dbUpsert select error on", table, ":", checkResult.error.message);
    showToast("DB error: " + checkResult.error.message, true);
    return false;
  }
  
  var result;
  if(checkResult.data && checkResult.data.length > 0) {
    result = await sb.from(table).update(payload).eq("user_id", user.id);
  } else {
    result = await sb.from(table).insert(Object.assign({ user_id: user.id }, payload));
  }
  
  if(result.error) {
    console.error("_dbUpsert write error on", table, ":", result.error.message);
    showToast("Save failed: " + result.error.message, true);
    return false;
  }
  
  console.log("_dbUpsert success:", table);
  return true;
}

async function dbSave(table, dataObj) {
  Store.set("jt_" + table, dataObj);
  await _dbUpsert(table, { data: dataObj });
}

async function dbSaveStyle(table, styleObj) {
  Store.set("jt_" + table + "Style", styleObj);
  await _dbUpsert(table, { style: styleObj });
}



async function dbLoad(table) {
  var sb = await getSupabase();
  var user = await getUser();
  if(!sb || !user) return Store.get("jt_" + table);
  try {
    var result = await sb.from(table).select("data").eq("user_id", user.id).limit(1);
    if(result.data && result.data.length > 0 && result.data[0].data) {
      Store.set("jt_" + table, result.data[0].data);
      return result.data[0].data;
    }
  } catch(e) { console.warn("dbLoad error:", e); }
  return Store.get("jt_" + table);
}

async function dbLoadStyle(table) {
  var sb = await getSupabase();
  var user = await getUser();
  if(!sb || !user) return Store.get("jt_" + table + "Style");
  try {
    var result = await sb.from(table).select("style").eq("user_id", user.id).limit(1);
    if(result.data && result.data.length > 0 && result.data[0].style) {
      Store.set("jt_" + table + "Style", result.data[0].style);
      return result.data[0].style;
    }
  } catch(e) { console.warn("dbLoadStyle error:", e); }
  return Store.get("jt_" + table + "Style");
}

async function dbSaveJobs(jobs) {
  Store.set("jt_jobs", jobs);
  var sb = await getSupabase();
  var user = await getUser();
  if(!sb || !user) return;
  try {
    var jobsCheck = await sb.from("jobs")
      .select("id").eq("user_id", user.id).eq("job_id", "all").limit(1);
    var existing = jobsCheck.data && jobsCheck.data.length > 0 ? jobsCheck.data[0] : null;
    if(existing) {
      await sb.from("jobs").update({
        data: jobs, updated_at: new Date().toISOString()
      }).eq("user_id", user.id).eq("job_id", "all");
    } else {
      await sb.from("jobs").insert({
        user_id: user.id, job_id: "all",
        data: jobs, updated_at: new Date().toISOString()
      });
    }
  } catch(e) { console.warn("Supabase jobs save failed:", e.message || e); }
}

async function dbLoadJobs() {
  var sb = await getSupabase();
  var user = await getUser();
  if(!sb || !user) return Store.get("jt_jobs") || [];
  var jobsLoad = await sb.from("jobs").select("data").eq("user_id", user.id).eq("job_id", "all").limit(1);
  if(jobsLoad.data && jobsLoad.data.length > 0 && jobsLoad.data[0].data) {
    Store.set("jt_jobs", jobsLoad.data[0].data);
    return jobsLoad.data[0].data;
  }
  return Store.get("jt_jobs") || [];
}

function renderSidebar(activePage) {
  var pages = [
    { id:"resume",       href:"resume.html",       icon:"📄", label:"Resume" },
    { id:"cover-letter", href:"cover-letter.html",  icon:"💌", label:"Cover Letter" },
    { id:"tracker",      href:"app.html",         icon:"💼", label:"Job Tracker" },
  ];
  var nav = pages.map(function(p) {
    return '<a href="'+p.href+'"><button class="sidebar-item'+(activePage===p.id?' active':'')+'" onclick="">'+
      '<span style="font-size:17px">'+p.icon+'</span>'+p.label+'</button></a>';
  }).join("");
  return '<div class="sidebar">'+
    '<div class="sidebar-logo">'+
      '<div class="logo-icon">J</div>'+
      '<div class="logo-text">Job<span>Tracker</span></div>'+
    '</div>'+
    '<nav class="sidebar-nav">'+nav+'</nav>'+
    '<div class="sidebar-bottom">'+
      '<button class="sidebar-item" onclick="exportData()"><span style="font-size:17px">💾</span>Save</button>'+
      '<label class="sidebar-item" style="cursor:pointer"><span style="font-size:17px">📂</span>Load<input type="file" accept=".json" onchange="importData(event)" style="display:none"/></label>'+
      '<button class="sidebar-item" onclick="promptForKey()" title="Set your Gemini API key for AI features">'+
        '<span style="font-size:17px">🔑</span>'+
        '<span style="flex:1">API Key</span>'+
        '<span id="key-status-dot" style="width:8px;height:8px;border-radius:50%;background:'+(getGeminiKey()?"#16a34a":"#dc2626")+';flex-shrink:0"></span>'+
      '</button>'+
      '<button class="sidebar-item" onclick="signOut()" style="color:#e91e8c">'+
        '<span style="font-size:17px">🚪</span>Sign Out'+
      '</button>'+
    '</div>'+
  '</div>';
}

// ── Export / Import ───────────────────────────────────────────────────────────
function exportData() {
  var data = Store.exportAll();
  var blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  var a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "jobtracker_data.json";
  a.click();
  URL.revokeObjectURL(a.href);
  showToast("Saved to jobtracker_data.json");
}

function importData(event) {
  var file = event.target.files[0];
  if(!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    try {
      Store.importAll(JSON.parse(e.target.result));
      showToast("Data loaded! Refreshing…");
      setTimeout(function(){ location.reload(); }, 800);
    } catch(err) {
      showToast("Could not read file", true);
    }
  };
  reader.readAsText(file);
}

// Expose globally
window.exportData = exportData;
window.getGeminiKey = getGeminiKey;
window.requireAuth = requireAuth;
window.getUser = getUser;
window.signOut = signOut;
window.dbSave = dbSave;
window.dbLoad = dbLoad;
window.dbSaveStyle = dbSaveStyle;
window.dbLoadStyle = dbLoadStyle;
window.dbSaveJobs = dbSaveJobs;
window.dbLoadJobs = dbLoadJobs;
window.promptForKey = promptForKey;
window.clearGeminiKey = clearGeminiKey;
window.importData = importData;
window.showToast  = showToast;
window.esc = esc;
window.el  = el;
window.v   = v;
window.callGemini = callGemini;
window.parseJSON  = parseJSON;
window.buildResumePlainText = buildResumePlainText;
window.Store = Store;
window.renderSidebar = renderSidebar;
window.SHARED_CSS = SHARED_CSS;
window.GEMINI_KEY = GEMINI_KEY;
window.GEMINI_MODEL = GEMINI_MODEL;
