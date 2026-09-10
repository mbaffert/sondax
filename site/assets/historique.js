/* Précédentes élections — script partagé par les 5 pages presidentielle-XXXX.html */

const TOUR1_2027 = new Date(2027, 3, 18);
const IS_MOBILE = window.innerWidth < 600;
const LABEL_PAD_TOP = 24;

const MOIS_COURT = ['janv.','févr.','mars','avr.','mai','juin',
                    'juil.','août','sept.','oct.','nov.','déc.'];

function fmtPct(v)  { return v.toFixed(1).replace('.', ',') + '\u00a0%'; }
function fmtPct2(v) { return v.toFixed(2).replace('.', ',') + '\u00a0%'; }
function fmtDate(iso) { const [y,m,d] = iso.split('-'); return `${d}/${m}/${y}`; }
function trackEvent(path) { window.goatcounter?.count({ path, event: true }); }

function joursAvant2027() {
  // Réutilise la valeur du countdown si elle a été calculée (même chiffre partout)
  if (window._joursAvantT1_2027 != null) return window._joursAvantT1_2027;
  const p = new Date().toLocaleDateString('en-CA', {timeZone: 'Europe/Paris'});
  const today = new Date(p + 'T00:00:00');
  return Math.round((new Date(2027,3,18) - today) / 86400000);
}

// --- Jour ↔ date ---
let T1_DATE = null;
function jourToDate(j) { const d = new Date(T1_DATE); d.setDate(d.getDate()+j); return d; }
function dateToJour(d) { return Math.round((d - T1_DATE) / 86400000); }

function monthTicks(minJ, maxJ, step) {
  const ticks = [];
  const start = jourToDate(minJ);
  let y = start.getFullYear(), m = start.getMonth();
  if (start.getDate() > 1) { m++; if (m>11){m=0;y++;} }
  if (step > 1) { m = Math.ceil(m/step)*step; if (m>11){m-=12;y++;} }
  while (true) {
    const d = new Date(y,m,1), j = dateToJour(d);
    if (j > maxJ) break;
    if (j >= minJ) ticks.push({value:j, date:d});
    m += step; if (m>11){m-=12;y++;}
  }
  return ticks;
}

function fmtTickLabel(date, isFirst) {
  const m = date.getMonth(), y = date.getFullYear();
  return (isFirst || m === 0) ? `${MOIS_COURT[m]} ${y}` : MOIS_COURT[m];
}

function fmtTooltipDate(j) {
  const d = jourToDate(j);
  return `${d.getDate()} ${MOIS_COURT[d.getMonth()]} ${d.getFullYear()} (J${j >= 0 ? '+' : ''}${j})`;
}

// Draw a label inside the chart; flip to left of line if it would overflow right
function drawLabel(ctx, text, xPx, yPx, right) {
  ctx.font = "11px 'IBM Plex Sans', sans-serif";
  const w = ctx.measureText(text).width;
  if (xPx + 4 + w > right) {
    ctx.textAlign = 'right';
    ctx.fillText(text, xPx - 4, yPx);
  } else {
    ctx.textAlign = 'left';
    ctx.fillText(text, xPx + 4, yPx);
  }
}

// Shared plugin factory for vertical markers
function vertLinesPlugin(id, jAuj) {
  return {
    id,
    afterDraw(chart) {
      const { ctx, chartArea: { top, bottom, left, right }, scales: { x: xScale } } = chart;
      ctx.save();
      ctx.textBaseline = 'top';

      // 1er tour (J0)
      const xJ0 = xScale.getPixelForValue(0);
      if (xJ0 >= left && xJ0 <= right) {
        ctx.strokeStyle = 'rgba(32,38,50,0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([6,4]);
        ctx.beginPath(); ctx.moveTo(xJ0, top); ctx.lineTo(xJ0, bottom); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(32,38,50,0.5)';
        drawLabel(ctx, '1er tour', xJ0, top + 4, right);
      }

      // Aujourd'hui pour 2027
      const xAuj = xScale.getPixelForValue(jAuj);
      if (xAuj >= left && xAuj <= right) {
        ctx.strokeStyle = 'rgba(12,108,242,0.35)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4,4]);
        ctx.beginPath(); ctx.moveTo(xAuj, top); ctx.lineTo(xAuj, bottom); ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = 'rgba(12,108,242,0.6)';
        drawLabel(ctx, `Aujourd\u2019hui pour 2027 (J-${joursAvant2027()})`, xAuj, top + 18, right);
      }

      ctx.restore();
    }
  };
}

