// Bandeau d'en-tête Sondax — rendu client depuis HEADER_DATA
// Le fichier header-data.js (généré au build) doit être chargé avant ce script.

(function () {
  var D = window.HEADER_DATA;
  if (!D) return;

  // --- Compte à rebours (réutilise la logique existante) ---
  var T1 = new Date(2027, 3, 18), T2 = new Date(2027, 4, 2);
  var p = new Date().toLocaleDateString('en-CA', { timeZone: 'Europe/Paris' });
  var today = new Date(p + 'T00:00:00');
  var d1 = Math.round((T1 - today) / 864e5);
  var d2 = Math.round((T2 - today) / 864e5);
  window._joursAvantT1_2027 = d1;

  var cdLabel, cdBig, cdDate, cdDateMobile;
  var hideCountdown = d2 < 0;

  if (d1 > 0) {
    cdLabel = 'Premier tour';
    cdBig = 'J\u2212' + d1;
    cdDate = 'dimanche 18 avril 2027';
    cdDateMobile = '1<sup>er</sup> tour \u00b7 dim. 18 avril 2027';
  } else if (d1 === 0) {
    cdLabel = 'Premier tour';
    cdBig = 'J0';
    cdDate = 'Premier tour aujourd\u2019hui';
    cdDateMobile = '1<sup>er</sup> tour \u00b7 aujourd\u2019hui';
  } else if (d2 > 0) {
    cdLabel = 'Second tour';
    cdBig = 'J\u2212' + d2;
    cdDate = 'dimanche 2 mai 2027';
    cdDateMobile = '2<sup>d</sup> tour \u00b7 dim. 2 mai 2027';
  } else if (d2 === 0) {
    cdLabel = 'Second tour';
    cdBig = 'J0';
    cdDate = 'Second tour aujourd\u2019hui';
    cdDateMobile = '2<sup>d</sup> tour \u00b7 aujourd\u2019hui';
  }

  // --- Logo SVG (icône seule, deux courbes entrelacées) ---
  var logoSVG = '<svg viewBox="0 0 44 24" aria-hidden="true">' +
    '<path d="M4 7 C 12 7, 14 17, 22 17 C 30 17, 32 7, 40 7" fill="none" stroke="#0C6CF2" stroke-width="5.5" stroke-linecap="round"/>' +
    '<path d="M4 17 C 12 17, 14 7, 22 7 C 30 7, 32 17, 40 17" fill="none" stroke="#F23D5B" stroke-width="5.5" stroke-linecap="round"/>' +
    '</svg>';

  // --- Navigation ---
  var pathname = window.location.pathname;
  var page = pathname.split('/').pop() || 'index.html';

  var navItems = [
    { label: 'Accueil', href: 'index.html', match: ['index.html', ''] },
    { label: 'Sondages', href: 'sondages.html', match: ['sondages.html'] },
    { label: 'M\u00e9thodologie', href: 'methodologie.html', match: ['methodologie.html'] },
    { label: 'Pr\u00e9c\u00e9dentes \u00e9lections', href: 'precedentes-elections.html', match: ['precedentes-elections.html'] }
  ];

  var baseHref = '';
  if (pathname.indexOf('/second-tour/') !== -1) {
    baseHref = '../';
  }

  function isActive(item) {
    for (var i = 0; i < item.match.length; i++) {
      if (page === item.match[i]) return true;
    }
    if (item.label === 'Pr\u00e9c\u00e9dentes \u00e9lections' && page.indexOf('presidentielle-') === 0) {
      return true;
    }
    return false;
  }

  var navHTML = '';
  for (var i = 0; i < navItems.length; i++) {
    var cls = isActive(navItems[i]) ? ' class="is-active"' : '';
    navHTML += '<a href="' + baseHref + navItems[i].href + '"' + cls + '>' + navItems[i].label + '</a>';
  }

  // --- Stats ---
  var statsText = D.pollCount + ' sondages agr\u00e9g\u00e9s \u00b7 ' + D.instituteCount + ' instituts';

  // --- Scores grid ---
  var gridHTML = '';
  for (var c = 0; c < D.candidates.length; c++) {
    var cand = D.candidates[c];
    gridHTML += '<div class="sh-col">' +
      '<div class="sh-name">' + cand.name + '</div>' +
      '<div class="sh-score">' +
        '<span class="sh-score-num">' + cand.score + '</span>' +
        '<span class="sh-score-pct">%</span>' +
      '</div>' +
    '</div>';
  }

  var detailText = 'Voir le d\u00e9tail \u2192';

  // --- Link target ---
  var scoreHref = baseHref + 'index.html#bloc-fiche';

  // --- Mobile title (short): "Institut · date" ---
  var mobileTitleText = D.institut + ' \u00b7 ' + D.terrainLabelMobile;

  // --- Desktop title: "Institut · date" ---
  var desktopTitleText = D.institut + ' \u00b7 ' + D.terrainLabel;

  // --- Assemble header: left column THEN countdown (right) ---
  var html = '<div class="sh-inner">' +
    '<div class="sh-left">' +
      '<div class="sh-nav-row">' +
        '<a class="sh-logo" href="' + baseHref + 'index.html" aria-label="Sondax \u2014 accueil">' +
          logoSVG +
          '<span class="sh-wordmark">sondax</span>' +
        '</a>' +
        '<div class="sh-nav">' + navHTML + '</div>' +
        '<div class="sh-stats sh-stats-desktop">' + statsText + '</div>' +
        '<button class="sh-menu-btn" aria-label="Menu" aria-expanded="false">' +
          '<span class="sh-menu-bar"></span>' +
          '<span class="sh-menu-bar"></span>' +
          '<span class="sh-menu-bar"></span>' +
        '</button>' +
      '</div>' +
      '<a class="sh-scores" href="' + scoreHref + '">' +
        '<h2 class="sh-title">' +
          '<span>Dernier sondage</span>' +
          '<span class="sh-title-meta sh-title-text"> \u2014 ' + desktopTitleText + ' \u00b7 </span>' +
          '<span class="sh-title-meta sh-title-text-mobile">' + mobileTitleText + '</span>' +
          '<span class="sh-detail">' + detailText + '</span>' +
        '</h2>' +
        '<div class="sh-grid">' + gridHTML + '</div>' +
        '<div class="sh-stats-mobile">' + statsText + '</div>' +
      '</a>' +
    '</div>' +
    (hideCountdown ? '' :
    '<div class="sh-countdown">' +
      '<div class="sh-cd-label">' + cdLabel + '</div>' +
      '<div class="sh-cd-big">' + cdBig + '</div>' +
      '<div class="sh-cd-date">' +
        '<span class="sh-cd-date-desktop">' + cdDate + '</span>' +
        '<span class="sh-cd-date-mobile">' + cdDateMobile + '</span>' +
      '</div>' +
    '</div>') +
  '</div>';

  html += '<nav class="sh-mobile-nav">';
  for (var j = 0; j < navItems.length; j++) {
    var cls2 = isActive(navItems[j]) ? ' class="is-active"' : '';
    html += '<a href="' + baseHref + navItems[j].href + '"' + cls2 + '>' + navItems[j].label + '</a>';
  }
  html += '</nav>';

  var el = document.getElementById('site-header');
  if (el) {
    el.innerHTML = html;
  }

  var btn = el && el.querySelector('.sh-menu-btn');
  var mobileNav = el && el.querySelector('.sh-mobile-nav');
  if (btn && mobileNav) {
    btn.addEventListener('click', function () {
      var open = mobileNav.classList.toggle('is-open');
      btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
})();
