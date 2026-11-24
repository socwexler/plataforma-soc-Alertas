(() => {
  const D = JSON.parse(document.getElementById('datos').textContent);
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const PDF = document.body.classList.contains('pdf');
  const stage = $('#stage'), slides = $$('.slide'), total = slides.length;
  const quieto = PDF || matchMedia('(prefers-reduced-motion: reduce)').matches;
  let cur = -1, escala = 1;
  const num = (v) => Math.round(v).toLocaleString('es-CO').replace(/ /g, '.');
  const compacto = (v) => new Intl.NumberFormat('es-CO', { notation: 'compact', maximumFractionDigits: 1 }).format(v);

  // ---------- pie de página y ajuste del texto al espacio disponible
  slides.forEach((s, i) => {
    if (s.matches('.cover,.divider,.closing,.portada,.fin')) return;
    const f = document.createElement('div'); f.className = 'foot';
    const lab = document.createElement('span'); lab.textContent = D.pie;
    f.innerHTML = '<i class="iso"></i>'; f.append(lab);
    f.insertAdjacentHTML('beforeend', `<span class="sep"></span><span class="num">${String(i + 1).padStart(2, '0')} / ${total}</span>`);
    s.append(f);
  });
  const ajustarTexto = () => { stage.classList.add('midiendo'); slides.forEach((s) => {
    const c = $('.cuerpo', s), ts = $$('[data-fit]', s);
    if (!c || !ts.length) return;
    const cabe = () => c.scrollHeight <= c.clientHeight + 1 && [...ts.map((t) => t.closest('.tx')), ...$$('.lado, .tj', s)].every((p) => !p || p.scrollHeight <= p.clientHeight + 1);
    const base = ts.map((x) => parseFloat(getComputedStyle(x).fontSize));
    const poner = (f) => ts.forEach((x, i) => { x.style.fontSize = Math.max(12, base[i] * f) + 'px'; });
    let f = 1;
    if (cabe()) { while (f < 1.35) { poner(f + .05); if (!cabe()) { poner(f); break; } f += .05; } }  // crece si sobra espacio
    else while (!cabe() && f > .6) { f -= .03; poner(f); }                                            // se reduce si no cabe
  }); stage.classList.remove('midiendo'); };

  // ---------- escenario
  const fit = () => { escala = Math.min(innerWidth / 1920, innerHeight / 1080); stage.style.transform = `translate(-50%, -50%) scale(${escala})`; };
  if (!PDF) { addEventListener('resize', fit); fit(); }
  addEventListener('beforeprint', () => document.body.classList.add('pdf'));
  addEventListener('afterprint', () => { if (!PDF) document.body.classList.remove('pdf'); });

  // ---------- contadores: cuentan hasta el número escrito y terminan con el texto original
  const contar = (s) => $$('[data-cuenta]', s).forEach((el) => {
    const texto = el.dataset.texto ??= el.textContent;
    const m = /^([\d.]+)(,\d+)?(.*)$/.exec(texto.trim());
    if (!m || quieto) return;
    const hasta = parseFloat(m[1].replace(/\./g, '') + (m[2] || '').replace(',', '.')), dec = m[2] ? m[2].length - 1 : 0;
    const t0 = performance.now(), ficha = (el._f = (el._f || 0) + 1);
    const paso = (t) => {
      if (el._f !== ficha) return;
      const k = Math.min(1, (t - t0) / 1300), v = hasta * (1 - Math.pow(1 - k, 3));
      el.textContent = k < 1 ? (dec ? v.toFixed(dec).replace('.', ',') : num(v)) + m[3] : texto;
      if (k < 1) requestAnimationFrame(paso);
    };
    requestAnimationFrame(paso);
  });

  // ---------- navegación
  const lista = $('#index-list');
  const abrir = (id, v) => $('#' + id).classList.toggle('open', v);
  const go = (n) => {
    n = Math.max(0, Math.min(total - 1, n));
    if (n === cur) return;
    slides[cur]?.classList.remove('active');
    cur = n; slides[cur].classList.add('active'); contar(slides[cur]);
    $('#progress').style.width = ((cur + 1) / total * 100) + '%';
    $('#notes-text').textContent = slides[cur].dataset.notes || 'Sin notas para esta diapositiva.';
    $$('a', lista).forEach((a, i) => a.classList.toggle('cur', i === cur));
    $('#tip').classList.remove('on');
  };
  slides.forEach((s, i) => {
    const li = document.createElement('li'), a = document.createElement('a');
    a.textContent = s.dataset.title; a.tabIndex = 0;
    a.onclick = () => { go(i); abrir('index', false); };
    li.append(a); lista.append(li);
  });
  $$('[data-ir]').forEach((b) => { b.onclick = () => { const i = slides.findIndex((s) => s.dataset.sec === b.dataset.ir); if (i >= 0) go(i); }; });
  const completa = () => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.().catch(() => {}));
  $('#b-prev').onclick = () => go(cur - 1); $('#b-next').onclick = () => go(cur + 1);
  $('#b-index').onclick = () => abrir('index'); $('#b-notes').onclick = () => abrir('notes'); $('#b-full').onclick = completa;
  addEventListener('keydown', (ev) => {
    const enBoton = ev.target.closest?.('button,a');
    if ($('#luz').classList.contains('open')) { if (ev.key === 'Escape') cerrarLuz(); return; }
    if (['ArrowRight', 'PageDown'].includes(ev.key) || ([' ', 'Enter'].includes(ev.key) && !enBoton)) { ev.preventDefault(); go(cur + 1); }
    else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(ev.key)) { ev.preventDefault(); go(cur - 1); }
    else if (ev.key === 'Enter' && enBoton?.matches('#index a')) enBoton.click();
    else if (ev.key === 'Home') go(0); else if (ev.key === 'End') go(total - 1);
    else if (ev.key.toLowerCase() === 'f' && !ev.ctrlKey) completa();
    else if (ev.key.toLowerCase() === 'i') abrir('index');
    else if (ev.key.toLowerCase() === 'n') abrir('notes');
    else if (ev.key === 'Escape') { abrir('index', false); abrir('notes', false); }
  });
  let tx = null;
  addEventListener('touchstart', (ev) => { tx = ev.target.closest('.mapa') ? null : ev.touches[0].clientX; }, { passive: true });
  addEventListener('touchend', (ev) => { if (tx === null) return; const dx = ev.changedTouches[0].clientX - tx; if (Math.abs(dx) > 50) go(cur + (dx < 0 ? 1 : -1)); tx = null; });

  // ---------- los controles se ocultan si el cursor está quieto
  let reloj;
  const despertar = () => { document.body.classList.remove('quieto'); clearTimeout(reloj); reloj = setTimeout(() => document.body.classList.add('quieto'), 2500); };
  ['pointermove', 'touchstart', 'focusin'].forEach((e) => addEventListener(e, despertar, { passive: true })); despertar();

  // ---------- globo de ayuda
  const tip = $('#tip');
  addEventListener('pointermove', (ev) => {
    const el = ev.target.closest?.('[data-tip]');
    tip.classList.toggle('on', !!el);
    if (!el) return;
    tip.textContent = el.dataset.tip;
    const r = tip.getBoundingClientRect();
    tip.style.left = Math.min(ev.clientX + 16, innerWidth - r.width - 12) + 'px';
    tip.style.top = Math.min(ev.clientY + 18, innerHeight - r.height - 12) + 'px';
  });

  // ---------- resaltar una criticidad en toda la diapositiva
  $$('.leyenda button').forEach((b) => {
    b.onclick = () => {
      const s = b.closest('.slide'), on = b.classList.contains('on');
      $$('.leyenda button', s).forEach((x) => x.classList.toggle('on', x === b && !on));
      s.classList.toggle('filtrando', !on);
      $$('[data-crit]', s).forEach((x) => x.classList.toggle('vis', x.dataset.crit === b.dataset.c));
    };
  });

  // ---------- boletín ampliado
  const luz = $('#luz');
  const cerrarLuz = () => luz.classList.remove('open');
  luz.onclick = cerrarLuz;
  $$('.bol').forEach((b) => {
    const ampliar = () => {
      const im = $('.img img', b);
      luz.replaceChildren();
      if (im) { const i = new Image(); i.src = im.src; i.alt = ''; luz.append(i); }
      const d = document.createElement('div'), h = document.createElement('h3'), p = document.createElement('p');
      h.textContent = $('h3', b).textContent; p.textContent = b.dataset.resumen; d.append(h, p); luz.append(d);
      luz.classList.toggle('solo', !im); luz.classList.add('open');
    };
    b.onclick = ampliar;
    b.onkeydown = (ev) => { if (ev.key === 'Enter') { ev.stopPropagation(); ampliar(); } };
  });

  // ---------- red animada de la portada y el cierre
  $$('canvas.red').forEach((cv) => {
    if (quieto) return;
    const s = cv.closest('.slide'), g = cv.getContext('2d');
    cv.width = 960; cv.height = 540;
    const P = Array.from({ length: 62 }, () => ({ x: Math.random() * 960, y: Math.random() * 540, a: (Math.random() - .5) * .35, b: (Math.random() - .5) * .35 }));
    const pinta = () => {
      requestAnimationFrame(pinta);
      if (!s.classList.contains('active') || document.hidden) return;
      g.clearRect(0, 0, 960, 540);
      P.forEach((p, i) => {
        p.x = (p.x + p.a + 960) % 960; p.y = (p.y + p.b + 540) % 540;
        for (let k = i + 1; k < P.length; k++) {
          const q = P[k], d = Math.hypot(p.x - q.x, p.y - q.y);
          if (d < 110) { g.strokeStyle = `rgba(255,60,105,${.22 * (1 - d / 110)})`; g.beginPath(); g.moveTo(p.x, p.y); g.lineTo(q.x, q.y); g.stroke(); }
        }
        g.fillStyle = 'rgba(255,255,255,.5)'; g.fillRect(p.x - .8, p.y - .8, 1.6, 1.6);
      });
    };
    pinta();
  });

  // ---------- mapa
  const SVG = 'http://www.w3.org/2000/svg';
  const nodo = (t, a, padre) => { const e = document.createElementNS(SVG, t); for (const k in a) e.setAttribute(k, a[k]); padre?.append(e); return e; };
  const ALTO_N = 0.135; // franja superior del mundo que no se muestra (Ártico)
  const merc = (lat) => { const r = lat * Math.PI / 180; return (1 - Math.asinh(Math.tan(r)) / Math.PI) / 2; };
  const NOM = { entrantes: 'Entrantes', salientes: 'Salientes' }, CL = { entrantes: 'e', salientes: 's2' };

  function teselas(m, W, H) {
    if (!D.mapa.base) return Promise.resolve();
    const z = 3, n = 2 ** z, t = W / n, y0 = Math.floor(ALTO_N * n), y1 = Math.min(n - 1, Math.floor((ALTO_N + H / W) * n));
    const pon = (url, capa) => {
      const ps = [];
      for (let y = y0; y <= y1; y++) for (let x = 0; x < n; x++) ps.push(new Promise((ok) => {
        const i = new Image(); i.alt = ''; i.referrerPolicy = 'no-referrer'; i.draggable = false;
        i.style.cssText = `left:${x * t}px;top:${y * t - ALTO_N * W}px;width:${t + 1.5}px;height:${t + 1.5}px`;
        i.onload = () => ok(1); i.onerror = () => { i.remove(); ok(0); };
        i.src = url.replace('{z}', z).replace('{y}', y).replace('{x}', x); capa.append(i);
      }));
      return Promise.all(ps);
    };
    const base = pon(D.mapa.base, $('.tes', m)).then((r) => {
      // Con huecos se vería mal: si no cargó completo queda la cuadrícula con las ubicaciones
      if (r.every(Boolean)) { m.classList.add('con-tes'); $('.credito', m).textContent = D.mapa.atribucion; }
      else $('.credito', m).textContent = 'Mapa de fondo no disponible sin conexión';
    });
    const lin = D.mapa.lineas ? pon(D.mapa.lineas, $('.lin', m)) : null;
    // El PDF no espera más de 8 s: sin salida a Internet se genera con las ubicaciones sobre la cuadrícula
    const limite = new Promise((ok) => setTimeout(() => {
      if (PDF && !m.classList.contains('con-tes')) { $$('.tes img, .lin img', m).forEach((i) => { i.removeAttribute('src'); i.remove(); }); $('.credito', m).textContent = 'Mapa de fondo no disponible sin conexión'; }
      ok();
    }, 8000));
    return Promise.race([Promise.all([base, lin]), limite]);
  }

  function mapa(m) {
    const W = m.clientWidth, H = m.clientHeight, capa = $('.capa', m), svg = $('svg', m), rk = $('.rk', m.closest('.slide'));
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
    const XY = (p) => [(p.lon + 180) / 360 * W, (merc(p.lat) - ALTO_N) * W];
    const [cx, cy] = XY(D.mapa.origen);
    let modo = m.dataset.modo, Z = 1, tx0 = 0, ty0 = 0;
    const aplicar = () => {
      tx0 = Math.min(0, Math.max(W * (1 - Z), tx0)); ty0 = Math.min(0, Math.max(H * (1 - Z), ty0));
      capa.style.transform = `translate(${tx0}px,${ty0}px) scale(${Z})`;
      $$('text', svg).forEach((t) => { t.style.fontSize = 15 / Z + 'px'; t.style.strokeWidth = 4 / Z + 'px'; });
      $$('[data-r]', svg).forEach((c) => c.setAttribute('r', c.dataset.r / Math.sqrt(Z)));
    };
    const zoom = (f, x = W / 2, y = H / 2) => { const z2 = Math.min(5, Math.max(1, Z * f)); tx0 = x - (x - tx0) * z2 / Z; ty0 = y - (y - ty0) * z2 / Z; Z = z2; aplicar(); };
    const foco = (pais) => {
      m.classList.toggle('foco', !!pais);
      $$('g.p', svg).forEach((g) => g.classList.toggle('on', g.dataset.pais === pais));
      $$('.it', rk).forEach((b) => b.classList.toggle('on', b.dataset.pais === pais));
    };
    const pintar = () => {
      svg.replaceChildren(); rk.replaceChildren(); m.classList.remove('foco');
      const modos = modo === 'ambos' ? ['entrantes', 'salientes'] : [modo];
      const cajas = [];
      modos.filter((q) => D.mapa[q].length).forEach((q) => {
        const todos = D.mapa[q], max = Math.max(...todos.map((p) => p.total)), suma = D.mapa.total[q];
        [...todos].reverse().forEach((p) => {
          const [x, y] = XY(p), f = Math.sqrt(p.total / max), dx = cx - x, dy = cy - y, L = Math.hypot(dx, dy) || 1;
          const lado = (q === 'entrantes' ? 1 : -1) * (dx < 0 ? 1 : -1), c = Math.min(.24 * L, 170) * lado;
          const mx = (x + cx) / 2 - dy / L * c, my = (y + cy) / 2 + dx / L * c;
          const d = q === 'entrantes' ? `M${x},${y}Q${mx},${my} ${cx},${cy}` : `M${cx},${cy}Q${mx},${my} ${x},${y}`;
          const g = nodo('g', { class: 'p ' + CL[q] }, svg);
          g.dataset.pais = p.pais; g.dataset.tip = `${p.pais} · ${q}\n${num(p.total)} eventos (${(p.total / suma * 100).toFixed(1).replace('.', ',')} % del top)`;
          nodo('path', { d, class: 'fondo' }, g);
          nodo('path', { d, class: 'flujo', 'stroke-width': (1.6 + 3.4 * f).toFixed(1) }, g);
          const r = (5 + 25 * f).toFixed(1);
          nodo('circle', { cx: x, cy: y, r, 'data-r': r, class: 'burb' }, g); nodo('circle', { cx: x, cy: y, r: 2.6, 'data-r': 2.6, class: 'nuc' }, g);
          g.onmouseenter = () => foco(p.pais); g.onmouseleave = () => foco(null);
        });
        const it = modo === 'ambos' ? 5 : 10;
        if (modo === 'ambos' || PDF) rk.insertAdjacentHTML('beforeend', `<div class="tt ${CL[q]}">${NOM[q]}</div>`);
        todos.slice(0, it).forEach((p, i) => {
          const b = document.createElement('button'); b.className = 'it ' + CL[q]; b.dataset.pais = p.pais;
          b.innerHTML = `<em>${i + 1}</em><span></span><b>${num(p.total)}</b><u><i style="--w:${Math.max(1.5, p.total / max * 100)}%"></i></u>`;
          $('span', b).textContent = p.pais;
          b.onmouseenter = b.onfocus = () => foco(p.pais); b.onmouseleave = b.onblur = () => foco(null);
          b.onclick = () => { const [x, y] = XY(p); Z = 2.6; tx0 = W / 2 - x * Z; ty0 = H / 2 - y * Z; aplicar(); };
          rk.append(b);
          // nombre en el mapa, si no se encima con otro
          const [x, y] = XY(p), w = p.pais.length * 9, caja = [x - w / 2, y - 14 - 30 * Math.sqrt(p.total / max), w, 18];
          if (!cajas.some((k) => Math.abs(k[0] + k[2] / 2 - (caja[0] + w / 2)) < (k[2] + w) / 2 + 4 && Math.abs(k[1] - caja[1]) < 32)) {
            cajas.push(caja);
            const g = $$('g.p', svg).find((k) => k.dataset.pais === p.pais && k.classList.contains(CL[q]));
            nodo('text', { x, y: caja[1] + 4, 'text-anchor': 'middle' }, g).textContent = p.pais;
          }
        });
      });
      nodo('circle', { cx, cy, r: 16, class: 'pulso' }, svg);
      nodo('circle', { cx, cy, r: 6, fill: '#3ddc97' }, svg);
      nodo('text', { x: cx, y: cy + 28, 'text-anchor': 'middle' }, svg).textContent = D.mapa.origen.pais;
      const sin = [...new Set(modos.flatMap((q) => D.mapa.sin[q]))];
      if (sin.length) { const s = document.createElement('div'); s.className = 'sinub'; s.textContent = 'Sin ubicación en el mapa: ' + sin.join(', '); rk.append(s); }
      $$('.tabs button', m.closest('.slide')).forEach((b) => b.classList.toggle('on', b.dataset.modo === modo));
      aplicar();
    };
    $$('.tabs button', m.closest('.slide')).forEach((b) => { b.onclick = () => { modo = b.dataset.modo; pintar(); }; });
    const [mas, menos, todo] = $$('.zoom button', m);
    mas.onclick = () => zoom(1.5); menos.onclick = () => zoom(1 / 1.5); todo.onclick = () => { Z = 1; tx0 = ty0 = 0; aplicar(); };
    m.addEventListener('wheel', (ev) => { ev.preventDefault(); const r = m.getBoundingClientRect(); zoom(ev.deltaY < 0 ? 1.25 : .8, (ev.clientX - r.left) / escala, (ev.clientY - r.top) / escala); }, { passive: false });
    let ar = null;
    m.addEventListener('pointerdown', (ev) => { if (ev.target.closest('button')) return; ar = [ev.clientX, ev.clientY, tx0, ty0]; m.classList.add('mov'); m.setPointerCapture(ev.pointerId); });
    m.addEventListener('pointermove', (ev) => { if (!ar) return; tx0 = ar[2] + (ev.clientX - ar[0]) / escala; ty0 = ar[3] + (ev.clientY - ar[1]) / escala; aplicar(); });
    ['pointerup', 'pointercancel'].forEach((t) => m.addEventListener(t, () => { ar = null; m.classList.remove('mov'); }));
    pintar();
    // Después de cargar la página: así un mapa que no responde no la retiene
    return new Promise((ok) => { if (document.readyState === 'complete') ok(); else addEventListener('load', ok, { once: true }); }).then(() => teselas(m, W, H));
  }

  // ---------- exportar a PDF (solo dentro de la plataforma)
  const bp = $('#b-pdf');
  if (bp) bp.onclick = async () => {
    bp.disabled = true;
    try {
      const r = await fetch(`/api/informes/${D.informe_id}/presentacion.pdf?estilo=${D.estilo}`, { headers: { Authorization: 'Bearer ' + localStorage.getItem('soc_token') } });
      if (!r.ok) throw new Error('Error ' + r.status);
      const u = URL.createObjectURL(await r.blob()), a = document.createElement('a');
      a.href = u; a.download = D.archivo; a.click(); setTimeout(() => URL.revokeObjectURL(u), 60000);
    } catch (err) { alert('No se pudo exportar: ' + err.message); }
    bp.disabled = false;
  };

  go(0);
  const mapas = Promise.all($$('.mapa').map(mapa)).catch(() => {});
  (document.fonts?.ready || Promise.resolve()).then(() => { ajustarTexto(); return mapas; }).then(() => setTimeout(() => { window.__listo = true; }, 300));
  window.focus();
})();
