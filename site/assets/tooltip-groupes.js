/* Infobulle des graphiques de premier tour : candidats interchangeables.
 *
 * Avant qu'un camp ait choisi son candidat, chaque courbe vient de son propre
 * scénario (Juppé dans l'un, Fillon dans l'autre) : à une date donnée, leurs
 * scores ne s'additionnent pas. L'infobulle les réunit donc sous une ligne
 * « LR, selon le candidat : », suivie des noms précédés de « ou ».
 * Tri : par score décroissant, chaque groupe placé au rang de son meilleur
 * score. Les groupes viennent de scripts/alternatives.py.
 *
 * Usage, dans les options tooltip d'un graphique Chart.js :
 *   const g = SondaxGroupes.creer(item => <cid>, cid => <groupe ou null>);
 *   filter:  (item, i, arr) => g.preparer(arr, garder) && garder(item)
 *   itemSort: g.itemSort, callbacks: { beforeLabel: g.beforeLabel }
 *   et g.prefixe(item) devant le nom dans le callback label.
 */
const SondaxGroupes = {
  creer(cidDe, groupeDe) {
    return {
      // À appeler depuis filter : annote une fois les éléments conservés
      // (groupe, meilleur score du groupe, effectif, premier du groupe).
      preparer(items, garder) {
        if (items._sxPrep) return true;
        items._sxPrep = true;
        const kept = items.filter(it => garder(it) && it.parsed && it.parsed.y != null && !isNaN(it.parsed.y));
        const info = {};
        for (const it of kept) {
          const cid = cidDe(it);
          const g = (cid && groupeDe(cid)) || null;
          it._sxG = g ? 'g:' + g : 'c:' + cid + ':' + it.datasetIndex;
          it._sxLib = g;
          const inf = info[it._sxG] || (info[it._sxG] = { max: -Infinity, n: 0, tete: null });
          inf.n++;
          if (it.parsed.y > inf.max
              || (it.parsed.y === inf.max && it.datasetIndex < inf.tete.datasetIndex)) {
            inf.max = it.parsed.y; inf.tete = it;
          }
        }
        for (const it of kept) {
          const inf = info[it._sxG];
          it._sxMax = inf.max;
          it._sxN = inf.n;
          it._sxTete = inf.tete === it;
        }
        return true;
      },
      itemSort(a, b) {
        const ma = a._sxMax ?? -Infinity, mb = b._sxMax ?? -Infinity;
        if (mb !== ma) return mb - ma;
        if (a._sxG !== b._sxG) return a._sxG < b._sxG ? -1 : 1;
        const ya = a.parsed?.y ?? -Infinity, yb = b.parsed?.y ?? -Infinity;
        if (yb !== ya) return yb - ya;
        return a.datasetIndex - b.datasetIndex;
      },
      beforeLabel(item) {
        return item._sxN > 1 && item._sxTete ? `${item._sxLib}, selon le candidat :` : '';
      },
      prefixe(item) {
        return item._sxN > 1 && !item._sxTete ? 'ou ' : '';
      },
    };
  },
};