// --- Données ---
let DATA = null, ELECTION = null, ANNEE = null;

async function loadData(annee) {
  ANNEE = annee;
  const resp = await fetch('data/derived/historique.json');
  DATA = await resp.json();
  ELECTION = DATA[annee];
  if (!ELECTION) throw new Error(`Pas de données pour ${annee}`);
  T1_DATE = new Date(ELECTION.tour1); T1_DATE.setHours(0,0,0,0);
}

// --- Premier tour ---
let chartT1 = null;
let checkedT1 = new Set();

function borneJour() {
  return Math.round((new Date(ELECTION.borne) - new Date(ELECTION.tour1)) / 86400000);
}
function periodeMinJour() {
  const active = document.querySelector('#periode-group button.active');
  if (!active) return borneJour();
  const months = parseInt(active.dataset.months);
  return months === 0 ? borneJour() : -Math.round(months * 30.44);
}
function tickStep() {
  const active = document.querySelector('#periode-group button.active');
  if (!active) return 2;
  const m = parseInt(active.dataset.months);
  return (m === 3 || m === 6) ? 1 : 2;
}

function decodeSerie(v, j0) {
  return v.split(',').map((s, i) => ({jour: j0+i, val: s==='' ? null : parseInt(s)/10}));
}

function buildGhostSegments(points, minJ) {
  const filtered = points.filter(p => p.jour >= minJ);
  const segs = [];
  let last = null, inGap = false;
  for (const p of filtered) {
    if (p.val !== null) {
      if (inGap && last) segs.push([{x:last.jour,y:last.val},{x:p.jour,y:p.val}]);
      last = p; inGap = false;
    } else { inGap = true; }
  }
  return segs;
}

function xAxisConfig(minJ, maxJ) {
  const ticks = monthTicks(minJ, maxJ, tickStep());
  return {
    type: 'linear', min: minJ, max: maxJ,
    afterBuildTicks(axis) { axis.ticks = ticks.map(t => ({value: t.value})); },
    ticks: {
      callback(value, index) {
        const t = ticks.find(t => t.value === value);
        return t ? fmtTickLabel(t.date, index === 0) : '';
      },
      maxRotation: 0, autoSkip: false,
    },
    grid: { color: '#edeee9' },
  };
}

function renderT1() {
  const cands = ELECTION.candidats;
  const minJ = periodeMinJour(), maxJ = 4;
  const datasets = [];
  const jAuj = -joursAvant2027();

  for (const [cid, info] of Object.entries(cands)) {
    if (!checkedT1.has(cid)) continue;
    const serie = decodeSerie(info.v, info.j0);
    datasets.push({
      label: info.nom,
      data: serie.filter(p => p.jour >= minJ).map(p => ({x:p.jour, y:p.val})),
      borderColor: info.couleur, borderWidth: 2, pointRadius: 0,
      tension: 0, fill: false, spanGaps: false, _cid: cid,
    });
    for (const seg of buildGhostSegments(serie, minJ)) {
      datasets.push({label:'', data:seg, borderColor:'#ccc', borderWidth:1,
        borderDash:[4,4], pointRadius:0, tension:0, fill:false, _isGhost:true});
    }
    const rawPts = info.pts.filter(([j])=>j>=minJ).map(([j,v])=>({x:j, y:v/10}));
    if (rawPts.length > 0) {
      datasets.push({label:'', data:rawPts, borderColor:'transparent',
        backgroundColor:info.couleur+'60', pointRadius:2.5, pointStyle:'circle',
        showLine:false, _isRaw:true});
    }
    if (info.resultat != null) {
      datasets.push({label:'', data:[{x:0,y:info.resultat}], borderColor:info.couleur,
        backgroundColor:info.couleur, pointRadius:6, pointStyle:'rectRot',
        showLine:false, _isResult:true});
    }
  }

  let yMax = 10;
  for (const ds of datasets) {
    for (const p of ds.data) {
      if (p.y !== null && !isNaN(p.y) && p.y > yMax) yMax = p.y;
    }
  }
  yMax = Math.max(10, Math.ceil(yMax / 5) * 5);

  if (chartT1) chartT1.destroy();
  chartT1 = new Chart(document.getElementById('chart-t1'), {
    type: 'line',
    data: { datasets },
    plugins: [vertLinesPlugin('vl-t1', jAuj)],
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: LABEL_PAD_TOP } },
      interaction: { mode:'nearest', axis:'x', intersect:false },
      scales: {
        x: xAxisConfig(minJ, maxJ),
        y: { min:0, max:yMax, ticks:{callback:v=>v+'\u00a0%'}, grid:{color:'#edeee9'} },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: item => !item.dataset._isGhost && !item.dataset._isRaw && !item.dataset._isResult,
          callbacks: {
            title: items => items.length ? fmtTooltipDate(items[0].parsed.x) : '',
            label: ctx => `${ctx.dataset.label}\u00a0: ${fmtPct(ctx.parsed.y)}`,
          },
        },
      },
    },
  });
}

