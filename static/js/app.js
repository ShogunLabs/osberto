/* ── Augur IPO Intelligence — App Engine ─────────────── */

// ── Avatar colours (12 distinct, dark-friendly) ──────
const AVATAR_COLORS = [
  '#2563eb','#7c3aed','#059669','#dc2626','#d97706',
  '#0891b2','#9333ea','#16a34a','#ea580c','#0284c7',
  '#be185d','#4f46e5'
];

function avatarColor(name) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

function initials(name) {
  const words = name.replace(/[^a-zA-Z\s]/g, ' ').trim().split(/\s+/);
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[words.length - 1][0]).toUpperCase();
}

// ── Formatters ───────────────────────────────────────
const crFmt = v => v == null ? '—' : `₹${Number(v).toLocaleString('en-IN', { maximumFractionDigits: 1 })} Cr`;
const numFmt = v => v == null ? '—' : Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 });

// ── State ─────────────────────────────────────────────
const S = {
  all: [],
  filtered: [],
  selected: null,
  filters: {
    search: '', type: 'all'
  }
};

// ── Toast ─────────────────────────────────────────────
function toast(msg, ok = true) {
  const el  = document.getElementById('toast');
  const msg_ = document.getElementById('toast-msg');
  const ico  = el.querySelector('svg');
  if (!el || !msg_) return;
  msg_.textContent = msg;
  ico.style.stroke = ok ? 'var(--green)' : 'var(--amber)';
  el.classList.add('show');
  setTimeout(() => el.classList.remove('show'), 3500);
}

// ── Overlay helpers ───────────────────────────────────
function openOverlay(id) {
  document.getElementById(id).classList.add('open');
  document.body.style.overflow = 'hidden';
}
function closeOverlay(id) {
  document.getElementById(id).classList.remove('open');
  document.body.style.overflow = '';
}

// ── Routing ───────────────────────────────────────────
function navigateTo(path) {
  window.location.hash = path ? `#/ipo/${path}` : '#/';
}

function getRoute() {
  const hash = window.location.hash || '#/';
  if (hash.startsWith('#/ipo/')) {
    return { view: 'detail', id: decodeURIComponent(hash.slice(6)) };
  }
  return { view: 'list' };
}

function handleRoute() {
  const route = getRoute();
  const listView = document.getElementById('view-list');
  const detailView = document.getElementById('view-detail');

  if (route.view === 'detail') {
    listView.style.display = 'none';
    detailView.style.display = 'block';
    loadDetail(route.id);
  } else {
    listView.style.display = 'block';
    detailView.style.display = 'none';
    window.scrollTo(0, 0);
  }
}

// ── Boot ──────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // today label
  const d = new Date();
  const el = document.getElementById('today-label');
  if (el) el.textContent = d.toLocaleDateString('en-IN', { day:'numeric', month:'short', year:'numeric' });

  wireEvents();
  boot();
});

window.addEventListener('hashchange', handleRoute);

async function boot() {
  await loadIpos();
  handleRoute();
}

// ── API calls ─────────────────────────────────────────
async function loadIpos() {
  try {
    const r = await fetch('/api/v1/ipos?limit=100');
    if (!r.ok) throw new Error();
    const d = await r.json();
    S.all = d.items || [];
    applyAndRender();
  } catch (e) {
    console.error(e);
    toast('Failed to load IPO data', false);
  }
}

// ── Filter pipeline ───────────────────────────────────
function applyAndRender() {
  let list = [...S.all];
  const f = S.filters;

  // search
  if (f.search) {
    const q = f.search.toLowerCase();
    list = list.filter(i =>
      i.name.toLowerCase().includes(q) ||
      (i.symbol || '').toLowerCase().includes(q) ||
      (i.industry || '').toLowerCase().includes(q)
    );
  }

  // type tab
  if (f.type !== 'all') list = list.filter(i => i.issue_type === f.type);

  // sort by issue size desc by default
  list.sort((a, b) => ((b.issue_size || 0) - (a.issue_size || 0)));

  S.filtered = list;
  renderList(list);
}

// ── List Rendering ───────────────────────────────────
function renderList(items) {
  const el = document.getElementById('ipo-list');
  const countEl = document.getElementById('ipo-count');
  if (!el) return;

  if (countEl) countEl.textContent = items.length;

  if (!items.length) {
    el.innerHTML = `<div class="empty-state">
      <h3>No matching IPOs</h3>
      <p>Try clearing your search or broadening your filters.</p>
    </div>`;
    return;
  }

  el.innerHTML = items.map(ipo => {
    const issue = ipo.issue || {};
    const color = avatarColor(ipo.name);
    const init  = initials(ipo.name);
    const isSme = ipo.issue_type === 'sme';

    // Build price/issue info
    const total = ipo.issue_size;
    const fresh = issue.fresh_cr;
    let priceInfo = '';
    if (total != null) {
      priceInfo = crFmt(total);
    } else if (fresh != null) {
      priceInfo = `${crFmt(fresh)} (fresh)`;
    } else {
      priceInfo = 'Book-built';
    }

    // GMP-like indicator using profitability or revenue growth
    let gmpHtml = '';
    if (ipo.latest_pat != null) {
      const isPos = ipo.latest_pat > 0;
      gmpHtml = `<span class="gmp ${isPos ? '' : 'negative'}">PAT ${crFmt(ipo.latest_pat)}</span>`;
    }

    return `
    <div class="ipo-row" onclick="navigateTo('${ipo.id}')">
      <div class="avatar" style="background:${color}">${init}</div>
      <div class="row-info">
        <div class="row-name">
          ${ipo.name}
          ${isSme ? '<span class="sme-badge">SME</span>' : ''}
        </div>
        <div class="row-sub">
          <span class="price-range">${priceInfo}</span>
          ${gmpHtml ? ` · ${gmpHtml}` : ''}
        </div>
      </div>
      <div class="row-right">
        <div class="row-status">${ipo.industry || '—'}</div>
        <div class="row-stage">${ipo.basis || 'DRHP'} · ${ipo.symbol}</div>
      </div>
    </div>`;
  }).join('');
}

