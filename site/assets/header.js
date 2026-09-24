// Bandeau d'en-tête Sondax — rendu client depuis HEADER_DATA
// Le fichier header-data.js (généré au build) doit être chargé avant ce script.
//
// Une seule ligne collante : logo, navigation principale, compte à rebours.
// Sur une page qui contient <nav id="sub-nav"> (l'accueil), la sous-navigation
// est déplacée dans le bandeau et n'apparaît qu'une fois le H1 dépassé : le
// bandeau passe alors en barre compacte (logo réduit, sections, bouton Menu).

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

  var cdBig, cdDate, cdDateCourte;
  var hideCountdown = d2 < 0;

  if (d1 > 0) {
    cdBig = 'J−' + d1;
    cdDate = '1<sup>er</sup> tour · 18 avril 2027';
    cdDateCourte = '18 avril';
  } else if (d1 === 0) {
    cdBig = 'J0';
    cdDate = '1<sup>er</sup> tour · aujourd’hui';
    cdDateCourte = 'aujourd’hui';
  } else if (d2 > 0) {
    cdBig = 'J−' + d2;
    cdDate = '2<sup>d</sup> tour · 2 mai 2027';
    cdDateCourte = '2 mai';
  } else if (d2 === 0) {
    cdBig = 'J0';
    cdDate = '2<sup>d</sup> tour · aujourd’hui';
    cdDateCourte = 'aujourd’hui';
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
    { slug: 'philippe', nom: 'Édouard Philippe' },
    { slug: 'melenchon', nom: 'Jean-Luc Mélenchon' },
    { slug: 'glucksmann', nom: 'Raphaël Glucksmann' },
    { slug: 'attal', nom: 'Gabriel Attal' },
    { slug: 'retailleau', nom: 'Bruno Retailleau' },
    { slug: 'tondelier', nom: 'Marine Tondelier' },
    { slug: 'zemmour', nom: 'Éric Zemmour' },
    { slug: 'roussel', nom: 'Fabien Roussel' }
  ];

  var navItems = [
    { label: 'Accueil', href: 'index.html', match: ['index.html', ''] },
    { label: 'Candidats', href: '#', match: candidatsPages.map(function(c) { return c.slug + '.html'; }), dropdown: true },
    { label: 'Sondages', href: 'sondages.html', match: ['sondages.html'] },
    { label: 'Instituts', href: 'instituts.html', match: ['instituts.html'] },
    { label: 'Élections passées', href: 'precedentes-elections.html', match: ['precedentes-elections.html'], prefixe: 'presidentielle-' },
    { label: 'Méthode', href: 'methodologie.html', match: ['methodologie.html'] },
    { label: 'Données', href: 'donnees.html', match: ['donnees.html'] }
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
    return !!(item.prefixe && page.indexOf(item.prefixe) === 0);
  }

  function candidatsMenuHTML() {
    var h = '<div class="menu-candidats">' +
      '<a href="' + baseHref + 'candidats/" class="menu-candidats-label">Candidats</a>' +
      '<div class="menu-panneau">';
    for (var k = 0; k < candidatsPages.length; k++) {
      var cp = candidatsPages[k];
      h += '<a href="' + baseHref + cp.slug + '.html">' + cp.nom + '</a>';
    }
    return h + '</div></div>';
  }

  function navLinksHTML() {
    var h = '';
    for (var i = 0; i < navItems.length; i++) {
      var it = navItems[i];
      if (it.dropdown) {
        h += candidatsMenuHTML();
      } else if (isActive(it)) {
        h += '<a href="' + baseHref + it.href + '" class="is-active" aria-current="page">' + it.label + '</a>';
      } else {
        h += '<a href="' + baseHref + it.href + '">' + it.label + '</a>';
      }
    }
    return h;
  }

  var html = '<div class="sh-inner">' +
      '<a class="sh-logo" href="' + baseHref + 'index.html" aria-label="Sondax — accueil">' +
        logoSVG +
        '<span class="sh-wordmark">sondax</span>' +
      '</a>' +
      '<nav class="sh-nav" aria-label="Navigation principale">' + navLinksHTML() + '</nav>' +
      '<div class="sh-sub-slot"></div>' +
      (hideCountdown ? '' :
      '<div class="sh-cd">' +
        '<span class="sh-cd-big">' + cdBig + '</span>' +
        '<span class="sh-cd-date sh-cd-date-longue">' + cdDate + '</span>' +
        '<span class="sh-cd-date sh-cd-date-courte">' + cdDateCourte + '</span>' +
      '</div>') +
      '<button type="button" class="sh-menu-btn" aria-label="Menu" aria-expanded="false" aria-controls="sh-panel">' +
        '<span class="sh-menu-bars" aria-hidden="true"><span></span><span></span><span></span></span>' +
        '<span class="sh-menu-txt" aria-hidden="true">Menu</span>' +
      '</button>' +
    '</div>' +
    '<nav class="sh-panel" id="sh-panel" aria-label="Navigation principale">' + navLinksHTML() + '</nav>';

  var el = document.getElementById('site-header');
  if (!el) return;
  el.innerHTML = html;

  var inner = el.querySelector('.sh-inner');
  var logo = el.querySelector('.sh-logo');
  var nav = el.querySelector('.sh-nav');
  var cd = el.querySelector('.sh-cd');
  var btn = el.querySelector('.sh-menu-btn');
  var panel = el.querySelector('.sh-panel');
  var mqMobile = window.matchMedia('(max-width: 767px)');

  // --- Bouton Menu / burger ---
  function fermerPanel() {
    panel.classList.remove('is-open');
    btn.setAttribute('aria-expanded', 'false');
  }
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    var open = panel.classList.toggle('is-open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', function (e) {
    if (!panel.contains(e.target)) fermerPanel();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && panel.classList.contains('is-open')) {
      fermerPanel();
      btn.focus();
    }
  });

  // Close dropdown on outside click (hover opens it on desktop)
  var menuWrap = el.querySelector('.sh-nav .menu-candidats');
  if (menuWrap) {
    document.addEventListener('click', function (e) {
      if (!menuWrap.contains(e.target)) {
        menuWrap.classList.remove('is-open');
      }
    });
  }

  // --- La navigation principale ne passe jamais sur deux lignes ---
  // Entre 768 et ~1 200 px, on mesure : si logo + navigation + compte à
  // rebours ne tiennent pas sur la ligne, on bascule sur le burger.
  function ajusterLargeur() {
    if (mqMobile.matches || el.classList.contains('is-compact')) return;
    el.classList.remove('is-narrow');
    var style = getComputedStyle(inner);
    var dispo = inner.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
    var gap = parseFloat(style.columnGap) || 0;
    var requis = logo.offsetWidth + nav.scrollWidth + (cd ? cd.offsetWidth : 0) + 2 * gap + 24;
    if (requis > dispo) el.classList.add('is-narrow');
  }
  ajusterLargeur();
  if (window.ResizeObserver) {
    new ResizeObserver(ajusterLargeur).observe(el);
  } else {
    window.addEventListener('resize', ajusterLargeur);
  }
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(ajusterLargeur);

  // --- Sous-navigation de l'accueil ---
  function initSousNav() {
    var sub = document.getElementById('sub-nav');
    var h1 = document.querySelector('main h1') || document.querySelector('h1');
    if (!sub || !h1 || !window.IntersectionObserver) return;

    el.querySelector('.sh-sub-slot').appendChild(sub);
    el.classList.add('has-subnav');

    var liens = [].slice.call(sub.querySelectorAll('a[href^="#"]'));
    var sections = liens.map(function (a) {
      return document.getElementById(a.getAttribute('href').slice(1));
    });
    var actif = null;
    var verrou = 0; // pendant un défilement déclenché par un clic

    function activer(i) {
      if (i === actif) return;
      actif = i;
      liens.forEach(function (a, j) {
        if (j === i) {
          a.classList.add('is-active');
          a.setAttribute('aria-current', 'true');
        } else {
          a.classList.remove('is-active');
          a.removeAttribute('aria-current');
        }
      });
      // Rangée à défilement horizontal (mobile) : ramener la pastille active
      var a = liens[i];
      if (a && sub.scrollWidth > sub.clientWidth) {
        sub.scrollTo({ left: a.offsetLeft - (sub.clientWidth - a.offsetWidth) / 2, behavior: 'smooth' });
      }
    }

    // Barre compacte une fois le H1 passé sous le bandeau
    new IntersectionObserver(function (entries) {
      var e = entries[0];
      var passe = !e.isIntersecting && e.boundingClientRect.top < e.rootBounds.top;
      if (passe === el.classList.contains('is-compact')) return;
      el.classList.toggle('is-compact', passe);
      if (!passe) {
        fermerPanel();
        ajusterLargeur();
      } else if (actif !== null) {
        var a = liens[actif];
        sub.scrollLeft = a.offsetLeft - (sub.clientWidth - a.offsetWidth) / 2;
      }
    }, { rootMargin: '-64px 0px 0px 0px' }).observe(h1);

    // Scroll-spy : section présente dans la moitié haute de l'écran
    var visibles = [];
    var spy = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) {
        visibles[sections.indexOf(e.target)] = e.isIntersecting;
      });
      if (Date.now() < verrou) return;
      // Plusieurs sections dans la zone : la dernière entrée (la plus basse)
      for (var i = sections.length - 1; i >= 0; i--) {
        if (visibles[i]) { activer(i); return; }
      }
      // Aucune section dans la zone : au-dessus de la première, rien d'actif
      if (sections[0] && sections[0].getBoundingClientRect().top > window.innerHeight / 2) activer(null);
    }, { rootMargin: '-110px 0px -50% 0px' });
    sections.forEach(function (s) { if (s) spy.observe(s); });

    // Clic : défilement doux, compensé par scroll-margin-top sur les sections
    var reduit = window.matchMedia('(prefers-reduced-motion: reduce)');
    liens.forEach(function (a, i) {
      a.addEventListener('click', function (e) {
        var cible = sections[i];
        if (!cible) return;
        e.preventDefault();
        activer(i);
        verrou = Date.now() + 1000;
        cible.scrollIntoView({ behavior: reduit.matches ? 'auto' : 'smooth', block: 'start' });
        if (history.replaceState) history.replaceState(null, '', '#' + cible.id);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSousNav);
  } else {
    initSousNav();
  }
})();
