/* Graphique d'intentions de vote du premier tour (et cotes Polymarket),
 * partagé par la home et les pages institut.
 *
 * Dépend de Chart.js 4 + chartjs-adapter-date-fns (+ locale fr), chargés avant.
 * La page déclare PAGES_CANDIDATS (Set des slugs ayant une fiche) et renseigne
 * CANDIDATS (contenu de candidats.json) avant d'appeler BlocChart.setCandidats.
 */
const NB_DEFAULT = 4;
const Y_MIN_MAX = 10;

let CANDIDATS = null;

// French number: 24,8\u00a0%
function fmtPct(v) {
  return v.toFixed(1).replace('.', ',') + '\u00a0%';
}

// "2026-09-03" → "03/09/2026"
function fmtDate(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
}

function parseDate(s) {
  const [y, m, d] = s.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function trackEvent(path) {
  window.goatcounter?.count({ path, event: true });
}

function couleur(cid) {
  const c = CANDIDATS[cid];
  return (c && c.couleur) ? c.couleur : '#888';
}

function nomCourt(cid) {
  const c = CANDIDATS[cid];
  return c ? c.nom : cid;
}

function computeYMax(datasets) {
  let max = 0;
  for (const ds of datasets) {
    if (ds._isGhost) continue;
    for (const p of ds.data) {
      if (p.y !== null && !isNaN(p.y) && p.y > max) max = p.y;
    }
  }
  return Math.max(Y_MIN_MAX, Math.ceil(max / 5) * 5);
}

// Chart.js global defaults
Chart.defaults.font.family = "'IBM Plex Sans', system-ui, sans-serif";
Chart.defaults.color = '#202632';
// Locale française pour l'adaptateur date-fns
if (window.dateFns && window.dateFns.locale && window.dateFns.locale.fr) {
  Chart.defaults.scales.time = Chart.defaults.scales.time || {};
  Chart.defaults.scales.time.adapters = { date: { locale: window.dateFns.locale.fr } };
}

const IS_TOUCH = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
const IS_MOBILE = window.innerWidth < 600;

// Config de l'axe X adaptée à la période et à l'écran
function xAxisConfig(dateDebut, dateFin) {
  const d0 = new Date(dateDebut), d1 = new Date(dateFin);
  const days = Math.round((d1 - d0) / 86400000);
  const unit = days > 120 ? 'month' : 'week';
  const displayFormats = {
    week: 'd MMM',
    month: 'MMM',
  };
  return {
    type: 'time',
    time: { unit, displayFormats, tooltipFormat: 'd MMMM yyyy' },
    adapters: { date: { locale: window.dateFns?.locale?.fr } },
    ticks: { maxRotation: 0, autoSkip: true, maxTicksLimit: IS_MOBILE ? 5 : 9,
      color: IS_MOBILE ? '#b0b5bc' : '#9aa2ac', font: { size: IS_MOBILE ? 10 : 11 } },
    grid: { color: IS_MOBILE ? '#f0f1ed' : '#edeee9' },
  };
}

// Tooltip touch-friendly : zone large, reste dans l'écran
Chart.defaults.plugins.tooltip.position = 'nearest';
Chart.defaults.plugins.tooltip.caretPadding = 8;
Chart.defaults.plugins.tooltip.padding = IS_TOUCH ? 10 : 6;
if (IS_TOUCH) {
  Chart.defaults.interaction.mode = 'nearest';
  Chart.defaults.interaction.axis = 'x';
  Chart.defaults.interaction.intersect = false;
  // Zone de détection large pour un doigt
  Chart.defaults.hover.mode = 'nearest';
  Chart.defaults.hover.axis = 'x';
  Chart.defaults.hover.intersect = false;
}

// Plugin global : fermer le tooltip au toucher en dehors du graphique
const touchDismissPlugin = {
  id: 'touchDismiss',
  beforeInit(chart) {
    if (!IS_TOUCH) return;
    const handler = (e) => {
      const rect = chart.canvas.getBoundingClientRect();
      const x = e.changedTouches[0].clientX;
      const y = e.changedTouches[0].clientY;
      if (x < rect.left || x > rect.right || y < rect.top || y > rect.bottom) {
        chart.tooltip.setActiveElements([], { x: 0, y: 0 });
        chart.update('none');
      }
    };
    document.addEventListener('touchstart', handler, { passive: true });
    chart._touchDismiss = handler;
  },
  destroy(chart) {
    if (chart._touchDismiss) {
      document.removeEventListener('touchstart', chart._touchDismiss);
    }
  }
};
Chart.register(touchDismissPlugin);

// Mode d'interaction des pages institut : comme 'nearest' sur l'axe X
// (intersect: false), mais en ignorant les courbes de fond (moyenne Sondax),
// dont les points quotidiens capteraient sinon le survol.
Chart.Interaction.modes.nearestHorsFond = function (chart, e, options, useFinal) {
  const pos = Chart.helpers.getRelativePosition(e, chart);
  const area = chart.chartArea;
  if (pos.x < area.left || pos.x > area.right || pos.y < area.top || pos.y > area.bottom) return [];
  let best = Infinity;
  let items = [];
  for (const meta of chart.getSortedVisibleDatasetMetas()) {
    if (meta._dataset._isFond) continue;
    meta.data.forEach((el, index) => {
      if (el.skip) return;
      const d = Math.abs(pos.x - el.getProps(['x'], useFinal).x);
      if (d < best) { best = d; items = []; }
      if (d === best) items.push({ element: el, datasetIndex: meta.index, index });
    });
  }
  return items;
};

// =========================================================================
// Generic bloc controller
// =========================================================================
class BlocChart {
  constructor({ canvasId, cbContainerId, periodeSelector = null, dateFin, dateDebut, nbDefault = NB_DEFAULT, periodeEventPrefix = null, fallbackEndDate = null, lienPrefix = '' }) {
    this.canvas = document.getElementById(canvasId);
    this.cbContainer = document.getElementById(cbContainerId);
    this.periodeEl = periodeSelector ? document.querySelector(periodeSelector) : null;
    this.lienPrefix = lienPrefix;
    this.dateFin = dateFin;
    this.dateDebut = dateDebut;
    this.nbDefault = nbDefault;
    this.periodeEventPrefix = periodeEventPrefix;
    this.fallbackEndDate = fallbackEndDate;
    this.chart = null;
    this.checked = new Set();
    this.candidats = {};
    // Pages institut : courbes = points bruts de l'institut (points visibles,
    // ruptures sans interpolation) ; `fond` = moyenne Sondax {cid: [{d, v}]}.
    this.courbesBrutes = false;
    this.fond = null;
    if (this.periodeEl) this.setupPeriode();
  }

  setCandidats(candidats, sortFn, visibleOrder, { showDelta = false, checked = null } = {}) {
    this.candidats = candidats;
    this.showDelta = showDelta;
    // visibleOrder: optional ordered list from latest sondage, used for display order
    this.sortedCids = visibleOrder || Object.keys(candidats).sort(sortFn);
    this.checked.clear();
    if (checked) {
      for (const cid of checked) this.checked.add(cid);
    } else {
      for (let i = 0; i < Math.min(this.nbDefault, this.sortedCids.length); i++) {
        this.checked.add(this.sortedCids[i]);
      }
    }
    this.renderCheckboxes();
    this.render();
  }

  lastVal(cid) {
    const pts = this.candidats[cid];
    if (!pts || pts.length === 0) return null;
    for (let i = pts.length - 1; i >= 0; i--) {
      if (pts[i].v !== null) return pts[i].v;
    }
    return null;
  }

  getDateDebut() {
    if (!this.periodeEl) return this.dateDebut;
    const active = this.periodeEl.querySelector('button.active');
    if (active) {
      if (active.dataset.all) return this.dateDebut;
      if (active.dataset.months) {
        const fin = new Date(this.dateFin);
        fin.setMonth(fin.getMonth() - parseInt(active.dataset.months));
        return fin.toISOString().slice(0, 10);
      }
    }
    const input = this.periodeEl.querySelector('.date-libre');
    if (input && input.value) return input.value;
    return this.dateDebut;
  }

  setupPeriode() {
    this.periodeEl.querySelectorAll('button').forEach(btn => {
      btn.addEventListener('click', () => {
        this.periodeEl.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const input = this.periodeEl.querySelector('.date-libre');
        if (input) input.value = '';
        if (this.periodeEventPrefix) {
          const label = btn.dataset.months ? btn.dataset.months + 'm'
            : btn.dataset.all ? 'tout' : 'autre';
          trackEvent(this.periodeEventPrefix + '/' + label);
        }
        this.render();
      });
    });
    const input = this.periodeEl.querySelector('.date-libre');
    if (input) {
      // Bornes calculées depuis les données (min = plus ancien, max = aujourd'hui)
      if (this.dateDebut) input.min = this.dateDebut;
      input.max = new Date().toISOString().slice(0, 10);
      if (this.dateDebut) input.placeholder = this.dateDebut;
      input.addEventListener('change', () => {
        this.periodeEl.querySelectorAll('button').forEach(b => b.classList.remove('active'));
        if (this.periodeEventPrefix) trackEvent(this.periodeEventPrefix + '/libre');
        this.render();
      });
    }
  }

  delta3m(cid) {
    const pts = this.candidats[cid];
    if (!pts || pts.length === 0) return null;
    let last = null, lastIdx = -1;
    for (let i = pts.length - 1; i >= 0; i--) {
      if (pts[i].v !== null) { last = pts[i]; lastIdx = i; break; }
    }
    if (!last) return null;
    const target = new Date(last.d);
    target.setDate(target.getDate() - 90);
    const targetISO = target.toISOString().slice(0, 10);
    let prev = null;
    for (let i = lastIdx; i >= 0; i--) {
      if (pts[i].d <= targetISO && pts[i].v !== null) { prev = pts[i]; break; }
    }
    if (!prev) return null;
    return Math.round((last.v - prev.v) * 10) / 10;
  }

  renderCheckboxes() {
    const VISIBLE = 8;
    this.cbContainer.innerHTML = '';

    if (this.showDelta) {
      const ncols = IS_MOBILE ? 2 : 4;
      for (let c = 0; c < ncols; c++) {
        const hdr = document.createElement('div');
        hdr.className = 'cb-col-header';
        hdr.innerHTML = '<span></span><span></span><span class="cb-avg-header"></span><span class="cb-delta-header" title="Variation de la moyenne pondérée sur trois mois, en points de pourcentage">sur 3\u00a0mois</span>';
        this.cbContainer.appendChild(hdr);
      }
    }

    let extraWrap = null;
    let btn = null;

    for (let idx = 0; idx < this.sortedCids.length; idx++) {
      const cid = this.sortedCids[idx];
      const col = couleur(cid);

      const label = document.createElement('label');
      label.className = 'candidat-cb' + (this.showDelta ? '' : ' no-delta');
      label.style.setProperty('--col', col);
      label.dataset.cid = cid;

      const cb = document.createElement('input');
      cb.type = 'checkbox';
      cb.checked = this.checked.has(cid);
      cb.addEventListener('change', () => {
        if (cb.checked) this.checked.add(cid);
        else this.checked.delete(cid);
        this.render();
      });

      const nameSpan = document.createElement('span');
      nameSpan.className = 'cb-name';
      const pageLink = PAGES_CANDIDATS.has(cid)
        ? ` <a href="${this.lienPrefix}${cid}.html" class="cb-page-link" title="Fiche ${nomCourt(cid)}" onclick="event.stopPropagation()">›</a>`
        : '';
      nameSpan.innerHTML = `<span class="pastille" style="background:${col}"></span> ${nomCourt(cid)}${pageLink}`;

      label.appendChild(cb);
      label.appendChild(nameSpan);

      if (this.showDelta) {
        const avg = this.lastVal(cid);
        const avgSpan = document.createElement('span');
        avgSpan.className = 'cb-avg';
        if (avg !== null) avgSpan.textContent = fmtPct(avg);
        label.appendChild(avgSpan);

        const d = this.delta3m(cid);
        const deltaSpan = document.createElement('span');
        deltaSpan.className = 'cb-delta';
        if (d !== null) {
          const sign = d > 0 ? '+' : '';
          deltaSpan.textContent = `${sign}${d.toFixed(1).replace('.', ',')}\u00a0pt`;
        }
        label.appendChild(deltaSpan);
      }

      // Survol / toucher : renforcer la courbe, atténuer les autres
      if (this.showDelta) {
        const highlight = () => this.highlightCurve(cid);
        const unhighlight = () => this.highlightCurve(null);
        label.addEventListener('mouseenter', highlight);
        label.addEventListener('mouseleave', unhighlight);
        if (IS_TOUCH) {
          label.addEventListener('touchstart', (e) => {
            if (e.target.tagName === 'INPUT' || e.target.tagName === 'A') return;
            highlight();
          }, { passive: true });
          label.addEventListener('touchend', unhighlight, { passive: true });
        }
      }

      if (idx < VISIBLE) {
        this.cbContainer.appendChild(label);
      } else {
        if (!extraWrap) {
          btn = document.createElement('button');
          btn.className = 'show-more';
          const remaining = this.sortedCids.length - VISIBLE;
          btn.textContent = `Voir tous les candidats (+${remaining})`;
          this.cbContainer.appendChild(btn);
          extraWrap = document.createElement('div');
          extraWrap.className = 'cb-extra collapsed';
          this.cbContainer.appendChild(extraWrap);
          btn.addEventListener('click', () => {
            const collapsed = extraWrap.classList.toggle('collapsed');
            btn.textContent = collapsed
              ? `Voir tous les candidats (+${remaining})`
              : 'Moins de candidats';
          });
        }
        extraWrap.appendChild(label);
      }
    }
  }

  highlightCurve(cid) {
    if (!this.chart) return;
    for (const ds of this.chart.data.datasets) {
      if (!ds._cid) continue;
      if (cid === null) {
        ds.borderWidth = ds._origBorderWidth || ds.borderWidth;
        ds.borderColor = ds._origBorderColor || ds.borderColor;
        if (ds._isBrut) {
          ds.backgroundColor = ds._origBgColor || ds.backgroundColor;
          ds.borderColor = ds._origBorderColor || ds.borderColor;
        }
      } else if (ds._cid === cid) {
        ds.borderWidth = ds._isGhost ? 1 : (IS_MOBILE ? 4 : 3.5);
        ds.borderColor = ds._origBorderColor || ds.borderColor;
        if (ds._isBrut) {
          ds.backgroundColor = ds._origBgColor || ds.backgroundColor;
        }
      } else {
        const orig = ds._origBorderColor || ds.borderColor;
        ds.borderColor = ds._isGhost ? '#eee' : (orig.startsWith('#') ? orig + '25' : orig);
        ds.borderWidth = ds._isGhost ? 1 : (ds._origBorderWidth || ds.borderWidth);
        if (ds._isBrut) {
          ds.backgroundColor = (ds._origBgColor || ds.backgroundColor).startsWith('#')
            ? (ds._origBgColor || ds.backgroundColor) + '15' : ds.backgroundColor;
        }
      }
    }
    this.chart.update('none');
  }

  buildGhostSegments(cid, dateDebut) {
    const raw = this.candidats[cid].filter(p => p.d >= dateDebut);
    const segments = [];
    let lastNonNull = null;
    let inGap = false;
    for (const p of raw) {
      if (p.v !== null) {
        if (inGap && lastNonNull !== null) {
          segments.push([
            { x: parseDate(lastNonNull.d), y: lastNonNull.v },
            { x: parseDate(p.d), y: p.v },
          ]);
        }
        lastNonNull = p;
        inGap = false;
      } else {
        inGap = true;
      }
    }
    return segments;
  }

  render() {
    const dateDebut = this.getDateDebut();
    const datasets = [];
    const CURVE_WIDTH = IS_MOBILE ? 2.8 : 2.5;
    const PT_RADIUS = IS_MOBILE ? 1.2 : 1.8;
    const PT_ALPHA = IS_MOBILE ? '50' : '70';

    for (const cid of this.sortedCids) {
      if (!this.checked.has(cid)) continue;
      const col = couleur(cid);

      const brut = this.courbesBrutes;
      const data = this.candidats[cid]
        .filter(p => p.d >= dateDebut)
        .map(p => brut
          ? { x: parseDate(p.d), y: p.v, institut: p.institut, terrain_debut: p.terrain_debut,
              terrain_fin: p.terrain_fin, echantillon: p.echantillon }
          : { x: parseDate(p.d), y: p.v, n: p.n, ref: p.ref });

      const fallbackEnd = this.fallbackEndDate ? parseDate(this.fallbackEndDate) : null;
      const colFaded = col.startsWith('#')
        ? col + '55'
        : col.replace('rgb(', 'rgba(').replace(')', ', 0.33)');

      datasets.push({
        label: nomCourt(cid),
        data: data,
        borderColor: col,
        _origBorderColor: col,
        backgroundColor: brut ? col : undefined,
        borderWidth: CURVE_WIDTH,
        _origBorderWidth: CURVE_WIDTH,
        borderDash: CANDIDATS[cid]?.type === 'parti' ? [6, 4] : undefined,
        pointRadius: brut ? (IS_MOBILE ? 2.5 : 3) : 0,
        pointHoverRadius: brut ? 5 : undefined,
        tension: 0,
        fill: false,
        spanGaps: false,
        _cid: cid,
        segment: {
          borderDash: ctx => {
            const n0 = ctx.p0?.raw?.n;
            const n1 = ctx.p1?.raw?.n;
            if ((n0 !== undefined && n0 <= 1) || (n1 !== undefined && n1 <= 1)) return [6, 4];
            return undefined;
          },
          borderColor: ctx => {
            if (!fallbackEnd) return undefined;
            const x0 = ctx.p0?.parsed?.x;
            const x1 = ctx.p1?.parsed?.x;
            if (x0 < fallbackEnd || x1 < fallbackEnd) return colFaded;
            return undefined;
          },
        },
      });

      if (this.fond && this.fond[cid]) {
        datasets.push({
          label: '',
          data: this.fond[cid]
            .filter(p => p.d >= dateDebut && p.d <= this.dateFin)
            .map(p => ({ x: parseDate(p.d), y: p.v })),
          borderColor: col + '40',
          _origBorderColor: col + '40',
          borderWidth: 1,
          _origBorderWidth: 1,
          pointRadius: 0,
          pointHoverRadius: 0,
          tension: 0,
          fill: false,
          spanGaps: false,
          order: 1,
          _cid: cid,
          _isFond: true,
        });
      }

      const ghosts = brut ? [] : this.buildGhostSegments(cid, dateDebut);
      for (const seg of ghosts) {
        datasets.push({
          label: '',
          data: seg,
          borderColor: '#ccc',
          _origBorderColor: '#ccc',
          borderWidth: 1,
          _origBorderWidth: 1,
          borderDash: [4, 4],
          pointRadius: 0,
          tension: 0,
          fill: false,
          _cid: cid,
          _isGhost: true,
        });
      }

      if (this.pointsBruts && this.pointsBruts[cid]) {
        const bruts = this.pointsBruts[cid]
          .filter(p => p.d >= dateDebut)
          .map(p => ({
            x: parseDate(p.d), y: p.v,
            institut: p.institut, terrain_debut: p.terrain_debut,
            terrain_fin: p.terrain_fin, echantillon: p.echantillon,
          }));
        if (bruts.length > 0) {
          datasets.push({
            label: '',
            data: bruts,
            borderColor: col + PT_ALPHA,
            _origBorderColor: col + PT_ALPHA,
            backgroundColor: col + PT_ALPHA,
            _origBgColor: col + PT_ALPHA,
            borderWidth: 0,
            _origBorderWidth: 0,
            pointRadius: PT_RADIUS,
            pointHoverRadius: 4,
            showLine: false,
            _cid: cid,
            _isBrut: true,
          });
        }
      }
    }

    const yMax = computeYMax(datasets);

    // Marge droite : au moins la largeur de la plus longue étiquette de fin
    // de courbe, pour qu'aucune ne soit coupée (mobile compris).
    const LABEL_FONT = `500 ${IS_MOBILE ? 10 : 11}px 'IBM Plex Sans', system-ui, sans-serif`;
    let labelsWidth = 0;
    if (this.enableEndLabels) {
      const mctx = document.createElement('canvas').getContext('2d');
      mctx.font = LABEL_FONT;
      for (const ds of datasets) {
        if (ds._isGhost || ds._isBrut || ds._isFond || !ds._cid) continue;
        const last = [...ds.data].reverse().find(p => p.y !== null && !isNaN(p.y));
        if (last) labelsWidth = Math.max(labelsWidth, mctx.measureText(`${nomCourt(ds._cid)} ${fmtPct(last.y)}`).width);
      }
    }

    if (this.chart) this.chart.destroy();

    const fallbackEndDate = this.fallbackEndDate;
    const getDateDebut = () => this.getDateDebut();
    const fallbackBandPlugin = fallbackEndDate ? {
      id: 'fallbackBand',
      beforeDraw: (chart) => {
        const xScale = chart.scales.x;
        const yScale = chart.scales.y;
        const endPx = xScale.getPixelForValue(parseDate(fallbackEndDate));
        if (endPx <= xScale.left) return;
        const ctx = chart.ctx;
        ctx.save();
        ctx.fillStyle = 'rgba(0, 0, 0, 0.03)';
        const left = Math.max(xScale.left, xScale.getPixelForValue(parseDate(getDateDebut())));
        ctx.fillRect(left, yScale.top, Math.min(endPx, xScale.right) - left, yScale.bottom - yScale.top);
        ctx.restore();
      },
      afterInit: (chart) => {
        const canvas = chart.canvas;
        canvas.addEventListener('mousemove', (e) => {
          const xScale = chart.scales.x;
          const rect = canvas.getBoundingClientRect();
          const x = e.clientX - rect.left;
          const endPx = xScale.getPixelForValue(parseDate(fallbackEndDate));
          if (x >= xScale.left && x <= endPx) {
            canvas.title = 'Avant fin mai 2026 : configurations hétérogènes, niveaux non strictement comparables — voir Méthodologie';
          } else if (canvas.title) {
            canvas.title = '';
          }
        });
      }
    } : null;

    // Plugin : labels de fin de courbe (nom + moyenne)
    const endLabelsPlugin = this.enableEndLabels ? {
      id: 'endLabels',
      afterDraw: (chart) => {
        const ctx = chart.ctx;
        const chartArea = chart.chartArea;
        const labels = [];
        const dsIndexMap = new Map();
        chart.data.datasets.forEach((ds, i) => dsIndexMap.set(ds, i));

        for (const ds of chart.data.datasets) {
          if (ds._isGhost || ds._isBrut || ds._isFond || !ds._cid) continue;
          let lastPt = null, lastIdx = -1;
          for (let i = ds.data.length - 1; i >= 0; i--) {
            if (ds.data[i].y !== null && !isNaN(ds.data[i].y)) {
              lastPt = ds.data[i]; lastIdx = i; break;
            }
          }
          if (!lastPt) continue;
          const meta = chart.getDatasetMeta(dsIndexMap.get(ds));
          const ptMeta = meta.data[lastIdx];
          if (!ptMeta) continue;
          const atEnd = (chartArea.right - ptMeta.x) < 40;
          labels.push({
            cid: ds._cid,
            text: `${nomCourt(ds._cid)} ${fmtPct(lastPt.y)}`,
            x: ptMeta.x,
            y: ptMeta.y,
            targetY: ptMeta.y,
            color: ds._origBorderColor || ds.borderColor,
            atEnd,
          });
        }
        if (labels.length === 0) return;

        labels.sort((a, b) => a.y - b.y);
        const GAP = IS_MOBILE ? 12 : 14;
        for (let i = 1; i < labels.length; i++) {
          if (labels[i].targetY - labels[i - 1].targetY < GAP) {
            labels[i].targetY = labels[i - 1].targetY + GAP;
          }
        }
        // Recentrer si le groupe dépasse le bas du graphe
        const lastLabel = labels[labels.length - 1];
        if (lastLabel.targetY > chartArea.bottom - 4) {
          const shift = lastLabel.targetY - (chartArea.bottom - 4);
          for (const l of labels) l.targetY -= shift;
        }

        ctx.save();
        ctx.font = LABEL_FONT;
        ctx.textBaseline = 'middle';

        for (const lb of labels) {
          const labelX = lb.atEnd ? chartArea.right + 6 : lb.x + 8;
          if (Math.abs(lb.targetY - lb.y) > 3) {
            ctx.strokeStyle = lb.color + '60';
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.moveTo(lb.atEnd ? chartArea.right : lb.x + 3, lb.y);
            ctx.lineTo(labelX - 3, lb.targetY);
            ctx.stroke();
          }
          ctx.textAlign = 'left';
          if (!lb.atEnd) {
            // Étiquette dans la zone de tracé : détourage blanc, lisible sur les courbes
            ctx.strokeStyle = '#fff';
            ctx.lineWidth = 3;
            ctx.lineJoin = 'round';
            ctx.strokeText(lb.text, labelX, lb.targetY);
          }
          ctx.fillStyle = lb.color;
          ctx.fillText(lb.text, labelX, lb.targetY);
        }
        ctx.restore();
      }
    } : null;

    const plugins = [];
    if (fallbackBandPlugin) plugins.push(fallbackBandPlugin);
    if (endLabelsPlugin) plugins.push(endLabelsPlugin);

    const interaction = {
      mode: this.fond ? 'nearestHorsFond' : 'nearest', axis: 'x', intersect: false,
    };

    this.chart = new Chart(this.canvas, {
      type: 'line',
      data: { datasets },
      plugins,
      options: {
        responsive: true,
        maintainAspectRatio: false,
        layout: this.enableEndLabels
          ? { padding: { right: Math.max(IS_MOBILE ? 90 : 115, Math.ceil(labelsWidth) + 10) } } : {},
        interaction: interaction,
        hover: interaction,
        scales: {
          x: xAxisConfig(dateDebut, this.dateFin),
          y: {
            min: 0,
            max: yMax,
            ticks: { callback: (v) => v + '\u00a0%',
              color: IS_MOBILE ? '#b0b5bc' : '#9aa2ac', font: { size: IS_MOBILE ? 10 : 11 } },
            grid: { color: IS_MOBILE ? '#f0f1ed' : '#edeee9' },
          },
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            ...interaction,
            filter: (item, _idx, arr) => {
              if (item.dataset._isGhost || item.dataset._isFond) return false;
              const hasBrut = arr.some(a => a.dataset._isBrut);
              if (hasBrut) return item.dataset._isBrut;
              return true;
            },
            callbacks: {
              title: (items) => {
                if (!items.length) return '';
                const first = items[0];
                if (first.dataset._isBrut || first.raw.institut) {
                  const raw = first.raw;
                  const terrain = raw.terrain_debut === raw.terrain_fin
                    ? raw.terrain_fin
                    : `${raw.terrain_debut} → ${raw.terrain_fin}`;
                  const ech = raw.echantillon ? ` · n\u00a0=\u00a0${raw.echantillon}` : '';
                  return `${raw.institut} — ${terrain}${ech}`;
                }
                const d = new Date(first.parsed.x);
                const opts = { day: 'numeric', month: 'long', year: 'numeric' };
                return 'Moyenne au ' + d.toLocaleDateString('fr-FR', opts);
              },
              label: (ctx) => {
                if (ctx.parsed.y === null || isNaN(ctx.parsed.y)) return '';
                return `${nomCourt(ctx.dataset._cid)} : ${fmtPct(ctx.parsed.y)}`;
              }
            }
          }
        },
      }
    });
  }
}
