/* Shared controls for inline SVG Star Almanack atlas charts.
   Mark protected target artwork with data-atlas-target="true". */
(function () {
  "use strict";
  const defaults = {
    asterisms: true, "other-asterisms": false,
    boundaries: true, figures: true, names: true,
    stars: true, catalog: false
  };
  function setup(root) {
    const svg = root.querySelector("svg");
    if (!svg) return;
    const scope = root.closest("main") || document;
    const controls = scope.querySelectorAll("input[type=checkbox][data-atlas-toggle]");
    function refresh() {
      const enabled = Object.assign({}, defaults);
      controls.forEach(box => { enabled[box.dataset.atlasToggle] = box.checked; });
      svg.querySelectorAll("[data-atlas-layer]").forEach(element => {
        if (element.closest('[data-atlas-target="true"]')) return;
        const layers = element.dataset.atlasLayer.trim().split(/\s+/);
        element.style.display = layers.every(layer => enabled[layer] !== false) ? "" : "none";
      });
    }
    controls.forEach(box => {
      if (Object.hasOwn(defaults, box.dataset.atlasToggle)) {
        box.checked = defaults[box.dataset.atlasToggle];
        box.addEventListener("change", refresh);
      }
    });
    refresh();
  }
  function start() { document.querySelectorAll("[data-atlas-chart]").forEach(setup); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
