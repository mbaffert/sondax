/* Copie dans le presse-papiers : seul usage de JavaScript du bloc « Partager /
   Reprendre ». Sans JS, les boutons restent masqués (attribut hidden) et le
   code HTML reste lisible et sélectionnable dans la zone de texte. */
(function () {
  function copier(texte, zone) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(texte);
    return new Promise(function (ok, ko) {
      var t = zone || document.createElement('textarea');
      if (!zone) { t.value = texte; t.setAttribute('readonly', ''); t.style.position = 'fixed'; t.style.opacity = '0'; document.body.appendChild(t); }
      t.select();
      var reussi = false;
      try { reussi = document.execCommand('copy'); } catch (e) {}
      if (!zone) document.body.removeChild(t);
      reussi ? ok() : ko();
    });
  }
  document.querySelectorAll('.pt-partage').forEach(function (bloc) {
    if (bloc.dataset.pret) return;
    bloc.dataset.pret = '1';
    var etat = bloc.querySelector('.pt-etat');
    bloc.querySelectorAll('button[data-copier], button[data-copier-cible]').forEach(function (b) {
      b.hidden = false;
      b.addEventListener('click', function () {
        var zone = b.dataset.copierCible ? document.getElementById(b.dataset.copierCible) : null;
        copier(zone ? zone.value : b.dataset.copier, zone).then(function () {
          etat.textContent = 'Copié';
        }, function () {
          etat.textContent = 'Copie impossible : sélectionnez le texte à la main.';
        });
      });
    });
  });
})();
