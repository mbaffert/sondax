// Bandeau d'en-tête Sondax — rendu client depuis HEADER_DATA
// Le fichier header-data.js (généré au build) doit être chargé avant ce script.

(function () {
  var D = window.HEADER_DATA;
  if (!D) return;

  // --- Compte à rebours (dates depuis config.json via HEADER_DATA) ---
  var ed = D.electionDates || {};
  var T1 = ed.premierTour ? new Date(ed.premierTour + 'T00:00:00') : new Date(2027, 3, 18);
  var T2 = ed.secondTour ? new Date(ed.secondTour + 'T00:00:00') : new Date(2027, 4, 2);
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

  var candidatsPages = [
    { slug: 'le-pen', nom: 'Marine Le Pen' },
    { slug: 'philippe', nom: '\u00c9douard Philippe' },
    { slug: 'melenchon', nom: 'Jean-Luc M\u00e9lenchon' },
    { slug: 'glucksmann', nom: 'Rapha\u00ebl Glucksmann' },
    { slug: 'attal', nom: 'Gabriel Attal' },
    { slug: 'retailleau', nom: 'Bruno Retailleau' },
    { slug: 'tondelier', nom: 'Marine Tondelier' },
    { slug: 'zemmour', nom: '\u00c9ric Zemmour' },
    { slug: 'roussel', nom: 'Fabien Roussel' }
  ];

  var navItems = [
    { label: 'Accueil', href: 'index.html', match: ['index.html', ''] },
    { label: 'Candidats', href: '#', match: candidatsPages.map(function(c) { return c.slug + '.html'; }), dropdown: true },
    { label: 'Sondages', href: 'sondages.html', match: ['sondages.html'] },
    { label: 'Instituts', href: 'instituts.html', match: ['instituts.html'] },
    { label: 'Pr\u00e9c\u00e9dentes \u00e9lections', href: 'precedentes-elections.html', match: ['precedentes-elections.html'] },
    { label: 'M\u00e9thodologie', href: 'methodologie.html', match: ['methodologie.html'] },
    { label: 'Donn\u00e9es', href: 'donnees.html', match: ['donnees.html'] }
  ];

  // Pages situées dans un sous-dossier : liens relatifs remontés d'un niveau
  var sousDossier = pathname.match(/\/(second-tour|sondages|instituts|candidats)\//);
  var baseHref = sousDossier ? '../' : '';

  // Rubrique d'une page de sous-dossier (fiches sondage, pages institut)
  var rubriques = { sondages: 'Sondages', instituts: 'Instituts' };

  function isActive(item) {
    if (sousDossier) {
      return rubriques[sousDossier[1]] === item.label;
    }
    for (var i = 0; i < item.match.length; i++) {
      if (page === item.match[i]) return true;
    }
    if (item.label === 'Pr\u00e9c\u00e9dentes \u00e9lections' && page.indexOf('presidentielle-') === 0) {
      return true;
    }
    return false;
  }

  // Build candidats hover menu
  var candidatsMenuHTML = '<div class="menu-candidats">' +
    '<a href="' + baseHref + 'candidats/" class="menu-candidats-label">Candidats</a>' +
    '<div class="menu-panneau">';
  for (var k = 0; k < candidatsPages.length; k++) {
    var cp = candidatsPages[k];
    candidatsMenuHTML += '<a href="' + baseHref + cp.slug + '.html">' + cp.nom + '</a>';
  }
  candidatsMenuHTML += '</div></div>';

  var navHTML = '';
  for (var i = 0; i < navItems.length; i++) {
    if (navItems[i].dropdown) {
      navHTML += candidatsMenuHTML;
    } else {
      var cls = isActive(navItems[i]) ? ' class="is-active"' : '';
      navHTML += '<a href="' + baseHref + navItems[i].href + '"' + cls + '>' + navItems[i].label + '</a>';
    }
  }

  // --- Stats ---
  var statsText = D.pollCount + ' sondages agr\u00e9g\u00e9s \u00b7 ' + D.instituteCount + ' instituts';

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
    if (navItems[j].dropdown) {
      html += candidatsMenuHTML;
    } else {
      var cls2 = isActive(navItems[j]) ? ' class="is-active"' : '';
      html += '<a href="' + baseHref + navItems[j].href + '"' + cls2 + '>' + navItems[j].label + '</a>';
    }
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

  // Close dropdown on outside click (hover opens it on desktop)
  var menuWrap = el && el.querySelector('.sh-nav .menu-candidats');
  if (menuWrap) {
    document.addEventListener('click', function (e) {
      if (!menuWrap.contains(e.target)) {
        menuWrap.classList.remove('is-open');
      }
    });
  }
})();
