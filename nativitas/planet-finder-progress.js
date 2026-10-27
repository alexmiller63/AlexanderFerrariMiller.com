/* Progress UI for the asynchronous Planet Finder worker.
 * Keep progress indeterminate until actual completion is known.
 */
(() => {
  'use strict';
  const panel = document.getElementById('finder-progress');
  if (!panel) return;
  const heading = document.getElementById('finder-progress-heading');
  const bar = document.getElementById('finder-progress-bar');
  const stage = document.getElementById('finder-stage');
  const elapsed = document.getElementById('finder-elapsed');
  const longRunning = document.getElementById('finder-long-running');
  const cancel = document.getElementById('finder-cancel');
  const zones = document.getElementById('finder-zones');
  for (const zone of ['UTC', ...(Intl.supportedValuesOf?.('timeZone') || [])]) {
    const option = document.createElement('option');
    option.value = zone;
    zones.append(option);
  }
  document.getElementById('finder-date').value = new Date().toISOString().slice(0, 10);
  let started = 0, ticker = null, cancelHandler = null;
  const tick = () => {
    const seconds = Math.floor((performance.now() - started) / 1000);
    elapsed.value = String(Math.floor(seconds / 60)).padStart(2, '0') + ':' + String(seconds % 60).padStart(2, '0');
    longRunning.hidden = seconds < 60;
  };
  const stop = () => { if (ticker !== null) clearInterval(ticker); ticker = null; };
  window.PlanetFinderProgress = {
    start(onCancel) {
      stop();
      cancelHandler = onCancel;
      cancel.disabled = false;
      heading.textContent = 'Calculating your chart';
      bar.setAttribute('aria-label', 'Calculation in progress');
      started = performance.now();
      panel.hidden = false;
      bar.removeAttribute('value'); // Indeterminate until actual solver progress is known.
      stage.textContent = 'Calculating planetary positions…';
      longRunning.hidden = true;
      tick();
      ticker = setInterval(tick, 1000);
    },
    update(message, fraction) {
      stage.textContent = String(message);
      if (Number.isFinite(fraction) && fraction >= 0 && fraction <= 1) {
        bar.max = 1;
        bar.value = fraction;
      } else bar.removeAttribute('value');
    },
    finish(message, successful = false) {
      stop();
      heading.textContent = successful ? 'Chart ready' : 'Calculation stopped';
      stage.textContent = String(message);
      longRunning.hidden = true;
      if (successful) { bar.max = 1; bar.value = 1; }
      else bar.removeAttribute('value');
      bar.setAttribute('aria-label', successful ? 'Calculation complete' : 'Calculation stopped');
      cancelHandler = null;
      cancel.disabled = true;
    },
    reset() {
      stop();
      panel.hidden = true;
      cancel.disabled = false;
    }
  };
  cancel.addEventListener('click', () => {
    if (typeof cancelHandler === 'function') cancelHandler();
  });
})();
