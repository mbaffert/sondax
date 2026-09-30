/* Bloc Rétro-Sondax de la home (#retro-sondax) — mise à jour côté navigateur.
   build_retro.py injecte le bloc pour le J-x du jour du build ; sans nouveau
   déploiement, il resterait figé. Ce script recalcule le J-x avec la valeur du
   compte à rebours du header et, s'il diffère, régénère le sous-titre et la
   grille depuis data/derived/retro.json, avec le même HTML que rendre_bloc()
   et cellule(). Hors de 1 à 365, ou si retro.json ne se charge pas, le bloc
   statique reste en place. SPEC §15. */

(function () {
  var ANNEES = ['2022', '2017', '2012', '2007'];
  var J_MAX = 365;
  var FEMININ = { royal: 1, aubry: 1, pecresse: 1, 'alliot-marie': 1, 'kosciusko-morizet': 1 };

  function joursAvant2027() {
    // Réutilise la valeur du countdown si elle a été calculée (même chiffre partout)
    if (window._joursAvantT1_2027 != null) return window._joursAvantT1_2027;
    var p = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' });
    var today = new Date(p + 'T00:00:00');
    return Math.round((new Date(2027, 3, 18) - today) / 864e5);
  }

  // html.escape de Python (quote=True)
  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#x27;');
  }

  // round() de Python : arrondi au pair sur les demis
  function arrondi(x) {
    var f = Math.floor(x);
    if (x - f === 0.5) return f % 2 === 0 ? f : f + 1;
    return Math.round(x);
  }

  function fmtPct(v) { return v.toFixed(1).replace('.', ','); }

  function cellule(e, cands, w) {
    var c = cands[e.id];
    var parti = c.type === 'parti';
    var note = '';
    if (parti && e.teste && cands[e.teste]) {
      note = esc(cands[e.teste].nom_court) + ' ' + (FEMININ[e.teste] ? 'testée' : 'testé');
    }
    return '<div class="' + (parti ? 'rs-cell rs-parti' : 'rs-cell') + '">' +
      '<div class="rs-nom">' + esc(c.nom_court) + '</div>' +
      '<div class="rs-score">' + fmtPct(e.v) + '<span class="pct">\u00a0%</span></div>' +
      '<div class="rs-bar-wrap"><div class="rs-bar" style="width:' + w + '%' +
      (parti ? '' : ';background:' + c.couleur) + '"></div></div>' +
      '<div class="rs-note">' + (note || '&nbsp;') + '</div>' +
      '</div>';
  }

  // Contenu de #retro-sondax, identique à rendre_bloc() entre les balises du bloc
  function rendreContenu(retro, x) {
    var colonnes = ANNEES.map(function (annee) {
      var el = retro.elections[annee];
      var top = el.jours[String(x)].top;
      var tete = top.length ? top[0].v : 1;
      var cells = top.map(function (e) {
        return cellule(e, el.candidats, arrondi(100 * e.v / tete));
      }).join('');
      return '    <div class="rs-col"><div class="rs-annee">' + annee + '</div>' + cells + '</div>';
    });
    return '\n  <h2>Rétro-Sondax</h2>\n' +
      '  <p class="subtitle">À J-' + x + ' de la présidentielle, qui était en tête des sondages\u00a0?</p>\n' +
      '  <div class="rs-grille">\n' + colonnes.join('\n') + '\n  </div>\n';
  }

  function maj() {
    var bloc = document.getElementById('retro-sondax');
    if (!bloc) return;
    var x = joursAvant2027();
    if (!(x >= 1 && x <= J_MAX)) return;
    var sous = bloc.querySelector('.subtitle');
    var m = sous && sous.textContent.match(/J-(\d+)/);
    if (m && +m[1] === x) return;
    fetch('data/derived/retro.json')
      .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then(function (retro) { bloc.innerHTML = rendreContenu(retro, x); })
      .catch(function () { /* bloc statique conservé */ });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', maj);
  else maj();
})();
