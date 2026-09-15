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
    if (cell.dataset.sunSpecial === 'true') return 'visible';
    return sunAboveHorizon(cell, latitude) && cell.dataset.normalLabel === 'Naked eye'
      ? 'Daylight'
      : (cell.dataset.solarGlare === 'true' ? 'Solar glare' : cell.dataset.normalLabel);
  }

  function specialHtml(label) {
    return '<span class="text-symbol" role="img" aria-label="' + label + '" title="' + label + '">☉︎</span> ' + label;
  }

  function update(root) {
    const input = root.querySelector('[data-ephemeris-latitude]');
    if (!input) return;
    let latitude = Number(input.value);
    if (!Number.isFinite(latitude)) latitude = 45;
    latitude = Math.max(-90, Math.min(90, latitude));
    input.value = String(latitude);
    root.querySelectorAll('td.ephemeris-rise').forEach(function (cell) {
      cell.textContent = riseSet(cell, latitude)[0];
    });
    root.querySelectorAll('td.ephemeris-set').forEach(function (cell) {
      cell.textContent = riseSet(cell, latitude)[1];
    });
    root.querySelectorAll('td.ephemeris-observing').forEach(function (cell) {
      if (cell.dataset.sunSpecial === 'true') return;
      if (!cell._normalHTML) cell._normalHTML = cell.innerHTML;
      const status = observingStatus(cell, latitude);
      if (status === 'Daylight' || status === 'Solar glare') {
        cell.innerHTML = specialHtml(status);
      } else {
        cell.innerHTML = cell._normalHTML;
      }
    });
  }

  document.querySelectorAll('main').forEach(function (root) {
    const input = root.querySelector('[data-ephemeris-latitude]');
    if (!input) return;
    input.addEventListener('input', function () { update(root); });
    input.addEventListener('change', function () { update(root); });
    update(root);
  });
})();
