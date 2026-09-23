/* Étiquettes de fin de courbe (nom + valeur), partagées par tous les graphiques.
 *
 * Usage : un dataset porteur d'étiquette a `_label` (texte) et éventuellement
 * `_labelColor`. L'étiquette se place au dernier point non nul du dataset.
 * Points proches du bord droit → étiquette dans la marge droite, empilée sans
 * chevauchement ; sinon, étiquette juste à droite du point.
 *
 *   options.layout.padding = SondaxEndLabels.padding({ top: 24 })
 *   plugins: [SondaxEndLabels.plugin]
 */
(function () {
  const mobile = () => window.innerWidth < 600;
  const font = () => `500 ${mobile() ? 10 : 11}px 'IBM Plex Sans', system-ui, sans-serif`;
  const GUTTER = 6;       // écart entre zone de tracé et étiquette
  const NEAR_EDGE = 40;   // px : en deçà, l'étiquette part dans la marge

  function labelled(chart) {
    return chart.data.datasets
      .map((ds, i) => ({ ds, i }))
      .filter(({ ds, i }) => ds._label && chart.isDatasetVisible(i));
  }

  function padding(base = {}) {
    return (ctx) => {
      const chart = ctx.chart;
      const c = chart.ctx;
      c.save();
      c.font = font();
      let w = 0;
      for (const { ds } of labelled(chart)) w = Math.max(w, c.measureText(ds._label).width);
      c.restore();
      return { top: 0, bottom: 0, left: 0, ...base, right: (base.right || 0) + (w ? Math.ceil(w) + GUTTER + 4 : 0) };
    };
  }

  const plugin = {
    id: 'sondaxEndLabels',
    afterDatasetsDraw(chart) {
      const area = chart.chartArea;
      const gauche = [], marge = [];
      for (const { ds, i } of labelled(chart)) {
        const meta = chart.getDatasetMeta(i);
        let k = ds.data.length - 1;
        while (k >= 0 && (ds.data[k] == null || ds.data[k].y == null || isNaN(ds.data[k].y))) k--;
        if (k < 0 || !meta.data[k]) continue;
        const pt = meta.data[k];
        if (pt.x < area.left - 1 || pt.x > area.right + 1) continue;
        const lb = {
          text: ds._label, x: pt.x, y: pt.y, ty: pt.y,
          color: ds._labelColor || ds._origBorderColor || ds.borderColor,
        };
        (area.right - pt.x < NEAR_EDGE ? marge : gauche).push(lb);
      }

      // Empilement sans chevauchement dans la marge droite
      const GAP = mobile() ? 12 : 14;
      marge.sort((a, b) => a.y - b.y);
      for (let j = 1; j < marge.length; j++) {
        if (marge[j].ty - marge[j - 1].ty < GAP) marge[j].ty = marge[j - 1].ty + GAP;
      }
      if (marge.length) {
        const over = marge[marge.length - 1].ty - (area.bottom - 4);
        if (over > 0) for (const l of marge) l.ty -= over;
        const under = (area.top + 4) - marge[0].ty;
        if (under > 0) for (const l of marge) l.ty += under;
      }

      const ctx = chart.ctx;
      ctx.save();
      ctx.font = font();
      ctx.textBaseline = 'middle';
      ctx.textAlign = 'left';
      for (const lb of marge) {
        const lx = area.right + GUTTER;
        if (Math.abs(lb.ty - lb.y) > 3) {
          ctx.strokeStyle = lb.color + '60';
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(lb.x + 3, lb.y);
          ctx.lineTo(lx - 2, lb.ty);
          ctx.stroke();
        }
        ctx.fillStyle = lb.color;
        ctx.fillText(lb.text, lx, lb.ty);
      }
      for (const lb of gauche) {
        ctx.fillStyle = lb.color;
        ctx.fillText(lb.text, lb.x + 6, lb.y);
      }
      ctx.restore();
    },
  };

  window.SondaxEndLabels = { plugin, padding };
})();
