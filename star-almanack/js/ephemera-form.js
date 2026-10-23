(() => {
  'use strict';
  const form = document.getElementById('ephemera-form');
  if (!form) return;
  const status = document.getElementById('ephemera-status');
  const results = document.getElementById('ephemera-results');
  const calculate = document.getElementById('ephemera-calculate');
  const cancel = document.getElementById('ephemera-cancel');
  const cityInput = document.getElementById('ephemera-city');
  const cityOptions = document.getElementById('ephemera-cities');
  let worker;
  let downloadURL;
  let cities;
  let loadingCities;
  let busy = false;
  form.elements.instant_utc.value = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
  const format = name => form.elements[name].value.trim();
  const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const zones = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];
  for (const zone of ['UTC', ...zones]) {
    const option = document.createElement('option');
    option.value = zone;
    document.getElementById('ephemera-zones').append(option);
  }
  async function loadCities() {
    if (!loadingCities) loadingCities = fetch('assets/ephemera/cities.json').then(response => {
      if (!response.ok) throw Error('City search could not load. You can still enter coordinates and a timezone.');
      return response.json();
    }).then(rows => {
      cities = rows.map(row => ({row, search: fold(row[1] + ' ' + row[2])}));
      return cities;
    }).catch(error => { loadingCities = null; throw error; });
    return loadingCities;
  }
  async function searchCities() {
    try {
      await loadCities();
      if (busy) return;
      cityOptions.replaceChildren();
      const query = fold(cityInput.value.trim());
      if (query.length < 2) return;
      const tokens = query.split(/\s+/);
      const matches = cities.filter(city => tokens.every(token => city.search.includes(token)))
        .sort((a, b) => Number(b.search.startsWith(query)) - Number(a.search.startsWith(query)))
        .slice(0, 12);
      for (const {row} of matches) {
        const button = document.createElement('button');
        button.type = 'button';
        button.textContent = `${row[1]} · ${row[6]}`;
        button.addEventListener('click', () => {
          if (busy) return;
          cityInput.value = row[1];
          form.elements.latitude.value = row[3];
          form.elements.longitude.value = row[4];
          form.elements.elevation_m.value = row[5];
          form.elements.timezone.value = row[6];
          cityOptions.replaceChildren();
          status.textContent = `Selected ${row[1]}. Rise/set use ${row[6]}.`;
          form.elements.instant_utc.focus();
        });
        cityOptions.append(button);
      }
      document.getElementById('city-note').textContent = matches.length ?
        'Choose a match to fill coordinates, estimated elevation and timezone. Showing up to 12 matches; add a country or region to narrow the search.' :
        'No matching city. Try another spelling, or enter coordinates and a timezone.';
    } catch (error) {
      document.getElementById('city-note').textContent = error.message;
    }
  }
  cityInput.addEventListener('input', searchCities);
  cityInput.addEventListener('focus', () => { loadCities().catch(error => {
    document.getElementById('city-note').textContent = error.message;
  }); });
  function validate() {
    const instant = format('instant_utc');
    const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?(Z|[+-]\d{2}:\d{2})$/.exec(instant);
    if (!match || !Number.isFinite(Date.parse(instant))) {
      throw Error('Enter a date/time with Z or an offset, e.g. 2026-10-22T21:00:00Z.');
    }
    const [, year, month, day, hour, minute, second = '0', offset] = match;
    if (+month < 1 || +month > 12 || +day < 1 ||
        +day > new Date(Date.UTC(+year, +month, 0)).getUTCDate() ||
        +hour > 23 || +minute > 59 || +second > 59 ||
        (offset !== 'Z' && (+offset.slice(1, 3) > 23 || +offset.slice(4) > 59))) {
      throw Error('Enter a valid calendar date and time.');
    }
    const utcYear = new Date(instant).getUTCFullYear();
    if (utcYear < 1900 || utcYear > 2099) throw Error('Current source kernels support years 1900–2099 (boundary dates depend on source coverage).');
    const values = {instant_utc: instant, timezone: format('timezone')};
    try { new Intl.DateTimeFormat('en', {timeZone: values.timezone}); }
    catch { throw Error('Choose a valid IANA timezone, e.g. America/Los_Angeles or UTC.'); }
    for (const [name, min, max] of [['latitude', -90, 90], ['longitude', -180, 180], ['elevation_m', -500, 10000]]) {
      const number = Number(format(name));
      if (!format(name) || !Number.isFinite(number) || number < min || number > max) {
        throw Error(`${name.replaceAll('_', ' ')} must be ${min} to ${max}.`);
      }
      values[name] = number;
    }
    return values;
  }
  function setBusy(value) {
    busy = value;
    calculate.disabled = value;
    cancel.hidden = !value;
    results.setAttribute('aria-busy', String(value));
    // Keep the submitted parameters visible and unchanged until the result arrives.
    for (const element of form.elements) if (element.tagName === 'INPUT') element.disabled = value;
    cityInput.disabled = value;
    document.getElementById('ephemera-location').disabled = value;
    for (const button of cityOptions.querySelectorAll('button')) button.disabled = value;
  }
  function render(data) {
    const localTime = new Intl.DateTimeFormat('en-US', {
      timeZone: data.timezone, hour: 'numeric', minute: '2-digit',
      hour12: true, timeZoneName: 'short'
    });
    const rows = document.getElementById('ephemera-rows');
    rows.replaceChildren();
    for (const body of data.bodies) {
      const row = document.createElement('tr');
      const name = document.createElement('th');
      name.scope = 'row';
      name.textContent = body.body[0].toUpperCase() + body.body.slice(1);
      row.append(name);
      for (const key of ['ra_hours', 'dec_deg', 'ecliptic_longitude_deg', 'ecliptic_latitude_deg', 'distance_au', 'altitude_deg', 'azimuth_deg']) {
        const cell = document.createElement('td');
        cell.textContent = body[key].toFixed(key === 'distance_au' ? 6 : 4);
        row.append(cell);
      }
      const events = document.createElement('td');
      if (body.rise_set.events.length) {
        for (const event of body.rise_set.events) {
          const line = document.createElement('div');
          line.textContent = `${event.type === 'rise' ? 'Rise' : 'Set'} ${localTime.format(new Date(event.utc))}`;
          line.title = `Local: ${event.local}; UTC: ${event.utc}`;
          events.append(line);
        }
      } else events.textContent = body.rise_set.state;
      row.append(events);
      rows.append(row);
    }
    const observer = data.observer;
    document.getElementById('ephemera-summary').textContent =
      `Positions: ${data.instant_utc}. Observer: ${observer.latitude}°, ${observer.longitude}°, ${observer.elevation_m} m. Rise/set: ${data.rise_set_local_date} in ${data.timezone}. Times are local, with the timezone shown beside each event.`;
    if (downloadURL) URL.revokeObjectURL(downloadURL);
    downloadURL = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2) + '\n'], {type: 'application/json'}));
    document.getElementById('ephemera-download').href = downloadURL;
    results.hidden = false;
    status.textContent = 'Calculation complete. All 11 bodies are shown below. Values remain provisional; see Method and limitations.';
    document.getElementById('results-heading').focus();
  }
  function stop() {
    if (worker) worker.terminate();
    worker = null;
    setBusy(false);
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (busy) return;
    try {
      const values = validate();
      results.hidden = true;
      setBusy(true);
      status.textContent = 'Starting the calculation engine…';
      if (!worker) {
        worker = new Worker('js/ephemera-worker.js');
        worker.onmessage = ({data}) => {
          if (data.type === 'progress') status.textContent = data.message;
          if (data.type === 'result') { setBusy(false); render(data.data); }
          if (data.type === 'error') {
            console.error(data.message);
            stop();
            const detail = data.message.trim().split('\n').filter(Boolean).pop();
            status.textContent = `Calculation failed: ${detail}. Check the inputs or retry.`;
          }
        };
        worker.onerror = () => { stop(); status.textContent = 'The calculation engine could not start. Please reload and retry.'; };
      }
      worker.postMessage(values);
    } catch (error) { stop(); status.textContent = error.message; }
  });
  cancel.addEventListener('click', () => { stop(); status.textContent = 'Calculation cancelled. Change the inputs and try again.'; });
  document.getElementById('ephemera-location').addEventListener('click', () => {
    if (!navigator.geolocation) { status.textContent = 'Your browser does not provide geolocation.'; return; }
    status.textContent = 'Requesting permission to fill your coordinates…';
    navigator.geolocation.getCurrentPosition(position => {
      if (busy) return;
      const {coords} = position;
      form.elements.latitude.value = coords.latitude.toFixed(6);
      form.elements.longitude.value = coords.longitude.toFixed(6);
      form.elements.elevation_m.value = Number.isFinite(coords.altitude) ? String(Math.max(-500, Math.min(10000, Math.round(coords.altitude)))) : '0';
      cityInput.value = '';
      cityOptions.replaceChildren();
      const zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
      form.elements.timezone.value = zone;
      status.textContent = `Coordinates filled. Timezone is your device's setting (${zone}); verify it for this location. Your coordinates stay on your device.`;
    }, () => { status.textContent = 'Location not available or permission not granted. Choose a city or enter coordinates.'; },
    {enableHighAccuracy: false, timeout: 12000, maximumAge: 300000});
  });
})();