function renderCheckboxesT1() {
  const container = document.getElementById('candidats-t1');
  container.innerHTML = '';
  const sorted = Object.entries(ELECTION.candidats);
  let extraWrap = null, btn = null;

  for (const [cid, info] of sorted) {
    const label = document.createElement('label');
    label.className = 'cand' + (checkedT1.has(cid) ? '' : ' masque');
    const cb = document.createElement('input');
    cb.type = 'checkbox'; cb.checked = checkedT1.has(cid);
    cb.style.accentColor = info.couleur;
    cb.addEventListener('change', () => {
      if (cb.checked) checkedT1.add(cid); else checkedT1.delete(cid);
      label.classList.toggle('masque', !cb.checked); renderT1();
    });
    const pastille = document.createElement('span');
    pastille.className = 'pastille'; pastille.style.background = info.couleur;
    const nom = document.createElement('span');
    nom.className = 'nom'; nom.textContent = info.nom;
    const res = document.createElement('span');
    res.className = 'res';
    res.textContent = info.resultat != null ? fmtPct2(info.resultat) : '';
    label.append(cb, pastille, nom, res);

    if (info.visible) {
      container.appendChild(label);
    } else {
      if (!extraWrap) {
        btn = document.createElement('button'); btn.className = 'plus';
        const remaining = sorted.filter(([,v])=>!v.visible).length;
        btn.textContent = `Voir tous les candidats (+${remaining})`;
        container.appendChild(btn);
        extraWrap = document.createElement('div');
        extraWrap.className = 'extra collapsed';
        container.appendChild(extraWrap);
        btn.addEventListener('click', () => {
          const c = extraWrap.classList.toggle('collapsed');
          btn.textContent = c ? `Voir tous les candidats (+${remaining})` : 'Moins de candidats';
        });
      }
      extraWrap.appendChild(label);
    }
  }
}

// --- Second tour ---
let chartT2 = null;

function getAllDuels() { return ELECTION.duels || {}; }

function duelCandidates() {
  const duels = getAllDuels(), count = {};
  for (const [key, d] of Object.entries(duels)) {
    const mesures = d.mesures || d;
    for (const cid of key.split('|')) count[cid] = (count[cid]||0) + mesures.length;
  }
  return Object.keys(count).sort((a,b) => count[b] - count[a]);
}

function candNom(cid)    { const c = ELECTION.candidats[cid]; return c ? c.nom : cid; }
function candCouleur(cid){ const c = ELECTION.candidats[cid]; return c ? c.couleur : '#888'; }

function populateDuelSelects() {
  const allCands = duelCandidates();
  const sel1 = document.getElementById('duel-cand1');
  const sel2 = document.getElementById('duel-cand2');
  sel1.innerHTML = '';
  for (const cid of allCands) {
    const o = document.createElement('option'); o.value = cid; o.textContent = candNom(cid);
    sel1.appendChild(o);
  }
  if (ELECTION.duel_final) sel1.value = ELECTION.duel_final.split('|')[0];
  populateDuelCand2();
  sel1.addEventListener('change', () => { populateDuelCand2(); renderT2(); });
  sel2.addEventListener('change', () => renderT2());
}

function populateDuelCand2() {
  const sel1 = document.getElementById('duel-cand1');
  const sel2 = document.getElementById('duel-cand2');
  const cid1 = sel1.value, prev = sel2.value;
  sel2.innerHTML = '';
  const duels = getAllDuels(), opponents = [];
  for (const [key, d] of Object.entries(duels)) {
    const pair = key.split('|'), mesures = d.mesures || d;
    if (!pair.includes(cid1)) continue;
    opponents.push({cid: pair[0]===cid1?pair[1]:pair[0], n:mesures.length});
  }
  opponents.sort((a,b)=>b.n-a.n);
  for (const {cid,n} of opponents) {
    const o = document.createElement('option'); o.value = cid;
    o.textContent = `${candNom(cid)} (${n} sondage${n>1?'s':''})`;
    if (cid===prev) o.selected = true;
    sel2.appendChild(o);
  }
  if (ELECTION.duel_final && !prev) {
    const pair = ELECTION.duel_final.split('|');
    sel2.value = pair[0]===cid1 ? pair[1] : pair[0];
  }
}