// ── Detail View ──────────────────────────────────────
async function loadDetail(ipoId) {
  try {
    const r = await fetch(`/api/v1/ipos/${ipoId}`);
    if (!r.ok) throw new Error();
    const ipo = await r.json();
    S.selected = ipo;
    populateDetail(ipo);
  } catch (e) {
    toast('Failed to load IPO details', false);
    navigateTo('');
  }
}

function populateDetail(ipo) {
  const issue = ipo.issue || {};
  const color = avatarColor(ipo.name);
  const init  = initials(ipo.name);

  // Breadcrumb
  setText('d-breadcrumb', ipo.name);

  // Avatar
  const avEl = document.getElementById('d-avatar');
  if (avEl) { avEl.textContent = init; avEl.style.background = color; }

  // Name
  setText('d-name', ipo.name);

  // Meta line
  const metaEl = document.getElementById('d-meta');
  if (metaEl) {
    const parts = [
      ipo.symbol,
      ipo.listing_exchange || 'BSE NSE',
      'Upcoming',
    ].filter(Boolean);
    metaEl.innerHTML = parts.map((p, i) =>
      `${p}${i < parts.length - 1 ? ' <span class="sep">·</span> ' : ''}`
    ).join('');
  }

  // Status badge
  const statusEl = document.getElementById('d-status-badge');
  if (statusEl) statusEl.textContent = 'DRHP Stage';

  // Key Metrics
  setText('d-issue-size', ipo.issue_size != null ? crFmt(ipo.issue_size) : 'Book-built');
  setText('d-fresh', issue.fresh_cr != null ? crFmt(issue.fresh_cr) : '—');
  setText('d-ofs', issue.ofs_cr != null ? crFmt(issue.ofs_cr) : '—');
  setText('d-revenue', ipo.latest_revenue != null ? crFmt(ipo.latest_revenue) : '—');

  // Description
  const descEl = document.getElementById('d-description');
  if (descEl) descEl.textContent = ipo.description || 'No description provided in prospectus.';

  // Capital Deployment table
  const ob = document.getElementById('d-objects-tbody');
  if (ob) {
    if (!ipo.objects?.length) {
      ob.innerHTML = `<tr><td colspan="3" style="text-align:center;color:var(--text-3);padding:20px 0;">No itemised objects available</td></tr>`;
    } else {
      ob.innerHTML = ipo.objects.map(o => `
        <tr>
          <td class="td-main" style="white-space:normal;max-width:280px;">${o.purpose}</td>
          <td class="td-green td-mono">${o.amount_cr != null ? crFmt(o.amount_cr) : 'TBD'}</td>
          <td class="td-dim">${o.percentage_of_fresh != null ? o.percentage_of_fresh + '%' : '—'}</td>
        </tr>`).join('');
    }
  }

  // Financials label
  setText('d-fin-label', `Financials (${ipo.unit_note || '₹ Cr'})`);

  // Financials table
  const fb = document.getElementById('d-fin-tbody');
  if (fb) {
    if (!ipo.financials?.length) {
      fb.innerHTML = `<tr><td colspan="6" style="text-align:center;color:var(--text-3);padding:20px 0;">No financial data available</td></tr>`;
    } else {
      fb.innerHTML = ipo.financials.map(f => `
        <tr>
          <td class="td-main">${f.fy}</td>
          <td class="td-mono" style="color:#818cf8;">${f.revenue_cr != null ? crFmt(f.revenue_cr) : '—'}</td>
          <td class="td-mono ${f.pat_cr > 0 ? 'td-green' : f.pat_cr != null ? 'td-red' : ''}">${f.pat_cr != null ? crFmt(f.pat_cr) : '—'}</td>
          <td class="td-mono">${f.pat_margin_pct != null ? f.pat_margin_pct + '%' : '—'}</td>
          <td class="td-mono">${f.net_worth_cr != null ? crFmt(f.net_worth_cr) : '—'}</td>
          <td class="td-mono">${f.eps != null ? '₹' + f.eps : '—'}</td>
        </tr>`).join('');
    }
  }

  // Promoter
  const promoEl = document.getElementById('d-promo-pre');
  if (promoEl) promoEl.textContent = ipo.promoter_holding_pre != null ? ipo.promoter_holding_pre + '%' : 'Not stated';

  // Risk factors
  const rl = document.getElementById('d-risk-list');
  if (rl) {
    if (!ipo.top_risks?.length) {
      rl.innerHTML = `<div style="color:var(--text-3);font-size:0.82rem;padding:8px 0;">No risk summary available.</div>`;
    } else {
      rl.innerHTML = ipo.top_risks.map((r, i) => `
        <div class="risk-item">
          <span class="risk-num">${i + 1}</span>
          <span>${r}</span>
        </div>`).join('');
    }
  }

  // Render chart
  if (ipo.financials?.length) {
    setTimeout(() => window.AugurChart?.render('fin-chart', ipo.financials), 80);
  }

  // Schema data (pre-populate for modal)
  const schemaEl = document.getElementById('schema-code');
  if (schemaEl) {
    const augurRecord = {
      id: ipo.id, symbol: ipo.symbol, name: ipo.name, status: ipo.status,
      isin: ipo.isin, issue_type: ipo.issue_type, issue_size: ipo.issue_size,
      industry: ipo.industry, listing_exchange: ipo.listing_exchange,
      drhp_url: ipo.drhp_url, rhp_url: ipo.rhp_url,
      timeline: { drhp_stage: true, basis: ipo.basis, unit_note: ipo.unit_note },
      registrar_info: { source: 'DRHP', extracted: true },
      raw_data: ipo.raw_data,
      first_seen_at: ipo.last_modified
    };
    schemaEl.textContent = JSON.stringify(augurRecord, null, 2);
  }

  // Scroll to top
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showSchemaModal() {
  openOverlay('schema-overlay');
}

// ── Upload ────────────────────────────────────────────
async function uploadFile(file) {
  if (!file.name.endsWith('.json')) { toast('Only .json files accepted', false); return; }
  const form = new FormData();
  form.append('file', file);
  try {
    const r = await fetch('/api/v1/ipos/upload-file', { method: 'POST', body: form });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    const d = await r.json();
    toast(`Uploaded ${d.filename} — ${d.total_ipos} indexed`);
    closeOverlay('upload-overlay');
    await boot();
  } catch (e) {
    toast(e.message || 'Upload failed', false);
  }
}

async function submitPaste() {
  const txt = document.getElementById('paste-area')?.value?.trim();
  if (!txt) { toast('Paste a valid JSON first', false); return; }
  try {
    const parsed = JSON.parse(txt);
    const r = await fetch('/api/v1/ipos/create', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(parsed)
    });
    if (!r.ok) { const e = await r.json(); throw new Error(e.detail); }
    toast('IPO saved and indexed!');
    closeOverlay('upload-overlay');
    document.getElementById('paste-area').value = '';
    await boot();
  } catch (e) {
    toast(e.message || 'Invalid JSON', false);
  }
}

