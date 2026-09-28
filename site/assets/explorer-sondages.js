/* Module « Explorer les sondages » (sondages.html, #bloc-fiche).
 *
 * Sélecteur de sondage, sélecteur de configuration, tableau
 * candidat / score / marge d'erreur. Le premier rendu est fait au build
 * (scripts/build_sondages_page.py) ; ce script prend le relais pour
 * l'interaction et produit le même balisage.
 *
 * La page déclare PAGES_CANDIDATS (Set des slugs ayant une fiche) et
 * renseigne CANDIDATS (contenu de candidats.json) avant d'instancier
 * ExplorerSondages.
 */
let CANDIDATS = null;

// Mêmes utilitaires que bloc-chart.js (non chargé sur cette page)
function fmtPct(v) {
  return v.toFixed(1).replace('.', ',') + ' %';
}

function fmtDate(iso) {
  const [y, m, d] = iso.split('-');
  return `${d}/${m}/${y}`;
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

function margeDErreur(p, n) {
  return 1.96 * Math.sqrt(p * (1 - p) / n) * 100;
}

function hypLabel(hyp, allT1) {
  const sets = allT1.map(h => new Set(Object.keys(h.scores)));
  const common = new Set(sets[0]);
  for (const s of sets.slice(1)) {
    for (const c of common) { if (!s.has(c)) common.delete(c); }
  }
  const mine = new Set(Object.keys(hyp.scores));
  const distinctive = [...mine].filter(c => !common.has(c)).map(c => nomCourt(c));
  if (distinctive.length === 0) return `${Object.keys(hyp.scores).length} candidats`;
  return `avec ${distinctive.join(', ')}`;
}

function trierT1(s) {
  // Principale d'abord, puis par nombre de candidats décroissant (comme les pages sondage)
  return s.hypotheses.filter(h => h.tour === 1)
    .map((h, i) => ({ h, i }))
    .sort((a, b) => ((a.h.principale ? 0 : 1) - (b.h.principale ? 0 : 1))
      || (Object.keys(b.h.scores).length - Object.keys(a.h.scores).length) || (a.i - b.i))
    .map(x => x.h);
}

function escHtml(str) {
  return String(str).replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
}

class ExplorerSondages {
  constructor(sondages) {
    // Plus récent d'abord ; à fin de terrain égale, plus grand échantillon
    // (même départage que select_latest_sondage dans build_header.py)
    this.sondages = sondages.slice().sort((a, b) => b.terrain_fin.localeCompare(a.terrain_fin)
      || ((b.echantillon || 0) - (a.echantillon || 0)));
    this.selSondage = document.getElementById('fiche-sondage');
    this.selHyp = document.getElementById('fiche-hyp');
    this.result = document.getElementById('fiche-result');

    this.populateSondages();
    this.selSondage.addEventListener('change', () => this.onSondageChange());
    this.selHyp.addEventListener('change', () => {
      const s = this.currentSondage();
      if (s) trackEvent('hypothese/1/' + s.id);
      this.renderResult();
    });
    this.onSondageChange();
  }

  populateSondages() {
    this.selSondage.innerHTML = '';
    for (const s of this.sondages) {
      const ech = s.echantillon ? Math.round(s.echantillon).toLocaleString('fr-FR') : '?';
      const opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = `${s.institut} — ${fmtDate(s.terrain_fin)} (n = ${ech})`;
      this.selSondage.appendChild(opt);
    }
  }

  currentSondage() {
    return this.sondages.find(s => s.id === this.selSondage.value) || null;
  }

  // Charge un sondage par son identifiant, configuration principale
  select(id) {
    if (!this.sondages.some(s => s.id === id)) return false;
    this.selSondage.value = id;
    this.onSondageChange();
    return true;
  }

  onSondageChange() {
    const s = this.currentSondage();
    this.selHyp.innerHTML = '';
    if (!s) { this.result.innerHTML = ''; return; }

    const t1 = trierT1(s);
    if (t1.length === 0) {
      const opt = document.createElement('option');
      opt.textContent = 'Aucune hypothèse de premier tour';
      this.selHyp.appendChild(opt);
      this.result.innerHTML = '';
      return;
    }

    t1.forEach((h, i) => {
      const opt = document.createElement('option');
      opt.value = i;
      opt.textContent = hypLabel(h, t1);
      this.selHyp.appendChild(opt);
    });

    this.renderResult();
  }

  renderResult() {
    const s = this.currentSondage();
    const metaEl = document.getElementById('fiche-meta');
    if (!s) { this.result.innerHTML = ''; return; }

    const t1 = trierT1(s);
    const hyp = t1[parseInt(this.selHyp.value)];
    if (!hyp) { this.result.innerHTML = ''; return; }

    const ech = s.echantillon ? Math.round(s.echantillon) : null;
    const echStr = ech ? ech.toLocaleString('fr-FR') : '—';

    const manuelTag = s.source === 'manuel' ? ' · <span style="color:var(--bleu-vif);">saisie manuelle</span>' : '';
    if (metaEl) {
      metaEl.innerHTML = `${s.institut} — ${fmtDate(s.terrain_debut)} → ${fmtDate(s.terrain_fin)} — Échantillon : ${echStr}${manuelTag}` +
        ` · <a href="sondages/${encodeURIComponent(s.id)}.html" style="font-weight:500;">Voir la fiche</a>`;
    }

    const hypEch = hyp.echantillon || null;
    const n = hypEch || ech;
    const approx = !hypEch && !!ech;
    const isP = !!hyp.principale;

    const scores = Object.entries(hyp.scores).filter(([cid]) => cid !== 'autre').sort((a, b) => b[1] - a[1]);

    const head = [];
    if (isP) head.push('<span class="badge badge-principale">Principale</span>');
    if (hypEch) head.push(`<span class="hyp-detail">${Math.round(hypEch).toLocaleString('fr-FR')} personnes</span>`);

    const th = '<th>Candidat</th><th class="col-score">Score</th><th class="col-me">Marge d’erreur</th>';

    const rows = scores.map(([cid, v]) => {
      const c = CANDIDATS[cid] || {};
      const nomComplet = escHtml([c.prenom, c.nom].filter(Boolean).join(' ') || cid);
      const nom = PAGES_CANDIDATS.has(cid) ? `<a href="${cid}.html">${nomComplet}</a>` : nomComplet;
      const partiCls = c.type === 'parti' ? ' class="type-parti"' : '';
      const p = v / 100;
      let meStr = '—';
      if (n && p > 0 && p < 1) {
        meStr = `± ${margeDErreur(p, n).toFixed(1).replace('.', ',')} %`;
        if (approx) meStr += ' <span class="me-approx">(approx.)</span>';
      }
      const w = Math.min(Math.max(v, 0), 60);
      return `<tr${partiCls}><td class="cand-name">${nom}</td>` +
        `<td class="col-score"><span class="bar" style="--w:${w.toFixed(0)};background:${couleur(cid)}"></span>${fmtPct(v)}</td>` +
        `<td class="col-me">${meStr}</td></tr>`;
    }).join('');

    let html = `<div class="hypothese${isP ? ' hyp-principale' : ''}">`;
    if (head.length) html += `<div class="hyp-header">${head.join(' ')}</div>`;
    html += `<table class="scores-table"><thead><tr>${th}</tr></thead><tbody>${rows}</tbody></table>`;
    if (approx) html += '<p class="note-approx">Marge approximative, calculée sur l’échantillon total.</p>';
    html += '</div>';
    this.result.innerHTML = html;
  }
}