function getDuelKey() {
  const a = document.getElementById('duel-cand1').value;
  const b = document.getElementById('duel-cand2').value;
  return (a && b) ? [a,b].sort().join('|') : null;
}

function renderT2() {
  const key = getDuelKey();
  const content = document.getElementById('t2-content');
  const duels = getAllDuels();
  const empty = '<p style="color:var(--gris);font-size:0.85em;">Aucune mesure pour ce duel.</p>';
  if (!key || !duels[key]) {
    content.innerHTML = empty;
    if (chartT2) { chartT2.destroy(); chartT2 = null; }
    return;
  }
  const duel = duels[key];
  const mesures = (duel.mesures || duel);
  const minJ = periodeMinJour();
  const filtered = mesures.filter(m => m.jour >= minJ);
  if (!filtered.length) {
    content.innerHTML = '<p style="color:var(--gris);font-size:0.85em;">Aucune mesure pour cette période.</p>';
    if (chartT2) { chartT2.destroy(); chartT2 = null; }
    return;
  }
  const cidA = document.getElementById('duel-cand1').value;
  const cidB = document.getElementById('duel-cand2').value;

  if (filtered.length < 5) {
    renderT2Table(filtered, cidA, cidB, content);
  } else {
    renderT2Chart(duel, filtered, cidA, cidB, content, key);
  }
}

function renderT2Table(mesures, cidA, cidB, content) {
  if (chartT2) { chartT2.destroy(); chartT2 = null; }
  const sorted = mesures.slice().sort((a,b)=>b.jour-a.jour);
  let html = `<table class="t2-table"><tr><th>Institut</th><th>Date</th><th>${candNom(cidA)}</th><th>${candNom(cidB)}</th></tr>`;
  for (const m of sorted)
    html += `<tr><td>${m.institut}</td><td>${fmtDate(m.terrain_fin)}</td><td>${fmtPct(m.scores[cidA])}</td><td>${fmtPct(m.scores[cidB])}</td></tr>`;
  html += '</table>';
  content.innerHTML = html;
}