// ── Utility ───────────────────────────────────────────
function setText(id, val) {
  const el = document.getElementById(id);
  if (el) el.textContent = val;
}

// ── Wire all events ───────────────────────────────────
function wireEvents() {
  // Search
  const si = document.getElementById('search-input');
  if (si) si.addEventListener('input', e => { S.filters.search = e.target.value; applyAndRender(); });

  // Keyboard shortcuts
  window.addEventListener('keydown', e => {
    if ((e.key === '/' || (e.metaKey && e.key === 'k')) && document.activeElement !== si) {
      e.preventDefault(); si?.focus();
    }
    if (e.key === 'Escape') {
      si?.blur();
      ['schema-overlay', 'upload-overlay'].forEach(closeOverlay);
    }
  });

  // Overlay close on bg click
  document.querySelectorAll('.overlay').forEach(o => {
    o.addEventListener('click', e => { if (e.target === o) closeOverlay(o.id); });
  });

  // Type tabs
  document.getElementById('type-tabs')?.querySelectorAll('.type-tab').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.type-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      S.filters.type = btn.dataset.type;
      applyAndRender();
    });
  });

  // Login button → Upload modal
  document.getElementById('btn-add-json')?.addEventListener('click', () => openOverlay('upload-overlay'));

  // Copy schema
  document.getElementById('btn-copy-schema')?.addEventListener('click', () => {
    const code = document.getElementById('schema-code')?.textContent;
    if (code) { navigator.clipboard.writeText(code); toast('Copied to clipboard'); }
  });

  // Upload dropzone
  const dz = document.getElementById('dropzone');
  const fi = document.getElementById('file-input');
  if (dz && fi) {
    dz.addEventListener('click', () => fi.click());
    fi.addEventListener('change', e => { if (e.target.files[0]) uploadFile(e.target.files[0]); });
    dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag'); });
    dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
    dz.addEventListener('drop', e => {
      e.preventDefault(); dz.classList.remove('drag');
      if (e.dataTransfer.files[0]) uploadFile(e.dataTransfer.files[0]);
    });
  }
  document.getElementById('btn-submit-paste')?.addEventListener('click', submitPaste);
}
