(() => {
  'use strict';
  let folded = null;
  const output = () => document.getElementById('natal-chart-output') || document.querySelector('main');
  window.addEventListener('beforeprint', () => {
    if (folded !== null) return;
    folded = [...(output()?.querySelectorAll('details:not([open])') || [])];
    folded.forEach(section => { section.open = true; });
  });
  window.addEventListener('afterprint', () => {
    folded?.forEach(section => { section.open = false; });
    folded = null;
  });
  document.addEventListener('click', event => {
    if (event.target.closest('[data-natal-print]')) window.print();
  });
})();
