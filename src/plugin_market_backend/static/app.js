/* Neo-MoFox Plugin Market - single-page frontend. */
(() => {
  "use strict";

  const qs = (sel, root = document) => root.querySelector(sel);
  const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const escape = (value) =>
    String(value ?? "").replace(/[&<>"']/g, (c) => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  const formatNumber = (n) => { n = Number(n||0); if(n>=1e6) return (n/1e6).toFixed(1)+"M"; if(n>=1e3) return (n/1e3).toFixed(1)+"k"; return String(n); };
  const formatBytes = (n) => { n = Number(n||0); if(n<1024) return n+" B"; if(n<1048576) return (n/1024).toFixed(1)+" KB"; return (n/1048576).toFixed(2)+" MB"; };

  const parseApiDate = (value) => {
    if (!value) return null;
    if (value instanceof Date) return Number.isNaN(value.getTime()) ? null : value;
    const text = String(value).trim();
    if (!text) return null;
    const normalized = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?$/.test(text)
      ? text.replace(" ", "T") + "Z"
      : text;
    const parsed = new Date(normalized);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  };

  const formatRelative = (value) => {
    const parsed = parseApiDate(value);
    if (!parsed) return "\u2014";
    const diff = Math.max(0, Date.now() - parsed.getTime());
    const m=60000, h=3600000, d=86400000;
    if (diff < m) return "\u521a\u521a";
    if (diff < h) return Math.floor(diff/m)+" \u5206\u949f\u524d";
    if (diff < d) return Math.floor(diff/h)+" \u5c0f\u65f6\u524d";
    if (diff < 30*d) return Math.floor(diff/d)+" \u5929\u524d";
    if (diff < 365*d) return Math.floor(diff/(30*d))+" \u4e2a\u6708\u524d";
    return Math.floor(diff/(365*d))+" \u5e74\u524d";
  };

  const formatDate = (v) => {
    const parsed = parseApiDate(v);
    return parsed ? parsed.toLocaleDateString(undefined,{year:"numeric",month:"short",day:"numeric"}) : "\u2014";
  };

  const starMarkup = (score) => {
    const pct = (Math.max(0,Math.min(5,Number(score)||0))/5)*100;
    return '<span class="stars" aria-hidden="true">\u2605\u2605\u2605\u2605\u2605<span class="fill" style="width:'+pct+'%">\u2605\u2605\u2605\u2605\u2605</span></span>';
  };

  const iconSvg = {
    heart:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>',
    download:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>',
    message:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
    github:'<svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12"></path></svg>',
  };

  const CATEGORY_LABELS = Object.freeze({
    ai: "AI增强",
    automation: "自动化",
    dev: "开发辅助",
    devtools: "开发工具",
    education: "学习教育",
    fun: "休闲娱乐",
    game: "游戏相关",
    image: "图像处理",
    life: "生活服务",
    media: "音视频",
    productivity: "效率办公",
    social: "社交互动",
    tool: "实用工具",
    tools: "工具合集",
    utility: "实用增强",
  });

  function categoryLabel(value) {
    const raw = String(value ?? "").trim();
    if (!raw) return "";
    return CATEGORY_LABELS[raw] || CATEGORY_LABELS[raw.toLowerCase()] || raw;
  }

  function categoryTagMarkup(value) {
    const raw = String(value ?? "").trim();
    const label = categoryLabel(raw);
    return `<span class="tag cat" title="${escape(raw)}">${escape(label)}</span>`;
  }

  // ---------- API ----------
  const API = {
    async request(path, {method="GET",body,expect="json"}={}) {
      const opts = {method, credentials:"include", headers:{}};
      if (body !== undefined) { opts.headers["Content-Type"]="application/json"; opts.body=typeof body==="string"?body:JSON.stringify(body); }
      const r = await fetch(path, opts);
      if (r.status===204) return null;
      const data = expect==="json" ? await r.json().catch(()=>null) : await r.text();
      if (!r.ok) { const err=new Error(data?.error?.message||r.statusText||"Request failed"); err.status=r.status; err.code=data?.error?.code; throw err; }
      return data;
    },
    get(p){return this.request(p)},
    post(p,b){return this.request(p,{method:"POST",body:b??{}})},
    put(p,b){return this.request(p,{method:"PUT",body:b??{}})},
    del(p,b){return this.request(p,{method:"DELETE",body:b})},
  };

  // ---------- State ----------
  const state = { viewer:null, viewerPromise:null, taxonomy:null, meSelection:null, adminSelection:null };
  const DISCLAIMER_ACK_KEY = "mofox_market_disclaimer_ack_v1";
  const DISCLAIMER_DELAY_SECONDS = 3;

  function hasAcceptedDisclaimer() {
    try { return localStorage.getItem(DISCLAIMER_ACK_KEY) === "1"; }
    catch (_) { return false; }
  }

  function markDisclaimerAccepted() {
    try { localStorage.setItem(DISCLAIMER_ACK_KEY, "1"); }
    catch (_) {}
  }

  function ensureDisclaimerModal() {
    let overlay = qs("[data-disclaimer-overlay]");
    if (overlay) return overlay;
    overlay = document.createElement("div");
    overlay.className = "disclaimer-overlay";
    overlay.dataset.disclaimerOverlay = "true";
    overlay.hidden = true;
    overlay.innerHTML = `
      <div class="disclaimer-modal" role="dialog" aria-modal="true" aria-labelledby="disclaimer-title">
        <div class="disclaimer-kicker">MoFox-Studio</div>
        <h2 id="disclaimer-title">\u9996\u6b21\u4f7f\u7528\u5b89\u5168\u63d0\u793a</h2>
        <div class="disclaimer-copy">
          <p>\u63d2\u4ef6\u5e02\u573a\u4e2d\u7684\u6240\u6709\u63d2\u4ef6\u5747\u7531\u7528\u6237\u81ea\u884c\u4e0a\u4f20\uff0c\u53ef\u80fd\u5305\u542b\u5b89\u5168\u98ce\u9669\u3001\u517c\u5bb9\u6027\u95ee\u9898\u6216\u6076\u610f\u4ee3\u7801\u3002</p>
          <p>\u5728\u5b89\u88c5\u6216\u4f7f\u7528\u4efb\u4f55\u63d2\u4ef6\u524d\uff0c\u8bf7\u52a1\u5fc5\u786e\u8ba4\u4f60\u4fe1\u4efb\u8be5\u63d2\u4ef6\u7684\u53d1\u5e03\u8005\uff0c\u5e76\u4e14\u5df2\u7ecf\u9605\u8bfb\u8fc7\u6e90\u7801\u3002</p>
          <p>\u56e0\u4f7f\u7528\u7b2c\u4e09\u65b9\u63d2\u4ef6\u9020\u6210\u7684\u4efb\u4f55\u6570\u636e\u4e22\u5931\u3001\u8d26\u53f7\u98ce\u9669\u3001\u8bbe\u5907\u635f\u574f\u6216\u5176\u4ed6\u635f\u5931\uff0cMoFox-Studio \u4e0d\u627f\u62c5\u8d23\u4efb\u3002</p>
        </div>
        <div class="disclaimer-actions">
          <button type="button" class="btn btn-primary" data-disclaimer-close disabled></button>
        </div>
      </div>`;
    document.body.appendChild(overlay);
    return overlay;
  }

  function setDisclaimerButtonLabel(button, remaining) {
    button.textContent = remaining > 0 ? `\u6211\u5df2\u77e5\u6089\uff08${remaining}s\uff09` : "\u6211\u5df2\u77e5\u6089";
  }

  function closeDisclaimerModal(overlay) {
    overlay.hidden = true;
    overlay.classList.remove("is-visible");
    document.body.classList.remove("modal-open");
    overlay.remove();
  }

  function showFirstVisitDisclaimer() {
    if (hasAcceptedDisclaimer()) return;
    const overlay = ensureDisclaimerModal();
    const closeBtn = qs("[data-disclaimer-close]", overlay);
    let remaining = DISCLAIMER_DELAY_SECONDS;
    overlay.hidden = false;
    overlay.classList.add("is-visible");
    document.body.classList.add("modal-open");
    closeBtn.disabled = true;
    setDisclaimerButtonLabel(closeBtn, remaining);
    const tick = window.setInterval(() => {
      remaining -= 1;
      if (remaining > 0) {
        setDisclaimerButtonLabel(closeBtn, remaining);
        return;
      }
      window.clearInterval(tick);
      closeBtn.disabled = false;
      setDisclaimerButtonLabel(closeBtn, 0);
    }, 1000);
    closeBtn.onclick = () => {
      if (closeBtn.disabled) return;
      window.clearInterval(tick);
      markDisclaimerAccepted();
      closeDisclaimerModal(overlay);
    };
  }

  function riskWarningMarkup(kind = "panel") {
    return `<div class="risk-warning risk-warning-${kind}" role="alert"><strong>\u98ce\u9669\u63d0\u793a</strong><p>\u6240\u6709\u63d2\u4ef6\u5747\u4e3a\u7528\u6237\u81ea\u884c\u4e0a\u4f20\uff0c\u53ef\u80fd\u5b58\u5728\u5b89\u5168\u98ce\u9669\u3002\u4e0b\u8f7d\u6216\u4f7f\u7528\u524d\uff0c\u8bf7\u52a1\u5fc5\u786e\u8ba4\u4f60\u4fe1\u4efb\u8be5\u63d2\u4ef6\uff0c\u5e76\u5df2\u9605\u8bfb\u5176\u6e90\u7801\u3002</p><p>\u56e0\u63d2\u4ef6\u4f7f\u7528\u9020\u6210\u7684\u4efb\u4f55\u635f\u5931\uff0cMoFox-Studio \u4e0d\u627f\u62c5\u8d23\u4efb\u3002</p></div>`;
  }

  async function loadViewer(force=false) {
    if (!force && state.viewerPromise) return state.viewerPromise;
    state.viewerPromise = API.get("/api/v1/me").catch(()=>({authenticated:false}));
    const auth = await state.viewerPromise;
    state.viewer = auth?.authenticated ? auth.user : null;
    renderAuthSlot();
    return auth;
  }

  async function loadTaxonomy(force=false) {
    if (!force && state.taxonomy) return state.taxonomy;
    const [c,t] = await Promise.all([API.get("/api/v1/categories").catch(()=>({items:[]})), API.get("/api/v1/tags").catch(()=>({items:[]}))]);
    state.taxonomy = {categories:c.items||[], tags:t.items||[]};
    return state.taxonomy;
  }

  // ---------- Toast ----------
  let toastTimer=null;
  function toast(msg,kind="") {
    const el=qs("[data-toast]"); if(!el) return;
    el.className="toast "+(kind||""); el.textContent=msg; el.hidden=false;
    clearTimeout(toastTimer); toastTimer=setTimeout(()=>{el.hidden=true},2600);
  }

  // ---------- Auth ----------
  function renderAuthSlot() {
    const slot=qs("[data-auth-slot]"); if(!slot) return;
    if (!state.viewer) {
      const rd=encodeURIComponent(location.pathname+location.search);
      slot.innerHTML=`<a class="btn btn-primary btn-sm" href="/api/v1/auth/github/login?redirect_to=${rd}">${iconSvg.github} GitHub \u767b\u5f55</a>`;
      return;
    }
    const me=state.viewer;
    const avatarMarkup = me.avatar_url
      ? `<img class="auth-avatar" src="${escape(me.avatar_url)}" alt="">`
      : `<span class="auth-avatar auth-avatar-fallback" aria-hidden="true">${escape((me.display_name || me.github_login || "M").trim()[0]?.toUpperCase() || "M")}</span>`;
    slot.innerHTML=`
      <a class="navlink navlink-profile" href="/author/${encodeURIComponent(me.author_id)}" data-route="/author">
        ${avatarMarkup}<span class="auth-name">${escape(me.display_name)}</span>
      </a>
      ${me.is_admin?'<a class="navlink" href="/admin" data-route="/admin">\u7ba1\u7406</a>':""}
      <button class="btn btn-ghost btn-sm" data-action="logout">\u9000\u51fa</button>`;
    qs("[data-action='logout']",slot)?.addEventListener("click",async()=>{
      await API.post("/api/v1/auth/logout").catch(()=>{});
      state.viewer=null; state.viewerPromise=null;
      toast("\u5df2\u9000\u51fa\u767b\u5f55","ok"); navigate("/"); renderAuthSlot();
    });
  }

  // ---------- Router ----------
  function navigate(path,{replace=false}={}) { if(replace) history.replaceState(null,"",path); else history.pushState(null,"",path); render(); }

  function parseRoute() {
    const p=location.pathname||"/", q=Object.fromEntries(new URLSearchParams(location.search));
    if(p==="/"||p==="") return {name:"market",query:q};
    if(p==="/me") return {name:"me",query:q};
    if(p==="/admin") return {name:"admin",query:q};
    const pm=p.match(/^\/plugin\/([^/]+)\/?$/); if(pm) return {name:"plugin",id:decodeURIComponent(pm[1]),query:q};
    const am=p.match(/^\/author\/([^/]+)\/?$/); if(am) return {name:"author",id:decodeURIComponent(am[1]),query:q};
    return {name:"notfound",query:q};
  }

  function riskWarningMarkup(kind = "panel") {
    return `<div class="risk-warning risk-warning-${kind}" role="alert"><strong>\u98ce\u9669\u63d0\u793a</strong><p>\u6240\u6709\u63d2\u4ef6\u5747\u4e3a\u7528\u6237\u81ea\u884c\u4e0a\u4f20\uff0c\u53ef\u80fd\u5b58\u5728\u5b89\u5168\u98ce\u9669\u3002\u4e0b\u8f7d\u6216\u4f7f\u7528\u524d\uff0c\u8bf7\u52a1\u5fc5\u786e\u8ba4\u4f60\u4fe1\u4efb\u8be5\u63d2\u4ef6\uff0c\u5e76\u5df2\u9605\u8bfb\u5176\u6e90\u7801\u3002</p><p>\u56e0\u63d2\u4ef6\u4f7f\u7528\u9020\u6210\u7684\u4efb\u4f55\u635f\u5931\uff0cMoFox-Studio \u4e0d\u627f\u62c5\u8d23\u4efb\u3002</p></div>`;
  }

  function navigate(path,{replace=false}={}) { if(replace) history.replaceState(null,"",path); else history.pushState(null,"",path); render(); }

  function parseRoute() {
    const p=location.pathname||"/", q=Object.fromEntries(new URLSearchParams(location.search));
    if(p==="/"||p==="") return {name:"market",query:q};
    if(p==="/me") return {name:"me",query:q};
    if(p==="/admin") return {name:"admin",query:q};
    const pm=p.match(/^\/plugin\/([^/]+)\/?$/); if(pm) return {name:"plugin",id:decodeURIComponent(pm[1]),query:q};
    const am=p.match(/^\/author\/([^/]+)\/?$/); if(am) return {name:"author",id:decodeURIComponent(am[1]),query:q};
    return {name:"notfound",query:q};
  }

  function highlightNav() {
    const r=parseRoute();
    qsa(".navlink").forEach(a=>a.classList.remove("active"));
    if(r.name==="market") qs('.navlink[data-route="/"]')?.classList.add("active");
    if(r.name==="me") qs('.navlink[data-route="/me"]')?.classList.add("active");
    if(r.name==="admin") qs('.navlink[data-route="/admin"]')?.classList.add("active");
  }

  document.addEventListener("click",(e)=>{
    const a=e.target.closest("a[data-route]"); if(!a) return;
    const href=a.getAttribute("href"); if(!href||href.startsWith("http")) return;
    e.preventDefault(); navigate(href);
  });
  window.addEventListener("popstate",()=>render());

  // ---------- Render ----------
  const appRoot=qs("[data-app]");

  async function render() {
    highlightNav();
    const route=parseRoute();
    await loadViewer();
    try {
      switch(route.name) {
        case "market": await renderMarket(route.query); break;
        case "plugin": await renderPluginDetail(route.id); break;
        case "me": await renderMe(); break;
        case "admin": await renderAdmin(); break;
        case "author": await renderAuthor(route.id); break;
        default: appRoot.innerHTML=emptyState("\u627e\u4e0d\u5230\u9875\u9762","\u4f60\u53ef\u80fd\u8bbf\u95ee\u4e86\u4e00\u4e2a\u4e0d\u5b58\u5728\u7684\u5730\u5740\u3002");
      }
    } catch(err) { console.error(err); appRoot.innerHTML=emptyState("\u52a0\u8f7d\u5931\u8d25",err?.message||"\u8bf7\u7a0d\u540e\u518d\u8bd5\u3002"); }
  }

  // ---------- Shared ----------
  function emptyState(title,msg) {
    return `<div class="empty"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg><strong style="display:block;color:var(--ink);margin-bottom:4px">${escape(title)}</strong><div>${escape(msg)}</div></div>`;
  }

  function trustBadge(level) {
    const map={official:"\u5b98\u65b9",verified:"\u8ba4\u8bc1",community:"\u793e\u533a"};
    return `<span class="badge trust-${escape(level)}">${escape(map[level]||level)}</span>`;
  }

  function pluginIcon(plugin) {
    if(plugin.icon_url) return `<img src="${escape(plugin.icon_url)}" alt="">`;
    return escape((plugin.display_name||plugin.plugin_id||"?").trim()[0]?.toUpperCase()||"?");
  }

  function pluginCard(plugin) {
    const tags=[...(plugin.categories||[]).slice(0,2).map(categoryTagMarkup),...(plugin.tags||[]).slice(0,3).map(t=>`<span class="tag">${escape(t)}</span>`)].join("");
    const author=plugin.owner_display_name||plugin.owner_login||plugin.owner_id;
    const av=plugin.owner_avatar_url?`<img src="${escape(plugin.owner_avatar_url)}" alt="">`:"";
    return `<a class="card" href="/plugin/${encodeURIComponent(plugin.plugin_id)}" data-route="/plugin">
      <div class="card-head">
        <div class="card-icon">${pluginIcon(plugin)}</div>
        <div class="card-title-row">
          <h3 class="card-title"><span class="card-title-text">${escape(plugin.display_name)}</span>${trustBadge(plugin.trust_level)}</h3>
          <div class="card-slug">${escape(plugin.plugin_id)}${plugin.latest_version?` \u00b7 <span class="card-version-chip">v${escape(plugin.latest_version)}</span>`:""}</div>
          <div class="card-author">${av}<span>${escape(author)}</span></div>
        </div>
      </div>
      <p class="card-summary">${escape(plugin.summary)}</p>
      <div class="card-tags">${tags}</div>
      <div class="card-meta">
        <div class="card-stats">
          <span class="rating">${starMarkup(plugin.rating_avg)} <span>${plugin.rating_avg.toFixed(1)}</span></span>
          <span class="stat-item${plugin.viewer_has_liked?" liked":""}">${iconSvg.heart}<span>${formatNumber(plugin.likes_count)}</span></span>
          <span class="stat-item">${iconSvg.download}<span>${formatNumber(plugin.downloads_count)}</span></span>
          <span class="stat-item">${iconSvg.message}<span>${formatNumber(plugin.comments_count)}</span></span>
        </div>
        <span>${formatRelative(plugin.updated_at)}</span>
      </div>
    </a>`;
  }

  // ---------- Market ----------
  const marketState={sort:"updated",category:"",tag:"",trust:"",view:"grid",query:"",offset:0,limit:24};

  async function renderMarket(query) {
    if(query.q) marketState.query=query.q;
    const si=qs("[data-search-input]"); if(si) si.value=marketState.query||"";
    appRoot.innerHTML=marketShellHtml();
    bindMarketToolbar();
    await Promise.all([renderMarketSidebar(),renderMarketFeatured(),renderMarketGrid(),renderMarketStats()]);
  }

  function marketShellHtml() {
    return `<section class="hero"><div><h1>Neo-MoFox \u63d2\u4ef6\u5e02\u573a</h1><p>\u5728\u8fd9\u91cc\u53d1\u73b0\u3001\u8bc4\u4ef7\u5e76\u53c2\u4e0e\u5171\u5efa Neo-MoFox \u63d2\u4ef6\u751f\u6001\u3002\u793e\u533a\u5ba1\u6838 \u00b7 \u771f\u5b9e\u53e3\u7891 \u00b7 \u5373\u88c5\u5373\u7528\u3002</p></div>
      <div class="hero-stats" data-hero-stats><div class="hero-stat"><b class="skeleton" style="height:1.4rem;width:48px">&nbsp;</b><span>\u5df2\u53d1\u5e03</span></div><div class="hero-stat"><b class="skeleton" style="height:1.4rem;width:48px">&nbsp;</b><span>\u7248\u672c</span></div><div class="hero-stat"><b class="skeleton" style="height:1.4rem;width:48px">&nbsp;</b><span>\u4f5c\u8005</span></div></div></section>
      <div class="market-layout"><aside class="sidebar" data-sidebar><div class="skeleton" style="height:200px"></div></aside>
      <div class="main-col"><div data-featured></div>
      <section class="section"><div class="toolbar"><div class="toolbar-left">
        <label for="sort-select">\u6392\u5e8f</label>
        <select id="sort-select" data-sort><option value="updated">\u6700\u8fd1\u66f4\u65b0</option><option value="popular">\u7efc\u5408\u70ed\u5ea6</option><option value="rating">\u8bc4\u5206\u4f18\u5148</option><option value="downloads">\u4e0b\u8f7d\u6700\u591a</option><option value="likes">\u70b9\u8d5e\u6700\u591a</option><option value="trending">\u8d8b\u52bf\u4e0a\u5347</option></select>
        <div class="chip-group" data-trust-chips><button type="button" class="chip active" data-trust="">\u5168\u90e8</button><button type="button" class="chip" data-trust="official">\u5b98\u65b9</button><button type="button" class="chip" data-trust="verified">\u8ba4\u8bc1</button><button type="button" class="chip" data-trust="community">\u793e\u533a</button></div>
      </div><div class="toolbar-right"><span data-result-summary style="font-size:0.82rem;color:var(--muted)"></span>
        <div class="chip-group" data-view-chips><button type="button" class="chip active" data-view="grid">\u7f51\u683c</button><button type="button" class="chip" data-view="list">\u5217\u8868</button></div>
      </div></div>
      <div class="section-head"><div><h2>\u5168\u90e8\u63d2\u4ef6 <span class="badge trust-community" data-total>0</span></h2><p data-filter-summary>\u6d4f\u89c8\u6240\u6709\u5df2\u53d1\u5e03\u7684\u63d2\u4ef6\uff0c\u652f\u6301\u6807\u7b7e\u3001\u5206\u7c7b\u548c\u4fe1\u4efb\u7b49\u7ea7\u7b5b\u9009\u3002</p></div>
        <button type="button" class="btn btn-ghost btn-sm" data-action="reset-filter" hidden>\u6e05\u9664\u7b5b\u9009</button></div>
      <div class="grid" data-plugin-grid></div></section></div></div>`;
  }

  async function renderMarketStats() {
    const s=await API.get("/api/v1/market/stats").catch(()=>null); if(!s) return;
    const c=qs("[data-hero-stats]"); if(c) c.innerHTML=`<div class="hero-stat"><b>${formatNumber(s.published_plugins||s.plugins_total||0)}</b><span>\u5df2\u53d1\u5e03</span></div><div class="hero-stat"><b>${formatNumber(s.versions_total||0)}</b><span>\u7248\u672c</span></div><div class="hero-stat"><b>${formatNumber(s.authors_total||0)}</b><span>\u4f5c\u8005</span></div>`;
  }

  function updateFeaturedVisibility() {
    const f=qs("[data-featured]"); if(!f) return;
    f.style.display=(marketState.query||marketState.category||marketState.tag||marketState.trust||marketState.sort!=="updated")?"none":"";
  }

  function scrollToGrid() {
    const g=qs("[data-plugin-grid]"); if(g) window.scrollTo({top:Math.max(0,g.getBoundingClientRect().top+window.scrollY-80),behavior:"smooth"});
  }

  function scrollToFeaturedSection(sectionKey) {
    const section = qs(`[data-featured-section="${sectionKey}"]`);
    if (!section) return;
    window.scrollTo({top: Math.max(0, section.getBoundingClientRect().top + window.scrollY - 88), behavior: "smooth"});
  }

  function resetMarketFilters({keepNav = false} = {}) {
    marketState.category = "";
    marketState.tag = "";
    marketState.trust = "";
    marketState.query = "";
    marketState.sort = "updated";
    const sel = qs("[data-sort]");
    if (sel) sel.value = "updated";
    qsa("[data-cat-list] button").forEach((button, index) => button.classList.toggle("active", index === 0));
    qsa("[data-tag-list] button").forEach((button, index) => button.classList.toggle("active", index === 0));
    qsa("[data-trust-chips] .chip").forEach((button, index) => button.classList.toggle("active", index === 0));
    if (!keepNav) qsa("[data-nav-list] button").forEach((button, index) => button.classList.toggle("active", index === 0));
    const searchInput = qs("[data-search-input]");
    if (searchInput) searchInput.value = "";
  }

  async function renderMarketSidebar() {
    await loadTaxonomy();
    const sb=qs("[data-sidebar]"); if(!sb) return;
    const cats=state.taxonomy.categories, tags=state.taxonomy.tags;
    sb.innerHTML=`<div class="sidebar-section"><h4>\u5feb\u901f\u5bfc\u822a</h4><ul class="sidebar-list" data-nav-list>
      <li><button type="button" data-nav="all" class="active">\u5168\u90e8\u63d2\u4ef6</button></li>
      <li><button type="button" data-nav="trending">\u70ed\u95e8\u63a8\u8350</button></li>
      <li><button type="button" data-nav="top_rated">\u9ad8\u5206\u597d\u8bc4</button></li>
      <li><button type="button" data-nav="latest">\u6700\u8fd1\u66f4\u65b0</button></li></ul></div>
      <div class="sidebar-section"><h4>\u5206\u7c7b</h4><ul class="sidebar-list" data-cat-list>
      <li><button type="button" data-cat="" class="active">\u5168\u90e8\u5206\u7c7b</button></li>
      ${cats.map(c=>`<li><button type="button" data-cat="${escape(c)}" title="${escape(c)}">${escape(categoryLabel(c))}</button></li>`).join("")}</ul></div>
      <div class="sidebar-section"><h4>\u70ed\u95e8\u6807\u7b7e</h4><ul class="sidebar-list" data-tag-list>
      <li><button type="button" data-tag="" class="active">\u5168\u90e8\u6807\u7b7e</button></li>
      ${tags.slice(0,30).map(t=>`<li><button type="button" data-tag="${escape(t)}">#${escape(t)}</button></li>`).join("")}</ul></div>`;

    sb.addEventListener("click",(e)=>{
      const catBtn=e.target.closest("button[data-cat]");
      const tagBtn=e.target.closest("button[data-tag]");
      const navBtn=e.target.closest("button[data-nav]");
      if(catBtn){ marketState.category=catBtn.dataset.cat; qsa("[data-cat-list] button").forEach(b=>b.classList.toggle("active",b===catBtn)); updateFeaturedVisibility(); renderMarketGrid(); scrollToGrid(); return; }
      if(tagBtn){ marketState.tag=tagBtn.dataset.tag; qsa("[data-tag-list] button").forEach(b=>b.classList.toggle("active",b===tagBtn)); updateFeaturedVisibility(); renderMarketGrid(); scrollToGrid(); return; }
      if(navBtn){
        const navKey = navBtn.dataset.nav;
        qsa("[data-nav-list] button").forEach(b=>b.classList.toggle("active",b===navBtn));
        if(navKey === "all") {
          resetMarketFilters({keepNav:true});
          updateFeaturedVisibility();
          renderMarketGrid();
          scrollToGrid();
          return;
        }
        resetMarketFilters({keepNav:true});
        updateFeaturedVisibility();
        renderMarketGrid();
        requestAnimationFrame(() => scrollToFeaturedSection(navKey === "trending" ? "ranking" : navKey));
        return;
      }
    });
  }

  async function renderMarketFeatured() {
    const c=qs("[data-featured]"); if(!c) return;
    const f=await API.get("/api/v1/market/featured?limit=6").catch(()=>null);
    if(!f){c.innerHTML="";return;}
    const sections=[{key:"ranking",title:"\ud83d\udd25 \u793e\u533a\u70ed\u95e8",desc:"\u7efc\u5408\u70b9\u8d5e\u3001\u4e0b\u8f7d\u4e0e\u8bc4\u4ef7\u7684\u793e\u533a\u70ed\u5ea6\u699c\u5355\u3002"},{key:"top_rated",title:"\u2b50 \u9ad8\u5206\u597d\u8bc4",desc:"\u7528\u6237\u8bc4\u5206\u6700\u9ad8\u7684\u63d2\u4ef6\uff0c\u53e3\u7891\u63a8\u8350\u3002"},{key:"latest",title:"\u4e0a\u65b0\u901f\u9012",desc:"\u8fd1\u671f\u6709\u65b0\u7248\u672c\u53d1\u5e03\u7684\u63d2\u4ef6\u3002"}];
    c.innerHTML=sections.filter(s=>(f[s.key]||[]).length).map(s=>{
      const items=f[s.key]||[];
      return `<section class="section" data-featured-section="${escape(s.key)}"><div class="section-head"><div><h2>${escape(s.title)}</h2><p>${escape(s.desc)}</p></div></div><div class="grid">${items.slice(0,6).map(pluginCard).join("")}</div></section>`;
    }).join("");
  }

  function bindMarketToolbar() {
    const sel=qs("[data-sort]"); if(sel){sel.value=marketState.sort; sel.addEventListener("change",()=>{marketState.sort=sel.value; updateFeaturedVisibility(); renderMarketGrid();});}
    qs("[data-trust-chips]")?.addEventListener("click",e=>{const b=e.target.closest("[data-trust]");if(!b)return;qsa("[data-trust-chips] .chip").forEach(el=>el.classList.toggle("active",el===b));marketState.trust=b.dataset.trust;updateFeaturedVisibility();renderMarketGrid();});
    qs("[data-view-chips]")?.addEventListener("click",e=>{const b=e.target.closest("[data-view]");if(!b)return;qsa("[data-view-chips] .chip").forEach(el=>el.classList.toggle("active",el===b));marketState.view=b.dataset.view;const g=qs("[data-plugin-grid]");if(g)g.classList.toggle("list-view",marketState.view==="list");});
    qs("[data-action='reset-filter']")?.addEventListener("click",()=>{
      resetMarketFilters();
      updateFeaturedVisibility(); renderMarketGrid();
    });
  }

  async function renderMarketGrid() {
    const grid=qs("[data-plugin-grid]"),summary=qs("[data-filter-summary]"),totalEl=qs("[data-total]"),resultEl=qs("[data-result-summary]"),resetBtn=qs("[data-action='reset-filter']");
    if(!grid) return;
    grid.innerHTML=Array.from({length:6},()=>'<div class="card skeleton" style="height:180px"></div>').join("");
    const p=new URLSearchParams(); p.set("limit",marketState.limit); p.set("sort",marketState.sort);
    if(marketState.query) p.set("q",marketState.query);
    if(marketState.category) p.set("category",marketState.category);
    if(marketState.tag) p.set("tag",marketState.tag);
    if(marketState.trust) p.set("trust_level",marketState.trust);
    const result=await API.get(`/api/v1/plugins?${p.toString()}`).catch(err=>{toast(err.message||"\u52a0\u8f7d\u5931\u8d25","error");return{items:[],total:0};});
    const items=result.items||[];
    grid.classList.toggle("list-view",marketState.view==="list");
    grid.innerHTML=items.length?items.map(pluginCard).join(""):emptyState("\u6682\u65e0\u5339\u914d\u63d2\u4ef6","\u8bd5\u8bd5\u66f4\u6362\u7b5b\u9009\u6761\u4ef6\u6216\u5173\u952e\u5b57\u3002");
    if(totalEl) totalEl.textContent=result.total||0;
    if(resultEl) resultEl.textContent=`\u5171 ${result.total||0} \u4e2a\u7ed3\u679c`;
    const hasF=marketState.query||marketState.category||marketState.tag||marketState.trust;
    if(resetBtn) resetBtn.hidden=!hasF;
    if(summary){
      const parts=[];
      if(marketState.query) parts.push(`\u5173\u952e\u5b57 "${marketState.query}"`);
      if(marketState.category) parts.push(`\u5206\u7c7b ${categoryLabel(marketState.category)}`);
      if(marketState.tag) parts.push(`\u6807\u7b7e #${marketState.tag}`);
      if(marketState.trust) parts.push(`${marketState.trust} \u63d2\u4ef6`);
      summary.textContent=parts.length?`\u5f53\u524d\u7b5b\u9009\uff1a${parts.join(" \u00b7 ")}`:"\u6d4f\u89c8\u6240\u6709\u5df2\u53d1\u5e03\u7684\u63d2\u4ef6\uff0c\u652f\u6301\u6807\u7b7e\u3001\u5206\u7c7b\u548c\u4fe1\u4efb\u7b49\u7ea7\u7b5b\u9009\u3002";
    }
  }

  // ---------- Plugin Detail ----------
  async function renderPluginDetail(pluginId) {
    appRoot.innerHTML='<div class="loading-screen">\u52a0\u8f7d\u63d2\u4ef6\u8be6\u60c5\u2026</div>';
    const [snapshot,versions]=await Promise.all([API.get(`/api/v1/plugins/${encodeURIComponent(pluginId)}/community`),API.get(`/api/v1/plugins/${encodeURIComponent(pluginId)}/versions`).catch(()=>({items:[]}))]);
    const plugin=snapshot.plugin, rating=snapshot.rating;
    appRoot.innerHTML=`
      <div class="shell" style="padding-top:16px;color:var(--muted);font-size:0.82rem"><a href="/" data-route="/">\u5e02\u573a</a><span style="margin:0 6px">/</span>${escape(plugin.display_name)}</div>
      <div class="detail"><div class="main-col">
        <section class="detail-hero">
          <div class="detail-icon">${pluginIcon(plugin)}</div>
          <div><div class="detail-title"><h1>${escape(plugin.display_name)}</h1>${trustBadge(plugin.trust_level)}<span class="badge status-${escape(plugin.status)}">${escape(plugin.status)}</span>${plugin.latest_version?`<span class="card-version-chip">v${escape(plugin.latest_version)}</span>`:""}</div>
          <div class="detail-sub"><span>${escape(plugin.plugin_id)}</span><span>\u00b7</span><span>\u4f5c\u8005 <a href="/author/${encodeURIComponent(plugin.owner_id)}" data-route="/author">${escape(plugin.owner_display_name||plugin.owner_login||plugin.owner_id)}</a></span><span>\u00b7</span><span>${escape(plugin.license)}</span><span>\u00b7</span><span>\u66f4\u65b0\u4e8e ${formatRelative(plugin.updated_at)}</span></div></div>
          <p class="detail-summary">${escape(plugin.summary)}</p>
        </section>
        <div class="tabs" data-tabs><button type="button" class="active" data-tab="overview">\u7b80\u4ecb</button><button type="button" data-tab="versions">\u7248\u672c<span class="count">${versions.items.length}</span></button><button type="button" data-tab="comments">\u8bc4\u8bba<span class="count">${plugin.comments_count}</span></button></div>
        <div data-tab-panels>
          <section data-panel="overview"><div class="panel"><h3>\u63d2\u4ef6\u7b80\u4ecb</h3><div class="description">${escape(plugin.description||plugin.summary)}</div></div>
            <div class="panel"><h3>\u5206\u7c7b\u4e0e\u6807\u7b7e</h3><div class="card-tags">${(plugin.categories||[]).map(categoryTagMarkup).join("")}${(plugin.tags||[]).map(t=>`<span class="tag">#${escape(t)}</span>`).join("")}</div></div>
            <div class="panel"><h3>\u7ef4\u62a4\u8005</h3><div style="color:var(--muted);font-size:0.86rem">${plugin.maintainers.map(m=>`<a href="/author/${encodeURIComponent(m)}" data-route="/author">${escape(m)}</a>`).join(" \u00b7 ")}</div></div></section>
          <section data-panel="versions" hidden><div class="panel"><h3>\u53d1\u5e03\u5386\u53f2</h3>${riskWarningMarkup("inline")}<div>${versions.items.length?versions.items.map(versionRow).join(""):emptyState("\u6682\u65e0\u7248\u672c","\u4f5c\u8005\u5c1a\u672a\u53d1\u5e03\u4efb\u4f55\u5df2\u5ba1\u6838\u901a\u8fc7\u7684\u7248\u672c\u3002")}</div></div></section>
          <section data-panel="comments" hidden><div class="panel" data-comment-panel><h3>\u8bc4\u8bba <span class="count" style="font-size:0.8rem;color:var(--muted);font-weight:400">${plugin.comments_count} \u6761</span></h3><div data-comment-form></div><div data-comment-list style="margin-top:14px"></div></div></section>
        </div>
      </div>
      <aside class="install-panel"><div class="panel"><h3>\u5b89\u88c5</h3>
        ${riskWarningMarkup("panel")}
        ${plugin.latest_version?`<div style="color:var(--muted);font-size:0.8rem;margin-bottom:4px">\u6700\u65b0\u7a33\u5b9a\u7248</div><div style="font-family:'JetBrains Mono','SFMono-Regular',Consolas,monospace;font-size:1rem;color:var(--ink);font-weight:600">v${escape(plugin.latest_version)}</div><div style="font-size:0.78rem;color:var(--muted)">\u53d1\u5e03\u4e8e ${formatRelative(plugin.latest_version_published_at)}</div>`:'<div style="color:var(--muted)">\u6682\u65e0\u53ef\u5b89\u88c5\u7248\u672c</div>'}
        <div class="install-stats"><div><b>${formatNumber(plugin.downloads_count)}</b><span>\u4e0b\u8f7d</span></div><div><b>${formatNumber(plugin.likes_count)}</b><span>\u70b9\u8d5e</span></div><div><b>${plugin.rating_avg.toFixed(1)}</b><span>${plugin.rating_count} \u8bc4\u4ef7</span></div></div>
        <div class="install-actions"><button type="button" class="btn btn-primary" data-install ${plugin.latest_version?"":"disabled"}>\u4e0b\u8f7d\u63d2\u4ef6</button><button type="button" class="btn" data-like>${plugin.viewer_has_liked?"\u2764 \u5df2\u8d5e":"\u2661 \u70b9\u8d5e"}</button></div>
        ${plugin.latest_version?`<code class="install-code">mofox plugin install ${escape(plugin.plugin_id)}@${escape(plugin.latest_version)}</code>`:""}
        <div style="margin-top:14px;display:flex;gap:10px;flex-wrap:wrap;font-size:0.82rem;color:var(--muted)">${plugin.homepage?`<a href="${escape(plugin.homepage)}" target="_blank" rel="noreferrer noopener">\u4e3b\u9875 \u2197</a>`:""}<a href="${escape(plugin.repository_url)}" target="_blank" rel="noreferrer noopener">GitHub \u2197</a></div>
      </div>
      <div class="panel"><h3>\u8bc4\u5206<span style="font-size:0.8rem;color:var(--muted);font-weight:400">${plugin.rating_count} \u7968</span></h3>
        <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:6px"><div style="font-size:2rem;font-weight:700;color:var(--ink)">${plugin.rating_avg.toFixed(1)}</div><div class="rating">${starMarkup(plugin.rating_avg)}</div></div>
        <div class="rating-dist">${[5,4,3,2,1].map(s=>{const cnt=rating.distribution?.[String(s)]||0;const pct=plugin.rating_count?Math.round(cnt/plugin.rating_count*100):0;return `<div class="rating-dist-row"><span>${s}\u2605</span><span class="rating-dist-bar"><span style="width:${pct}%"></span></span><span>${cnt}</span></div>`;}).join("")}</div>
        <div style="margin-top:12px"><div style="font-size:0.8rem;color:var(--muted);margin-bottom:4px">\u6211\u7684\u8bc4\u5206</div>
          <div class="rating-picker" data-rating-picker>${[1,2,3,4,5].map(n=>`<button type="button" data-score="${n}"${(rating.viewer_rating||0)>=n?' class="active"':""}>&#9733;</button>`).join("")}${rating.viewer_rating?'<button type="button" class="btn btn-xs btn-ghost" style="margin-left:6px" data-clear-rating>\u6e05\u9664</button>':""}</div>
          ${state.viewer?"":'<div style="font-size:0.78rem;color:var(--muted);margin-top:4px">\u767b\u5f55\u540e\u53ef\u4ee5\u8bc4\u5206\u548c\u8bc4\u8bba\u3002</div>'}
        </div>
      </div></aside></div>`;
    bindDetailEvents(plugin,rating);
    renderComments(plugin.plugin_id);
  }

  function versionRow(v) {
    return `<div class="version-item"><span class="ver">v${escape(v.version)}${v.is_prerelease?' <small style="color:var(--warn)">pre</small>':""}${v.is_yanked?' <small style="color:var(--bad)">yanked</small>':""}</span>
      <div class="meta"><div><strong>${escape(v.release_title||v.version)}</strong></div><div>${formatDate(v.published_at)} \u00b7 ${formatBytes(v.file_size)} \u00b7 API ${escape(v.plugin_api_version)} \u00b7 \u5bbf\u4e3b \u2265 ${escape(v.min_host_version)}${v.max_host_version?` \u2264 ${escape(v.max_host_version)}`:""}</div><div>${formatNumber(v.download_count)} \u6b21\u4e0b\u8f7d \u00b7 \u5e73\u53f0 ${(v.supported_platforms||[]).join(", ")||"all"}</div></div>
      <div class="table-actions"><a class="btn btn-sm" href="${escape(v.release_url)}" target="_blank" rel="noreferrer noopener">Release</a><a class="btn btn-sm btn-primary" href="${escape(v.asset_download_url)}" target="_blank" rel="noreferrer noopener" data-download="${escape(v.version)}">\u4e0b\u8f7d</a></div></div>`;
  }

  function bindDetailEvents(plugin,rating) {
    qsa("[data-tab]").forEach(btn=>btn.addEventListener("click",()=>{const tab=btn.dataset.tab;qsa("[data-tab]").forEach(t=>t.classList.toggle("active",t===btn));qsa("[data-panel]").forEach(p=>(p.hidden=p.dataset.panel!==tab));}));
    qs("[data-install]")?.addEventListener("click",async()=>{try{const v=await API.post(`/api/v1/plugins/${encodeURIComponent(plugin.plugin_id)}/install-record`);if(v?.asset_download_url)window.open(v.asset_download_url,"_blank","noopener");toast("\u5df2\u8bb0\u5f55\u4e0b\u8f7d","ok");}catch(e){toast(e.message||"\u4e0b\u8f7d\u5931\u8d25","error");}});
    qsa("[data-download]").forEach(btn=>btn.addEventListener("click",()=>{API.post(`/api/v1/plugins/${encodeURIComponent(plugin.plugin_id)}/install-record?version=${encodeURIComponent(btn.dataset.download)}`).catch(()=>{});}));
    qs("[data-like]")?.addEventListener("click",async()=>{if(!state.viewer){triggerLogin();return;}try{const r=await API.post(`/api/v1/plugins/${encodeURIComponent(plugin.plugin_id)}/like`);toast(r.liked?"\u5df2\u70b9\u8d5e":"\u5df2\u53d6\u6d88\u70b9\u8d5e","ok");renderPluginDetail(plugin.plugin_id);}catch(e){toast(e.message||"\u64cd\u4f5c\u5931\u8d25","error");}});
    const picker=qs("[data-rating-picker]");
    if(picker){const btns=qsa("[data-score]",picker);btns.forEach(btn=>{btn.addEventListener("mouseenter",()=>{const n=Number(btn.dataset.score);btns.forEach(b=>b.classList.toggle("hover",Number(b.dataset.score)<=n));});btn.addEventListener("mouseleave",()=>btns.forEach(b=>b.classList.remove("hover")));btn.addEventListener("click",async()=>{if(!state.viewer){triggerLogin();return;}try{await API.post(`/api/v1/plugins/${encodeURIComponent(plugin.plugin_id)}/rating`,{score:Number(btn.dataset.score)});toast("\u611f\u8c22\u4f60\u7684\u8bc4\u5206","ok");renderPluginDetail(plugin.plugin_id);}catch(e){toast(e.message||"\u8bc4\u5206\u5931\u8d25","error");}});});
    qs("[data-clear-rating]")?.addEventListener("click",async()=>{try{await API.del(`/api/v1/plugins/${encodeURIComponent(plugin.plugin_id)}/rating`);toast("\u5df2\u6e05\u9664\u8bc4\u5206","ok");renderPluginDetail(plugin.plugin_id);}catch(e){toast(e.message||"\u64cd\u4f5c\u5931\u8d25","error");}});}
  }

  async function renderComments(pluginId) {
    const list=qs("[data-comment-list]"),formBox=qs("[data-comment-form]"); if(!list||!formBox) return;
    formBox.innerHTML=state.viewer?`<form class="comment-form" data-comment-submit><textarea maxlength="4000" name="content" placeholder="\u5206\u4eab\u4f60\u7684\u5b89\u88c5\u4f53\u9a8c\u6216\u63d0\u51fa\u95ee\u9898..." required></textarea><div class="comment-form-actions"><small>\u652f\u6301\u591a\u884c\u6587\u5b57\u3002\u4e0d\u8981\u53d1\u9001\u5e7f\u544a\u6216\u4e2a\u4eba\u9690\u79c1\u4fe1\u606f\u3002</small><button class="btn btn-primary btn-sm" type="submit">\u53d1\u5e03\u8bc4\u8bba</button></div></form>`:`<div class="empty" style="padding:16px">\u767b\u5f55\u540e\u53ef\u4ee5\u53d1\u8868\u8bc4\u8bba\u4e0e\u4f5c\u8005\u4e92\u52a8\u3002<div style="margin-top:8px"><a class="btn btn-primary btn-sm" href="/api/v1/auth/github/login?redirect_to=${encodeURIComponent(location.pathname)}">${iconSvg.github} GitHub \u767b\u5f55</a></div></div>`;
    qs("[data-comment-submit]",formBox)?.addEventListener("submit",async(ev)=>{ev.preventDefault();const form=ev.target,content=form.elements.content.value.trim();if(!content)return;form.elements.content.disabled=true;try{await API.post(`/api/v1/plugins/${encodeURIComponent(pluginId)}/comments`,{content});form.reset();toast("\u5df2\u53d1\u5e03","ok");await renderComments(pluginId);}catch(e){toast(e.message||"\u53d1\u5e03\u5931\u8d25","error");}finally{form.elements.content.disabled=false;}});
    list.innerHTML='<div class="skeleton" style="height:60px"></div>';
    const result=await API.get(`/api/v1/plugins/${encodeURIComponent(pluginId)}/comments?limit=50`).catch(()=>({items:[]}));
    const comments=result.items||[];
    if(!comments.length){list.innerHTML=emptyState("\u8fd8\u6ca1\u6709\u8bc4\u8bba","\u6765\u62a2\u5360\u7b2c\u4e00\u4e2a\u8bc4\u8bba\u5427\uff01");return;}
    list.innerHTML=comments.map(renderCommentHtml).join("");
    qsa("[data-delete-comment]",list).forEach(btn=>btn.addEventListener("click",async()=>{if(!confirm("\u786e\u5b9a\u5220\u9664\u8fd9\u6761\u8bc4\u8bba\u5417\uff1f"))return;try{await API.del(`/api/v1/plugins/${encodeURIComponent(pluginId)}/comments/${btn.dataset.deleteComment}`);toast("\u5df2\u5220\u9664","ok");renderComments(pluginId);}catch(e){toast(e.message||"\u5220\u9664\u5931\u8d25","error");}}));
  }

  function renderCommentHtml(c) {
    const a=c.author, av=a.avatar_url?`<img src="${escape(a.avatar_url)}" alt="">`:escape(a.display_name?.[0]?.toUpperCase()||"?");
    const canDel=state.viewer&&(state.viewer.author_id===a.author_id||state.viewer.is_admin);
    return `<div class="comment"><div class="comment-avatar">${av}</div><div><div class="comment-meta"><strong>${escape(a.display_name)}</strong><span>@${escape(a.github_login)}</span>${a.is_admin?'<span class="badge trust-official">\u7ba1\u7406\u5458</span>':""}<span>\u00b7</span><span>${formatRelative(c.created_at)}</span></div><p class="comment-content">${escape(c.content)}</p><div class="comment-actions">${canDel?`<button type="button" data-delete-comment="${c.id}">\u5220\u9664</button>`:""}</div></div></div>`;
  }

  function triggerLogin() { toast("\u8bf7\u5148\u767b\u5f55",""); setTimeout(()=>{location.href=`/api/v1/auth/github/login?redirect_to=${encodeURIComponent(location.pathname)}`;},600); }

  function statusText(status) {
    const labels = {
      published: "已上架",
      pending_review: "待审核",
      draft: "已退回",
      deprecated: "已下架",
      blocked: "已封禁",
      archived: "已归档",
      submitted: "已提交",
      yanked: "已撤回",
    };
    return labels[status] || status || "-";
  }

  function reviewActionText(action) {
    const labels = {
      register_plugin: "注册插件",
      update_plugin: "更新插件",
      submit_version: "提交版本",
      approve_plugin: "重新上架",
      reject_plugin: "退回插件",
      block_plugin: "封禁插件",
      deprecate_plugin: "下架插件",
      archive_plugin: "归档插件",
      approve_version: "恢复版本",
      reject_version: "退回版本",
      yank_version: "下架版本",
      block_version: "封禁版本",
      sync_version: "同步版本",
      webhook_received: "Webhook 事件",
    };
    return labels[action] || action || "-";
  }

  function formatUptime(seconds) {
    const total = Number(seconds || 0);
    const days = Math.floor(total / 86400);
    const hours = Math.floor((total % 86400) / 3600);
    const minutes = Math.floor((total % 3600) / 60);
    if (days > 0) return `${days}d ${hours}h`;
    if (hours > 0) return `${hours}h ${minutes}m`;
    return `${minutes}m`;
  }

  function metricCard(label, value, hint = "") {
    return `<div class="control-metric"><span>${escape(label)}</span><b>${escape(String(value))}</b>${hint ? `<small>${escape(hint)}</small>` : ""}</div>`;
  }

  function selectPluginId(items, current, fallbackStatus) {
    const list = items || [];
    if (!list.length) return null;
    if (current && list.some((item) => item.plugin_id === current)) return current;
    if (fallbackStatus) {
      const matched = list.find((item) => item.status === fallbackStatus);
      if (matched) return matched.plugin_id;
    }
    return list[0].plugin_id;
  }

  function activityChartMarkup(activity) {
    const days = activity || [];
    const peaks = days.flatMap((item) => [item.plugins_created, item.comments_created, item.ratings_created]);
    const maxValue = Math.max(1, ...peaks);
    return `
      <div class="activity-legend">
        <span><i class="dot dot-plugin"></i>新增插件</span>
        <span><i class="dot dot-comment"></i>评论</span>
        <span><i class="dot dot-rating"></i>评分</span>
      </div>
      <div class="activity-chart">
        ${days.map((item) => {
          const dateLabel = item.date ? item.date.slice(5) : "--";
          const pluginHeight = Math.max(8, Math.round((item.plugins_created || 0) / maxValue * 88));
          const commentHeight = Math.max(8, Math.round((item.comments_created || 0) / maxValue * 88));
          const ratingHeight = Math.max(8, Math.round((item.ratings_created || 0) / maxValue * 88));
          return `
            <div class="activity-day">
              <div class="activity-bars">
                <span class="activity-bar plugin" style="height:${pluginHeight}px" title="新增插件 ${item.plugins_created || 0}"></span>
                <span class="activity-bar comment" style="height:${commentHeight}px" title="评论 ${item.comments_created || 0}"></span>
                <span class="activity-bar rating" style="height:${ratingHeight}px" title="评分 ${item.ratings_created || 0}"></span>
              </div>
              <strong>${dateLabel}</strong>
              <small>${(item.plugins_created || 0) + (item.comments_created || 0) + (item.ratings_created || 0)} 动态</small>
            </div>`;
        }).join("")}
      </div>`;
  }

  function breakdownMarkup(title, data) {
    const entries = Object.entries(data || {}).filter(([, value]) => Number(value || 0) > 0);
    return `
      <div class="mini-breakdown">
        <h4>${escape(title)}</h4>
        <div class="mini-breakdown-grid">
          ${(entries.length ? entries : [["empty", 0]]).map(([key, value]) => `
            <div class="mini-breakdown-item">
              <span>${escape(key === "empty" ? "暂无" : statusText(key))}</span>
              <b>${escape(String(value))}</b>
            </div>`).join("")}
        </div>
      </div>`;
  }

  function reviewFeedMarkup(items, emptyMessage) {
    const rows = items || [];
    if (!rows.length) return `<div class="empty compact-empty">${escape(emptyMessage)}</div>`;
    return `<div class="review-feed">${rows.map((item) => `
      <article class="review-feed-item">
        <div>
          <strong>${escape(reviewActionText(item.action))}</strong>
          <p>${escape(item.target_id)} · ${escape(item.status_before || "-")} → ${escape(item.status_after || "-")}</p>
        </div>
        <div class="review-feed-meta">
          <span>${escape(item.operator_id)}</span>
          <span>${formatRelative(item.created_at)}</span>
        </div>
      </article>`).join("")}</div>`;
  }

  function governanceVersionMarkup(scope, pluginId, version) {
    const actions = [];
    if (scope === "admin") {
      if (version.status !== "published" || version.is_yanked) actions.push(`<button class="btn btn-xs" data-admin-version-action="publish" data-plugin-id="${escape(pluginId)}" data-version="${escape(version.version)}">恢复</button>`);
      if (version.status !== "submitted") actions.push(`<button class="btn btn-xs" data-admin-version-action="reject" data-plugin-id="${escape(pluginId)}" data-version="${escape(version.version)}">退回</button>`);
      if (!version.is_yanked) actions.push(`<button class="btn btn-xs" data-admin-version-action="yank" data-plugin-id="${escape(pluginId)}" data-version="${escape(version.version)}">下架</button>`);
      if (version.status !== "blocked") actions.push(`<button class="btn btn-xs btn-danger" data-admin-version-action="block" data-plugin-id="${escape(pluginId)}" data-version="${escape(version.version)}">封禁</button>`);
    } else {
      if (!version.is_yanked) actions.push(`<button class="btn btn-xs" data-me-version-action="yank" data-plugin-id="${escape(pluginId)}" data-version="${escape(version.version)}">下架此版本</button>`);
    }
    return `
      <div class="governance-version-row">
        <div class="governance-version-main">
          <div class="governance-version-head">
            <strong>v${escape(version.version)}</strong>
            <span class="badge status-${escape(version.status)}">${escape(statusText(version.status))}</span>
            ${version.is_yanked ? '<span class="badge status-blocked">已 yank</span>' : ""}
          </div>
          <p>${escape(version.release_title || version.version)} · ${formatDate(version.published_at)} · ${formatBytes(version.file_size)} · ${formatNumber(version.download_count)} 下载</p>
          <small>API ${escape(version.plugin_api_version)} · Host >= ${escape(version.min_host_version)}${version.max_host_version ? ` <= ${escape(version.max_host_version)}` : ""} · ${escape((version.supported_platforms || []).join(", ") || "all")}</small>
        </div>
        <div class="table-actions">
          <a class="btn btn-xs btn-ghost" href="${escape(version.release_url)}" target="_blank" rel="noreferrer noopener">Release</a>
          ${actions.join("")}
        </div>
      </div>`;
  }

  function managementPluginList(items, selectedId, dataAttr) {
    return `<div class="control-list">${(items || []).map((plugin) => `
      <button type="button" class="control-list-item${plugin.plugin_id === selectedId ? " is-active" : ""}" ${dataAttr}="${escape(plugin.plugin_id)}">
        <div>
          <strong>${escape(plugin.display_name)}</strong>
          <span>${escape(plugin.plugin_id)}</span>
        </div>
        <div>
          <span class="badge status-${escape(plugin.status)}">${escape(statusText(plugin.status))}</span>
          <small>${formatRelative(plugin.updated_at)}</small>
        </div>
      </button>`).join("")}</div>`;
  }

  function trustLevelLabel(level) {
    const labels = { official: "官方", verified: "认证", community: "社区" };
    return labels[level] || level || "-";
  }

  function adminSidebarMarkup(activeSection) {
    const items = [
      { id: "admin-overview", label: "总览" },
      { id: "admin-queue", label: "治理队列" },
      { id: "admin-plugin-governance", label: "插件治理" },
      { id: "admin-version-governance", label: "版本治理" },
      { id: "admin-trends", label: "趋势观察" },
      { id: "admin-review-feed", label: "审核流" },
      { id: "admin-plugin-history", label: "治理历史" },
    ];
    return `
      <aside class="panel admin-page-sidebar">
        <div class="admin-page-sidebar-head">
          <span class="control-kicker">Admin Nav</span>
          <h2>快速切换</h2>
          <p>直接跳到你现在要处理的那一块，不用整页下滑。</p>
        </div>
        <nav class="admin-nav" aria-label="管理后台分区导航">
          ${items.map((item) => `<a class="admin-nav-link${activeSection === item.id ? " is-active" : ""}" href="#${item.id}" data-admin-anchor="${item.id}">${escape(item.label)}</a>`).join("")}
        </nav>
      </aside>`;
  }

  function bindAdminSidebarNavigation(root) {
    const links = qsa("[data-admin-anchor]", root);
    const sections = links.map((link) => qs(`#${link.dataset.adminAnchor}`, root)).filter(Boolean);
    const setActive = (id) => {
      links.forEach((link) => link.classList.toggle("is-active", link.dataset.adminAnchor === id));
    };

    links.forEach((link) => link.addEventListener("click", (event) => {
      const sectionId = link.dataset.adminAnchor;
      const target = qs(`#${sectionId}`, root);
      if (!target) return;
      event.preventDefault();
      setActive(sectionId);
      history.replaceState(null, "", `#${sectionId}`);
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    }));

    if (!sections.length || !("IntersectionObserver" in window)) return;
    const observer = new IntersectionObserver((entries) => {
      const visible = entries
        .filter((entry) => entry.isIntersecting)
        .sort((left, right) => right.intersectionRatio - left.intersectionRatio)[0];
      if (visible?.target?.id) setActive(visible.target.id);
    }, { rootMargin: "-20% 0px -60% 0px", threshold: [0.2, 0.45, 0.7] });
    sections.forEach((section) => observer.observe(section));
  }

  // ---------- Me ----------
  async function renderMe() {
    if(!state.viewer){appRoot.innerHTML=`<div class="shell" style="padding-top:40px">${emptyState("请先登录","使用 GitHub 账号登录后，才能管理自己的插件与版本。")}<div style="text-align:center;margin-top:12px"><a class="btn btn-primary" href="/api/v1/auth/github/login?redirect_to=/me">${iconSvg.github} GitHub 登录</a></div></div>`;return;}
    const me=state.viewer;
    const pluginResult=await API.get("/api/v1/me/plugins").catch(()=>({items:[]}));
    const plugins=pluginResult.items||[];
    state.meSelection = selectPluginId(plugins, state.meSelection);
    const snapshot = state.meSelection ? await API.get(`/api/v1/me/plugins/${encodeURIComponent(state.meSelection)}`).catch(()=>null) : null;
    const selectedPlugin = snapshot?.plugin || null;
    const publishedCount = plugins.filter((item) => item.status === "published").length;
    const versionCount = snapshot?.versions?.length || 0;
    const yankedCount = (snapshot?.versions || []).filter((item) => item.is_yanked).length;
    appRoot.innerHTML=`<div class="shell control-room">
      <section class="control-hero creator-hero">
        <div class="control-hero-copy">
          <span class="control-kicker">Creator Studio</span>
          <h1>我的插件工作台</h1>
          <p>在这里处理版本下架、检查最近审核反馈、决定是否彻底删除插件。</p>
          <div class="control-pills">
            <span class="control-pill">@${escape(me.github_login)}</span>
            <span class="control-pill">${plugins.length} 个管理中的插件</span>
            <span class="control-pill">${publishedCount} 个正在上架</span>
          </div>
        </div>
        <div class="profile-card">
          ${me.avatar_url?`<img src="${escape(me.avatar_url)}" alt="">`:"<div class=\"profile-card-fallback\">M</div>"}
          <div>
            <strong>${escape(me.display_name)}</strong>
            <span>${escape(me.author_id)}</span>
            <div class="table-actions"><a class="btn btn-sm" href="/author/${encodeURIComponent(me.author_id)}" data-route="/author">公开主页</a><a class="btn btn-sm btn-ghost" href="https://github.com/${encodeURIComponent(me.github_login)}" target="_blank" rel="noreferrer noopener">GitHub</a></div>
          </div>
        </div>
      </section>
      <div class="control-layout">
        <aside class="panel control-sidebar">
          <div class="section-head compact-head"><div><h2>插件列表</h2><p>选择一个插件查看版本与治理记录。</p></div></div>
          ${plugins.length ? managementPluginList(plugins, state.meSelection, "data-me-select") : emptyState("还没有插件","使用 MPDT CLI 上传第一个插件后，这里会出现管理入口。")}
        </aside>
        <div class="control-main">
          ${selectedPlugin ? `
            <section class="control-metrics-row">
              ${metricCard("当前状态", statusText(selectedPlugin.status), `最近更新 ${formatRelative(selectedPlugin.updated_at)}`)}
              ${metricCard("版本总数", versionCount, `${yankedCount} 个已下架`)}
              ${metricCard("社区反馈", `${formatNumber(selectedPlugin.comments_count)} / ${formatNumber(selectedPlugin.rating_count)}`, "评论 / 评分")}
              ${metricCard("热度", `${formatNumber(selectedPlugin.likes_count)} ❤`, `${formatNumber(selectedPlugin.downloads_count)} 下载`)}
            </section>
            <section class="ops-grid single-column-layout">
              <div class="panel plugin-sheet">
                <div class="section-head compact-head"><div><h2>${escape(selectedPlugin.display_name)}</h2><p>${escape(selectedPlugin.summary)}</p></div><div class="table-actions"><span class="badge status-${escape(selectedPlugin.status)}">${escape(statusText(selectedPlugin.status))}</span>${trustBadge(selectedPlugin.trust_level)}</div></div>
                <div class="plugin-sheet-grid">
                  <div>
                    <h4>基础信息</h4>
                    <ul class="meta-list">
                      <li><span>插件 ID</span><strong>${escape(selectedPlugin.plugin_id)}</strong></li>
                      <li><span>最新版本</span><strong>${escape(selectedPlugin.latest_version || "-")}</strong></li>
                      <li><span>分类标签</span><strong>${escape([...(selectedPlugin.categories || []).map(categoryLabel), ...(selectedPlugin.tags || [])].join(" / ") || "未设置")}</strong></li>
                      <li><span>仓库</span><strong><a href="${escape(selectedPlugin.repository_url)}" target="_blank" rel="noreferrer noopener">查看源码</a></strong></li>
                    </ul>
                  </div>
                  <div>
                    <h4>危险操作</h4>
                    <p class="soft-note">删除会移除插件、版本、评论与审核记录。建议只在确认废弃整个项目时使用。</p>
                    <div class="table-actions"><button class="btn btn-danger" data-me-plugin-delete="${escape(selectedPlugin.plugin_id)}">删除插件</button></div>
                  </div>
                </div>
              </div>
              <div class="panel version-governance">
                <div class="section-head compact-head"><div><h2>版本管理</h2><p>支持一键下架存在问题的版本，前台会立即停止推荐该版本。</p></div></div>
                <div class="governance-version-list">${(snapshot.versions || []).length ? snapshot.versions.map((item) => governanceVersionMarkup("me", selectedPlugin.plugin_id, item)).join("") : emptyState("暂无版本","当前插件还没有任何可管理的版本。")}</div>
              </div>
              <div class="panel review-stream-panel">
                <div class="section-head compact-head"><div><h2>最近治理记录</h2><p>这里会显示后台对该插件与版本的最近操作。</p></div></div>
                ${reviewFeedMarkup(snapshot.recent_reviews || [], "这个插件还没有任何治理记录。")}
              </div>
            </section>` : `<section class="panel">${emptyState("还没有可管理的插件","上传插件后，这里会展示版本和治理控制入口。")}</section>`}
        </div>
      </div>
    </div>`;

    qsa("[data-me-select]", appRoot).forEach((button) => button.addEventListener("click", () => {
      state.meSelection = button.dataset.meSelect;
      renderMe();
    }));

    qsa("[data-me-version-action='yank']", appRoot).forEach((button) => button.addEventListener("click", async () => {
      const pluginId = button.dataset.pluginId;
      const version = button.dataset.version;
      const confirmed = window.confirm(`确认下架 ${pluginId}@${version} 吗？`);
      if (!confirmed) return;
      const reason = window.prompt("可填写下架原因，留空也可以。", "") || "";
      try {
        await API.post(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}/versions/${encodeURIComponent(version)}/yank`, reason.trim() ? {reason: reason.trim()} : {});
        toast("版本已下架", "ok");
        renderMe();
      } catch (err) {
        toast(err.message || "操作失败", "error");
      }
    }));

    qs("[data-me-plugin-delete]", appRoot)?.addEventListener("click", async (event) => {
      const button = event.currentTarget;
      const pluginId = button.dataset.mePluginDelete;
      const confirmed = window.confirm(`确认彻底删除 ${pluginId} 吗？这个操作不可撤销。`);
      if (!confirmed) return;
      try {
        await API.del(`/api/v1/me/plugins/${encodeURIComponent(pluginId)}`);
        state.meSelection = null;
        toast("插件已删除", "ok");
        renderMe();
      } catch (err) {
        toast(err.message || "删除失败", "error");
      }
    });
  }

  // ---------- Author ----------
  async function renderAuthor(authorId) {
    const plugins=await API.get(`/api/v1/plugins?limit=100&sort=popular`).catch(()=>({items:[]}));
    const items=(plugins.items||[]).filter(p=>p.owner_id===authorId||(p.maintainers||[]).includes(authorId));
    const author=items.find(p=>p.owner_id===authorId)||items[0]||null;
    const header=author?`<section class="hero"><div><h1>${escape(author.owner_display_name||author.owner_login||authorId)}</h1><p>@${escape(author.owner_login||authorId)} · 共维护 ${items.length} 个插件</p></div>${author.owner_avatar_url?`<img src="${escape(author.owner_avatar_url)}" alt="" style="width:72px;height:72px;border-radius:16px">`:""}</section>`:`<section class="hero"><div><h1>${escape(authorId)}</h1><p>该作者目前没有公开发布的插件。</p></div></section>`;
    appRoot.innerHTML=`<div class="shell" style="padding:24px 0 64px">${header}<section class="section"><div class="section-head"><div><h2>公开插件</h2><p>按综合热度排序。</p></div></div><div class="grid">${items.length?items.map(pluginCard).join(""):emptyState("暂无插件","该作者尚未发布任何已审核通过的插件。")}</div></section></div>`;
  }

  // ---------- Admin ----------
  async function renderAdmin() {
    if(!state.viewer||!state.viewer.is_admin){appRoot.innerHTML=`<div class="shell" style="padding-top:40px">${emptyState("需要管理员权限","请使用具有管理员权限的 GitHub 账号登录。")}</div>`;return;}
    appRoot.innerHTML='<div class="shell control-room" data-admin-root><div class="loading-screen">加载中…</div></div>';
    const [system,dashboard,pluginResult,reviews]=await Promise.all([
      API.get("/api/v1/admin/system"),
      API.get("/api/v1/admin/dashboard"),
      API.get("/api/v1/admin/plugins"),
      API.get("/api/v1/admin/reviews"),
    ]);
    const plugins=pluginResult.items||[];
    state.adminSelection = selectPluginId(plugins, state.adminSelection, "pending_review");
    const snapshot = state.adminSelection ? await API.get(`/api/v1/admin/plugins/${encodeURIComponent(state.adminSelection)}`).catch(()=>null) : null;
    const selectedPlugin = snapshot?.plugin || null;
    const activeSection = [
      "admin-overview",
      "admin-queue",
      "admin-plugin-governance",
      "admin-version-governance",
      "admin-trends",
      "admin-review-feed",
      "admin-plugin-history",
    ].includes((location.hash || "").slice(1)) ? (location.hash || "").slice(1) : "admin-overview";
    qs("[data-admin-root]").innerHTML=`
      <div class="admin-shell">
        ${adminSidebarMarkup(activeSection)}
        <div class="admin-page-content">
          <section class="control-hero admin-hero" id="admin-overview">
            <div class="control-hero-copy">
              <span class="control-kicker">Moderation Room</span>
              <h1>插件市场后端管理台</h1>
              <p>在这里进行状态治理、服务监控和社区节奏追踪，方便你判断市场的实时动态。</p>
              <div class="control-pills">
                <span class="control-pill">${escape(system.environment)}</span>
                <span class="control-pill">运行 ${escape(formatUptime(system.uptime_seconds))}</span>
                <span class="control-pill">OAuth ${system.github_oauth_configured ? "已接通" : "未配置"}</span>
                <span class="control-pill">Webhook ${system.github_webhook_configured ? "在线" : "未配置"}</span>
              </div>
            </div>
            <div class="server-stack">
              <div class="server-tile"><span>服务状态</span><strong>${escape(system.status)}</strong><small>数据库 ${escape(system.database)}</small></div>
              <div class="server-tile"><span>审核模式</span><strong>${system.review_required ? "人工审核" : "快速发布"}</strong><small>最近审核 ${formatRelative(system.stats.latest_review_at)}</small></div>
              <div class="server-tile"><span>数据库路径</span><strong>${escape(system.database_path || "内存数据库")}</strong><small>启动于 ${formatDate(system.started_at)}</small></div>
            </div>
          </section>

          <section class="control-metrics-row admin-metrics">
            ${metricCard("插件总数", dashboard.stats.plugins_total, `${dashboard.stats.pending_plugins} 待审核`)}
            ${metricCard("版本总数", dashboard.stats.versions_total, `${dashboard.stats.pending_versions} 待审核`)}
            ${metricCard("评论 / 评分", `${formatNumber(dashboard.stats.comments_total)} / ${formatNumber(dashboard.stats.ratings_total)}`, "社区互动")}
            ${metricCard("点赞 / 下载", `${formatNumber(dashboard.stats.likes_total)} / ${formatNumber(dashboard.stats.downloads_total)}`, "热度追踪")}
            ${metricCard("作者 / Webhook", `${dashboard.stats.authors_total} / ${dashboard.stats.webhooks_total}`, "生态节点")}
          </section>

          <section class="admin-board">
            <div class="panel activity-panel">
              <div class="section-head compact-head"><div><h2>最近 7 天市场动态</h2><p>重点观察新增插件、评论和评分的波动。</p></div></div>
              ${activityChartMarkup(dashboard.activity || [])}
              <div class="breakdown-row">
                ${breakdownMarkup("插件状态分布", dashboard.plugin_status_breakdown)}
                ${breakdownMarkup("版本状态分布", dashboard.version_status_breakdown)}
              </div>
            </div>
            <div class="panel queue-panel" id="admin-queue">
              <div class="section-head compact-head"><div><h2>治理队列</h2><p>优先处理待审核与异常插件。点击条目切换右侧详情。</p></div></div>
              ${plugins.length ? managementPluginList(plugins, state.adminSelection, "data-admin-select") : emptyState("暂无插件","当前市场没有插件记录。")}
            </div>
          </section>

          <section class="ops-grid">
            <div class="panel plugin-sheet" id="admin-plugin-governance">
          ${selectedPlugin ? `
            <div class="section-head compact-head"><div><h2>${escape(selectedPlugin.display_name)}</h2><p>${escape(selectedPlugin.summary)}</p></div><div class="table-actions">${trustBadge(selectedPlugin.trust_level)}<span class="badge status-${escape(selectedPlugin.status)}">${escape(statusText(selectedPlugin.status))}</span></div></div>
            <div class="plugin-sheet-grid">
              <div>
                <h4>治理动作</h4>
                <p class="soft-note">支持退回、封禁、下架、删除，以及在修复后重新上架。</p>
                <div class="table-actions admin-action-cluster">
                  ${selectedPlugin.status !== "published" ? `<button class="btn btn-sm" data-admin-plugin-action="publish" data-plugin-id="${escape(selectedPlugin.plugin_id)}">重新上架</button>` : ""}
                  ${selectedPlugin.status !== "draft" ? `<button class="btn btn-sm" data-admin-plugin-action="reject" data-plugin-id="${escape(selectedPlugin.plugin_id)}">退回</button>` : ""}
                  ${selectedPlugin.status !== "deprecated" ? `<button class="btn btn-sm" data-admin-plugin-action="deprecate" data-plugin-id="${escape(selectedPlugin.plugin_id)}">下架</button>` : ""}
                  ${selectedPlugin.status !== "blocked" ? `<button class="btn btn-sm btn-danger" data-admin-plugin-action="block" data-plugin-id="${escape(selectedPlugin.plugin_id)}">封禁</button>` : ""}
                  <button class="btn btn-sm btn-danger" data-admin-plugin-action="delete" data-plugin-id="${escape(selectedPlugin.plugin_id)}">删除</button>
                </div>
                <h4 style="margin-top:18px">社区标识</h4>
                <p class="soft-note">直接切换插件在市场中显示的身份标签，用于区分官方、认证和普通社区作品。</p>
                <div class="table-actions trust-switch-row">
                  ${["official", "verified", "community"].map((level) => `<button class="btn btn-sm${selectedPlugin.trust_level === level ? " is-active" : ""}" data-admin-trust-level="${level}" data-plugin-id="${escape(selectedPlugin.plugin_id)}">${trustLevelLabel(level)}</button>`).join("")}
                </div>
              </div>
              <div>
                <h4>社区状态</h4>
                <ul class="meta-list">
                  <li><span>作者</span><strong>${escape(selectedPlugin.owner_display_name || selectedPlugin.owner_login || selectedPlugin.owner_id)}</strong></li>
                  <li><span>当前标识</span><strong>${escape(trustLevelLabel(selectedPlugin.trust_level))}</strong></li>
                  <li><span>评分</span><strong>${selectedPlugin.rating_avg.toFixed(1)} / ${selectedPlugin.rating_count}</strong></li>
                  <li><span>互动</span><strong>${formatNumber(selectedPlugin.comments_count)} 评论 · ${formatNumber(selectedPlugin.likes_count)} 点赞</strong></li>
                  <li><span>流量</span><strong>${formatNumber(selectedPlugin.downloads_count)} 下载</strong></li>
                </ul>
              </div>
            </div>
          ` : emptyState("未选择插件","从左侧队列里点一个插件，即可查看完整治理面板。")}
            </div>
            <div class="panel version-governance" id="admin-version-governance">
              <div class="section-head compact-head"><div><h2>版本治理</h2><p>支持恢复、退回、下架与封禁版本。</p></div></div>
              ${selectedPlugin ? `<div class="governance-version-list">${(snapshot.versions || []).length ? snapshot.versions.map((item) => governanceVersionMarkup("admin", selectedPlugin.plugin_id, item)).join("") : emptyState("暂无版本","当前插件还没有任何版本记录。")}</div>` : emptyState("未选择插件","先从队列中选择插件。")}
            </div>
          </section>

          <section class="ops-grid">
            <div class="panel trend-panel" id="admin-trends">
              <div class="section-head compact-head"><div><h2>热门插件观察</h2><p>按趋势热度排序，方便观察社区讨论中心。</p></div></div>
              <div class="trend-list">${(dashboard.popular_plugins || []).map((plugin) => `
                <a class="trend-item" href="/plugin/${encodeURIComponent(plugin.plugin_id)}" data-route="/plugin">
                  <div class="trend-item-main"><strong>${escape(plugin.display_name)}</strong><span>${escape(plugin.plugin_id)}</span></div>
                  <div class="trend-item-meta"><span>${formatNumber(plugin.comments_count)} 评</span><span>${formatNumber(plugin.downloads_count)} 下载</span></div>
                </a>`).join("")}</div>
            </div>
            <div class="panel review-stream-panel" id="admin-review-feed">
              <div class="section-head compact-head"><div><h2>最近审核流</h2><p>展示最新的插件与版本治理动作。</p></div></div>
              ${reviewFeedMarkup((reviews || []).slice().reverse().slice(0, 18), "暂无审核记录。")}
            </div>
          </section>

          <section class="panel review-stream-panel" id="admin-plugin-history">
            <div class="section-head compact-head"><div><h2>当前选中插件的治理历史</h2><p>帮助判断这次要不要恢复上架，还是继续封禁。</p></div></div>
            ${selectedPlugin ? reviewFeedMarkup(snapshot.recent_reviews || [], "当前插件暂无治理历史。") : emptyState("未选择插件","先在治理队列中选择插件。")}
          </section>
        </div>
      </div>`;

    qsa("[data-admin-select]", appRoot).forEach((button) => button.addEventListener("click", () => {
      state.adminSelection = button.dataset.adminSelect;
      renderAdmin();
    }));

    qsa("[data-admin-plugin-action]", appRoot).forEach((button) => button.addEventListener("click", async () => {
      const pluginId = button.dataset.pluginId;
      const action = button.dataset.adminPluginAction;
      const confirmed = window.confirm(`确认执行 ${action} 操作：${pluginId} ？`);
      if (!confirmed) return;
      const reason = action === "delete" ? "" : (window.prompt("可填写操作原因，留空也可以。", "") || "");
      try {
        if (action === "delete") {
          await API.del(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}`);
          if (state.adminSelection === pluginId) state.adminSelection = null;
        } else {
          await API.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/${action}`, reason.trim() ? {reason: reason.trim()} : {});
        }
        toast(action === "delete" ? "插件已删除" : "治理动作已执行", "ok");
        renderAdmin();
      } catch (err) {
        toast(err.message || "操作失败", "error");
      }
    }));

    qsa("[data-admin-trust-level]", appRoot).forEach((button) => button.addEventListener("click", async () => {
      const pluginId = button.dataset.pluginId;
      const trustLevel = button.dataset.adminTrustLevel;
      if (!pluginId || !trustLevel) return;
      if (selectedPlugin?.trust_level === trustLevel) return;
      const reason = window.prompt(`可填写切换为“${trustLevelLabel(trustLevel)}”的原因，留空也可以。`, "") || "";
      try {
        await API.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/trust-level/${encodeURIComponent(trustLevel)}`, reason.trim() ? {reason: reason.trim()} : {});
        toast("社区标识已更新", "ok");
        renderAdmin();
      } catch (err) {
        toast(err.message || "切换失败", "error");
      }
    }));

    qsa("[data-admin-version-action]", appRoot).forEach((button) => button.addEventListener("click", async () => {
      const pluginId = button.dataset.pluginId;
      const version = button.dataset.version;
      const action = button.dataset.adminVersionAction;
      const confirmed = window.confirm(`确认对 ${pluginId}@${version} 执行 ${action} 吗？`);
      if (!confirmed) return;
      const reason = window.prompt("可填写操作原因，留空也可以。", "") || "";
      try {
        await API.post(`/api/v1/admin/plugins/${encodeURIComponent(pluginId)}/versions/${encodeURIComponent(version)}/${action}`, reason.trim() ? {reason: reason.trim()} : {});
        toast("版本治理动作已执行", "ok");
        renderAdmin();
      } catch (err) {
        toast(err.message || "操作失败", "error");
      }
    }));

    bindAdminSidebarNavigation(appRoot);
  }

  // ---------- Search ----------
  qs("[data-search-form]")?.addEventListener("submit",(e)=>{
    e.preventDefault();
    const q=qs("[data-search-input]").value.trim();
    marketState.query=q; marketState.offset=0;
    if(parseRoute().name!=="market"){navigate("/?"+(q?`q=${encodeURIComponent(q)}`:""));}
    else{history.replaceState(null,"",q?`/?q=${encodeURIComponent(q)}`:"/");updateFeaturedVisibility();renderMarketGrid();}
  });

  qs("[data-mobile-toggle]")?.addEventListener("click",()=>{
    const nav=qs("[data-topbar-nav]"); if(!nav) return;
    if(nav.dataset.hideMobile==="true") delete nav.dataset.hideMobile; else nav.dataset.hideMobile="true";
  });

  // ---------- Boot ----------
  showFirstVisitDisclaimer();
  render();
})();
