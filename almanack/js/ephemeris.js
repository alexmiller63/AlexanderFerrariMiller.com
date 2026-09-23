(function () {
  'use strict';

  const SUN_HORIZON_DEG = -0.8333;
  const OBSERVING_HOUR_ANGLE_DEG = 135.0;

  function formatLat(hours) {
    const totalMinutes = ((Math.round(((hours % 24) + 24) % 24 * 60) % 1440) + 1440) % 1440;
    const hour = Math.floor(totalMinutes / 60);
    const minute = totalMinutes % 60;
    return String(hour).padStart(2, '0') + ':' + String(minute).padStart(2, '0');
  }

  function riseSet(cell, latitude) {
    const ra = Number(cell.dataset.raHours);
    const dec = Number(cell.dataset.decDeg) * Math.PI / 180;
    const sunRa = Number(cell.dataset.sunRaHours);
    const horizon = Number(cell.dataset.horizonDeg) * Math.PI / 180;
    const phi = latitude * Math.PI / 180;
    const sinPhi = Math.sin(phi), cosPhi = Math.cos(phi);
    const sinDec = Math.sin(dec), cosDec = Math.cos(dec);
    const denominator = cosPhi * cosDec;

    if (Math.abs(denominator) < 1e-12) {
      return sinPhi * sinDec > Math.sin(horizon)
        ? ['always up', 'does not set']
        : ['does not rise', 'does not set'];
    }

    const cosine = (Math.sin(horizon) - sinPhi * sinDec) / denominator;
    if (cosine < -1) return ['always up', 'does not set'];
    if (cosine > 1) return ['does not rise', 'does not set'];

    const angle = Math.acos(Math.max(-1, Math.min(1, cosine))) * 180 / Math.PI / 15;
    return [
      formatLat(12 + ra - angle - sunRa),
      formatLat(12 + ra + angle - sunRa)
    ];
  }

  function sunAboveHorizon(cell, latitude) {
    const dec = Number(cell.dataset.sunDecDeg) * Math.PI / 180;
    const phi = latitude * Math.PI / 180;
    const hourAngle = OBSERVING_HOUR_ANGLE_DEG * Math.PI / 180;
    const altitude = Math.asin(
      Math.sin(phi) * Math.sin(dec)
      + Math.cos(phi) * Math.cos(dec) * Math.cos(hourAngle)
    ) * 180 / Math.PI;
    return altitude > SUN_HORIZON_DEG;
  }

  function observingStatus(cell, latitude) {
    if (cell.dataset.sunSpecial === 'true') return 'Visible';
    return sunAboveHorizon(cell, latitude) && cell.dataset.normalLabel === 'Naked eye'
      ? 'Daylight'
      : (cell.dataset.solarGlare === 'true' ? 'Solar Glare' : cell.dataset.normalLabel);
  }

  function currentNotationMode() {
    const pressed = document.querySelector('[data-bayer-mode][aria-pressed="true"]');
    if (pressed && (pressed.dataset.bayerMode === 'greek' || pressed.dataset.bayerMode === 'latin' || pressed.dataset.bayerMode === 'mixed')) {
      return pressed.dataset.bayerMode;
    }
    try {
      const saved = localStorage.getItem('star-almanack-bayer-mode');
      if (saved === 'greek' || saved === 'latin' || saved === 'mixed') return saved;
    } catch (_) {}
    return 'greek';
  }

  function specialHtml(label, mode) {
    const symbol = '<span class="text-symbol" role="img" aria-label="' + label + '" title="' + label + '">☉︎</span>';
    if (mode === 'greek') return symbol;
    if (mode === 'latin') return label;
    return symbol + ' ' + label;
  }

  function renderNormalObserving(cell, mode) {
    const greek = cell.dataset.greekHtml;
    const latin = cell.dataset.latin;
    const mixed = cell.dataset.mixedHtml;
    if (mode === 'greek' && greek) cell.innerHTML = greek;
    else if (mode === 'latin' && latin) cell.textContent = latin;
    else if (mode === 'mixed' && mixed) cell.innerHTML = mixed;
    else cell.innerHTML = cell._normalHTML || cell.innerHTML;
  }

  function update(root) {
    const input = root.querySelector('[data-ephemeris-latitude]');
    if (!input) return;
    let latitude = Number(input.value.replace('−', '-').trim());
    if (!Number.isFinite(latitude)) {
      input.setCustomValidity('Enter a latitude from -90 to +90.');
      input.reportValidity();
      return;
    }
    if (latitude < -90 || latitude > 90) {
      input.setCustomValidity('Latitude must be from -90 to +90.');
      input.reportValidity();
      return;
    }
    input.setCustomValidity('');
    input.value = String(latitude);
    root.querySelectorAll('td.ephemeris-rise').forEach(function (cell) {
      cell.textContent = riseSet(cell, latitude)[0];
    });
    root.querySelectorAll('td.ephemeris-set').forEach(function (cell) {
      cell.textContent = riseSet(cell, latitude)[1];
    });
    const mode = currentNotationMode();
    root.querySelectorAll('td.ephemeris-observing').forEach(function (cell) {
      if (cell.dataset.sunSpecial === 'true') return;
      if (!cell._normalHTML) cell._normalHTML = cell.innerHTML;
      const status = observingStatus(cell, latitude);
      if (status === 'Daylight' || status === 'Solar Glare') {
        cell.innerHTML = specialHtml(status, mode);
      } else {
        renderNormalObserving(cell, mode);
      }
    });
  }

  document.querySelectorAll('main').forEach(function (root) {
    const input = root.querySelector('[data-ephemeris-latitude]');
    if (!input) return;
    const apply = root.querySelector('[data-ephemeris-apply]');
    if (apply) apply.addEventListener('click', function () { update(root); });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'Enter') {
        event.preventDefault();
        update(root);
      }
    });
    document.querySelectorAll('[data-bayer-mode]').forEach(function (button) {
      button.addEventListener('click', function () { setTimeout(function () { update(root); }, 0); });
    });
    update(root);
  });
})();