function renderT2Chart(duel, mesures, cidA, cidB, content, key) {
  const pair = key.split('|');
  const resT2 = ELECTION.resultats_t2 || {};
  const t2Jour = Math.round((new Date(ELECTION.tour2) - new Date(ELECTION.tour1)) / 86400000);
  const minJ = periodeMinJour(), maxJ = t2Jour + 4;
  const jAuj = -joursAvant2027();

  const datasets = [];

  // Moving average lines (from precomputed series)
  for (const cid of [cidA, cidB]) {
    const serieKey = `serie_${cid}`;
    if (duel[serieKey] && duel.series_j0 != null) {
      const decoded = decodeSerie(duel[serieKey], duel.series_j0);
      const data = decoded.filter(p => p.jour >= minJ && p.val !== null).map(p => ({x:p.jour, y:p.val}));
      datasets.push({
        label: candNom(cid), data,
        borderColor: candCouleur(cid), borderWidth: 2, pointRadius: 0,
        tension: 0, fill: false, spanGaps: false,
      });
      // Ghost segments for gaps
      for (const seg of buildGhostSegments(decoded, minJ)) {
        datasets.push({label:'', data:seg, borderColor:'#ccc', borderWidth:1,
          borderDash:[4,4], pointRadius:0, tension:0, fill:false, _isGhost:true});
      }
    }
  }

  // Raw points (semi-transparent)
  for (const cid of [cidA, cidB]) {
    const pts = mesures.map(m => ({x:m.jour, y:m.scores[cid]}));
    datasets.push({label:'', data:pts, borderColor:'transparent',
      backgroundColor: candCouleur(cid)+'60', pointRadius:2.5, pointStyle:'circle',
      showLine:false, _isRaw:true});
  }

  // Result diamonds
  for (const cid of [cidA, cidB]) {
    if (resT2[cid] != null) {
      datasets.push({label:'', data:[{x:t2Jour, y:resT2[cid]}],
        borderColor:candCouleur(cid), backgroundColor:candCouleur(cid),
        pointRadius:6, pointStyle:'rectRot', showLine:false, _isResult:true});
    }
  }

  // Y bounds: include all data points and results, keep 50 %
  const allVals = [];
  for (const ds of datasets) for (const p of ds.data) if (p.y!=null) allVals.push(p.y);
  allVals.push(50);
  const yMin = Math.min(Math.floor(Math.min(...allVals) / 5) * 5, 45);
  const yMax = Math.max(Math.ceil(Math.max(...allVals) / 5) * 5, 55);

  // 50 % line plugin
  const ligne50 = {
    id: 'ligne50t2',
    afterDraw(chart) {
      const { ctx, chartArea: { left, right } } = chart;
      const y = chart.scales.y.getPixelForValue(50);
      ctx.save();
      ctx.strokeStyle = 'rgba(32,38,50,0.25)'; ctx.lineWidth = 1;
      ctx.setLineDash([6,4]);
      ctx.beginPath(); ctx.moveTo(left, y); ctx.lineTo(right, y); ctx.stroke();
      ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(32,38,50,0.4)';
      ctx.font = "11px 'IBM Plex Sans', sans-serif";
      ctx.textBaseline = 'bottom';
      ctx.fillText('50\u00a0%', left + 4, y - 3);
      ctx.restore();
    }
  };

  content.innerHTML = '<div class="chart-wrap"><canvas id="chart-t2"></canvas></div>' +
    '<div class="candidats t2-legend" id="t2-legend"></div>';

  if (chartT2) chartT2.destroy();
  chartT2 = new Chart(document.getElementById('chart-t2'), {
    type: 'line',
    data: { datasets },
    plugins: [ligne50, vertLinesPlugin('vl-t2', jAuj)],
    options: {
      responsive: true, maintainAspectRatio: false,
      layout: { padding: { top: LABEL_PAD_TOP } },
      interaction: { mode:'nearest', axis:'x', intersect:false },
      scales: {
        x: xAxisConfig(minJ, maxJ),
        y: { min:yMin, max:yMax, ticks:{callback:v=>v+'\u00a0%'}, grid:{color:'#edeee9'} },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          filter: item => !item.dataset._isGhost && !item.dataset._isRaw && !item.dataset._isResult,
          callbacks: {
            title: items => items.length ? fmtTooltipDate(items[0].parsed.x) : '',
            label: ctx => `${ctx.dataset.label}\u00a0: ${fmtPct(ctx.parsed.y)}`,
          },
        },
      },
    },
  });

  // Custom legend
  const legend = document.getElementById('t2-legend');
  for (const cid of [cidA, cidB]) {
    const label = document.createElement('label');
    label.className = 'cand';
    label.style.cursor = 'default';
    const pastille = document.createElement('span');
    pastille.className = 'pastille'; pastille.style.background = candCouleur(cid);
    const nom = document.createElement('span');
    nom.className = 'nom'; nom.textContent = candNom(cid);
    const res = document.createElement('span');
    res.className = 'res';
    res.textContent = resT2[cid] != null ? fmtPct2(resT2[cid]) : '';
    // no checkbox for T2 legend
    const spacer = document.createElement('span');
    label.append(spacer, pastille, nom, res);
    legend.appendChild(label);
  }
}

// --- Initialisation ---
async function initHistorique(annee) {
  await loadData(annee);

  document.getElementById('periode-group').querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', () => {
      document.getElementById('periode-group').querySelectorAll('button').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      renderT1();
      if (document.querySelector('#panel-t2.active')) renderT2();
    });
  });

  checkedT1.clear();
  for (const [cid, info] of Object.entries(ELECTION.candidats))
    if (info.visible) checkedT1.add(cid);
  renderCheckboxesT1();
  renderT1();

  const tabs = document.querySelectorAll('.tab');
  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      document.getElementById('panel-t1').classList.toggle('active', tab.dataset.tab === 't1');
      document.getElementById('panel-t2').classList.toggle('active', tab.dataset.tab === 't2');
      if (tab.dataset.tab === 't2') {
        if (!document.getElementById('duel-cand1').options.length) populateDuelSelects();
        renderT2();
      }
    });
  });

  populateDuelSelects();

  const resume = document.getElementById('resume');
  if (resume) {
    const nb = ELECTION.nb_sondages_t1, nr = ELECTION.nb_rollings_t1;
    resume.textContent = `${nb} sondages depuis janvier ${ELECTION.borne.slice(0,4)}` +
      (nr > 0 ? ` dont ${nr} vagues de rolling` : '') + '.';
  }

  const attrib = document.getElementById('attribution');
  if (attrib && ELECTION.revid) {
    attrib.innerHTML = `Source\u00a0: <a href="https://en.wikipedia.org/w/index.php?oldid=${ELECTION.revid}" target="_blank">en.wikipedia.org</a>, version figée (CC BY-SA 4.0).`;
  }
}
