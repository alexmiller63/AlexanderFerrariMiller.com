(function () {
  'use strict';

  const SUN_HORIZON_DEG = -0.8333;
  const DEFAULT_OBSERVER_TIME_HOURS = 21;

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

  function observerHourAngleDeg(root) {
    const input = root.querySelector('[data-ephemeris-observer-time]');
    const value = input ? input.value.trim() : '';
    const match = /^(\d{1,2}):(\d{2})$/.exec(value);
    if (!match) return (DEFAULT_OBSERVER_TIME_HOURS - 12) * 15;
    const hour = Number(match[1]), minute = Number(match[2]);
    if (hour > 23 || minute > 59) return (DEFAULT_OBSERVER_TIME_HOURS - 12) * 15;
    return ((hour + minute / 60) - 12) * 15;
  }

  function solarAltitudeDeg(cell, latitude, hourAngleDeg) {
    const dec = Number(cell.dataset.sunDecDeg) * Math.PI / 180;
    const phi = latitude * Math.PI / 180;
    const hourAngle = hourAngleDeg * Math.PI / 180;
    return Math.asin(
      Math.sin(phi) * Math.sin(dec)
      + Math.cos(phi) * Math.cos(dec) * Math.cos(hourAngle)
    ) * 180 / Math.PI;
  }

  function skyState(altitudeDeg) {
    if (altitudeDeg >= SUN_HORIZON_DEG) return 'Daylight';
    if (altitudeDeg >= -6) return 'Civil twilight';
    if (altitudeDeg >= -12) return 'Nautical twilight';
    if (altitudeDeg >= -18) return 'Astronomical twilight';
    return 'Night';
  }

  function targetAltitudeDeg(cell, latitude, solarHourAngleDeg) {
    const ra = Number(cell.dataset.raHours);
    const dec = Number(cell.dataset.decDeg) * Math.PI / 180;
    const sunRa = Number(cell.dataset.sunRaHours);
    if (!Number.isFinite(ra) || !Number.isFinite(dec) || !Number.isFinite(sunRa)) return null;
    const phi = latitude * Math.PI / 180;
    const hourAngle = (solarHourAngleDeg + (sunRa - ra) * 15) * Math.PI / 180;
    return Math.asin(
      Math.sin(phi) * Math.sin(dec)
      + Math.cos(phi) * Math.cos(dec) * Math.cos(hourAngle)
    ) * 180 / Math.PI;
  }

  function observingStatus(cell, latitude, hourAngleDeg) {
    const state = skyState(solarAltitudeDeg(cell, latitude, hourAngleDeg));
    if (cell.dataset.sunSpecial === 'true') return state;
    const targetAltitude = targetAltitudeDeg(cell, latitude, hourAngleDeg);
    if (targetAltitude !== null && targetAltitude < -0.5667) return 'Below horizon';
    if (state !== 'Night') return state;
    return cell.dataset.solarGlare === 'true' ? 'Solar Glare' : cell.dataset.normalLabel;
  }

  function currentNotationMode() {
    const aliases = {1:'1',2:'2',3:'3',greek:'1',latin:'2',english:'2',mixed:'3'};
    const pressed = document.querySelector('[data-bayer-mode][aria-pressed="true"]');
    if (pressed && aliases[pressed.dataset.bayerMode]) return aliases[pressed.dataset.bayerMode];
    try { return aliases[localStorage.getItem('star-almanack-bayer-mode')] || '1'; }
    catch (_) { return '1'; }
  }

  function specialHtml(label, mode) {
    const skyGlyphs = {
      'Civil twilight': ['civil-twilight', 'Sun between sunset/sunrise and 6° below the horizon'],
      'Nautical twilight': ['nautical-twilight', 'Sun 6° to 12° below the horizon'],
      'Astronomical twilight': ['astronomical-twilight', 'Sun 12° to 18° below the horizon'],
      'Night': ['night', 'Sun more than 18° below the horizon']
    };
    const glyph = skyGlyphs[label];
    const symbol = glyph
      ? '<img class="visibility-glyph" src="../../../assets/almanack/visibility-glyphs/masters/' + glyph[0] + '.svg" alt="' + label + '" aria-label="' + label + '" title="' + label + ' — ' + glyph[1] + '">'
      : '<span class="text-symbol" role="img" aria-label="' + label + '" title="' + label + '">☉︎</span>';
    if (mode === '1') return symbol;
    if (mode === '2') return label;
    return symbol + ' ' + label;
  }

  function observingNotation(cell) {
    return cell.querySelector('.observing-notation-item, .notation-rendered');
  }

  function renderNormalObserving(cell, mode) {
    const item = observingNotation(cell);
    if (!item) return;
    const greek = item.dataset.greek;
    const latin = item.dataset.latin;
    const mixed = item.dataset.mixed;
    if (mode === '1' && greek) item.innerHTML = greek;
    else if (mode === '2' && latin) item.textContent = latin;
    else if (mode === '3' && mixed) item.innerHTML = mixed;
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
    const hourAngleDeg = observerHourAngleDeg(root);
    root.querySelectorAll('td.ephemeris-observing').forEach(function (cell) {
      const status = observingStatus(cell, latitude, hourAngleDeg);
      if (status === 'Daylight' || status === 'Civil twilight' || status === 'Nautical twilight' || status === 'Astronomical twilight' || status === 'Night' || status === 'Solar Glare' || status === 'Below horizon') {
        const item = observingNotation(cell);
        if (item) item.innerHTML = specialHtml(status, mode);
        else cell.innerHTML = specialHtml(status, mode);
      } else {
        renderNormalObserving(cell, mode);
      }
    });
  }

  document.querySelectorAll('main').forEach(function (root) {
    const input = root.querySelector('[data-ephemeris-latitude]');
    if (!input) return;
    const timeInput = root.querySelector('[data-ephemeris-observer-time]');
    const apply = root.querySelector('[data-ephemeris-apply]');
    if (apply) apply.addEventListener('click', function () { update(root); });
    if (timeInput) timeInput.addEventListener('change', function () { update(root); });
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
