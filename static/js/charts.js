/* ── Charts — Premium Augur Theme ──────────────────── */
window.AugurChart = {
  render(canvasId, financials) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !financials?.length) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();

    canvas.width  = rect.width  * dpr;
    canvas.height = rect.height * dpr;
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;

    ctx.clearRect(0, 0, W, H);

    const data = [...financials].reverse();
    const revs = data.map(f => f.revenue_cr ?? 0);
    const pats  = data.map(f => f.pat_cr  ?? 0);
    const labels = data.map(f => f.fy ?? '');

    const pad = { top: 24, right: 20, bottom: 36, left: 56 };
    const cW = W - pad.left - pad.right;
    const cH = H - pad.top  - pad.bottom;

    const maxV = Math.max(...revs, ...pats, 10) * 1.18;
    const minV = Math.min(0, ...pats);
    const range = maxV - minV;

    const X = i => pad.left + (data.length === 1 ? cW / 2 : i * (cW / (data.length - 1)));
    const Y = v => pad.top + cH - ((v - minV) / range) * cH;

    // Grid lines
    for (let i = 0; i <= 4; i++) {
      const v = minV + (range / 4) * i;
      const y = Y(v);
      ctx.strokeStyle = 'rgba(255,255,255,0.04)';
      ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(pad.left, y); ctx.lineTo(pad.left + cW, y); ctx.stroke();

      ctx.fillStyle = '#5c5c6d';
      ctx.font = '10px Inter, sans-serif';
      ctx.textAlign = 'right';
      ctx.fillText(v >= 1000 ? `₹${(v/1000).toFixed(1)}k` : `₹${Math.round(v)}`, pad.left - 6, y + 3);
    }

    // X labels
    ctx.fillStyle = '#5c5c6d';
    ctx.font = '10px Inter, sans-serif';
    ctx.textAlign = 'center';
    data.forEach((_, i) => ctx.fillText(labels[i], X(i), pad.top + cH + 22));

    // Revenue area + line (indigo theme)
    {
      const g = ctx.createLinearGradient(0, pad.top, 0, pad.top + cH);
      g.addColorStop(0, 'rgba(129, 140, 248, 0.18)');
      g.addColorStop(0.6, 'rgba(129, 140, 248, 0.04)');
      g.addColorStop(1, 'rgba(129, 140, 248, 0)');

      ctx.beginPath();
      ctx.moveTo(X(0), pad.top + cH);
      data.forEach((_, i) => ctx.lineTo(X(i), Y(revs[i])));
      ctx.lineTo(X(data.length - 1), pad.top + cH);
      ctx.closePath();
      ctx.fillStyle = g;
      ctx.fill();

      ctx.beginPath();
      ctx.strokeStyle = '#818cf8';
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      data.forEach((_, i) => { i === 0 ? ctx.moveTo(X(i), Y(revs[i])) : ctx.lineTo(X(i), Y(revs[i])); });
      ctx.stroke();

      data.forEach((_, i) => {
        ctx.beginPath(); ctx.arc(X(i), Y(revs[i]), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = '#0a0a0c'; ctx.fill();
        ctx.strokeStyle = '#818cf8'; ctx.lineWidth = 2; ctx.stroke();
      });
    }

    // PAT line (emerald theme)
    {
      ctx.beginPath();
      ctx.strokeStyle = '#34d399';
      ctx.lineWidth = 2;
      ctx.lineJoin = 'round';
      ctx.lineCap = 'round';
      data.forEach((_, i) => { i === 0 ? ctx.moveTo(X(i), Y(pats[i])) : ctx.lineTo(X(i), Y(pats[i])); });
      ctx.stroke();

      data.forEach((_, i) => {
        ctx.beginPath(); ctx.arc(X(i), Y(pats[i]), 3.5, 0, Math.PI * 2);
        ctx.fillStyle = '#0a0a0c'; ctx.fill();
        ctx.strokeStyle = '#34d399'; ctx.lineWidth = 2; ctx.stroke();
      });
    }
  }
};
