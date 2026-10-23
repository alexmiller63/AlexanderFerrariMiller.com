(() => {
  'use strict';
  const scriptURL = document.currentScript.src;
  const form = document.getElementById('ephemera-form');
  if (!form) return;
  const status = document.getElementById('ephemera-status');
  const results = document.getElementById('ephemera-results');
  const calculate = document.getElementById('ephemera-calculate');
  const progressPanel = document.getElementById('ephemera-progress');
  const progressBar = document.getElementById('ephemera-progress-bar');
  const progressLabel = document.getElementById('ephemera-progress-label');
  const cancel = document.getElementById('ephemera-cancel');
  const cityInput = document.getElementById('ephemera-city');
  const cityOptions = document.getElementById('ephemera-cities');
  let worker;
  let downloadURL;
  let cities;
  let loadingCities;
  let busy = false;
  const format = name => form.elements[name].value.trim();
  const fold = value => value.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
  const zones = typeof Intl.supportedValuesOf === 'function' ? Intl.supportedValuesOf('timeZone') : [];
  for (const zone of ['UTC', ...zones]) {
    const option = document.createElement('option');
    option.value = zone;
    document.getElementById('ephemera-zones').append(option);
  }
  async function loadCities() {
    if (!loadingCities) loadingCities = fetch(new URL('../assets/ephemera/cities.json', scriptURL)).then(response => {
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
          refreshOccurrences();
          form.elements.local_date.focus();
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
  function clockParts(instant, zone) {
    const formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
    });
    return Object.fromEntries(formatter.formatToParts(instant).map(part => [part.type, part.value]));
  }
  function localInstants() {
    const zone = format('timezone');
    try { new Intl.DateTimeFormat('en', {timeZone: zone}); }
    catch { throw Error('Choose a valid time zone, e.g. America/Los_Angeles or UTC.'); }
    const date = format('local_date'), time = format('local_time');
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time)) {
      throw Error('Choose a valid local date and time.');
    }
    const wall = Date.parse(`${date}T${time}:00Z`);
    if (!Number.isFinite(wall) || new Date(wall).toISOString().slice(0, 16) !== `${date}T${time}`) {
      throw Error('Choose a valid local date and time.');
    }
    if (date < '1900-01-01' || date > '2099-12-31') throw Error('Choose a date from 1900 through 2099.');
    // Collect offsets on both sides of a possible clock change. Verify every
    // candidate against the chosen wall clock, independent of the device zone.
    const offsets = new Set();
    for (let hours = -36; hours <= 36; hours += 6) {
      const probe = wall + hours * 3600000;
      const p = clockParts(probe, zone);
      offsets.add(Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`) - probe);
    }
    return [...offsets].map(offset => wall - offset).filter(instant => {
      const p = clockParts(instant, zone);
      return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}` === `${date}T${time}:00`;
    }).sort((a, b) => a - b);
  }
  function refreshOccurrences() {
    const select = form.elements.time_occurrence;
    const previous = select.value;
    select.replaceChildren();
    document.getElementById('ephemera-repeat-label').hidden = true;
    let matches;
    try { matches = localInstants(); } catch { return []; }
    if (matches.length > 1) {
      document.getElementById('ephemera-repeat-label').hidden = false;
      const placeholder = document.createElement('option');
      placeholder.value = '';
      placeholder.textContent = 'Choose first or second occurrence';
      select.append(placeholder);
      const formatter = new Intl.DateTimeFormat('en-US', {
        timeZone: format('timezone'), hour: 'numeric', minute: '2-digit',
        hour12: true, timeZoneName: 'short'
      });
      matches.forEach((instant, index) => {
        const option = document.createElement('option');
        option.value = String(instant);
        option.textContent = `${index === 0 ? 'First' : 'Second'}: ${formatter.format(instant)} (${new Date(instant).toISOString().slice(11, 16)} UTC)`;
        select.append(option);
      });
      if (matches.some(instant => String(instant) === previous)) select.value = previous;
    }
    return matches;
  }
  function setNow() {
    try {
      const now = new Date();
      const p = clockParts(now, format('timezone'));
      form.elements.local_date.value = `${p.year}-${p.month}-${p.day}`;
      form.elements.local_time.value = `${p.hour}:${p.minute}`;
      const matches = refreshOccurrences();
      if (matches.length > 1) {
        form.elements.time_occurrence.value = String(matches.reduce((a, b) => Math.abs(b - now) < Math.abs(a - now) ? b : a));
      }
    } catch { status.textContent = 'Choose a valid time zone before using Now.'; }
  }
  for (const name of ['local_date', 'local_time', 'timezone']) {
    form.elements[name].addEventListener('input', refreshOccurrences);
    form.elements[name].addEventListener('change', refreshOccurrences);
  }
  document.getElementById('ephemera-now').addEventListener('click', setNow);
  setNow();
  function validate() {
    const matches = localInstants();
    refreshOccurrences();
    if (!matches.length) throw Error('That local time does not exist because the clocks change. Choose another time.');
    const chosen = matches.length === 1 ? matches[0] : Number(form.elements.time_occurrence.value);
    if (!matches.includes(chosen)) throw Error('This local time occurs twice. Choose the first or second occurrence below the date and time.');
    const instant = new Date(chosen).toISOString();
    const utcYear = new Date(chosen).getUTCFullYear();
    if (utcYear < 1900 || utcYear > 2099) throw Error('This instant is outside the source-data coverage. Choose another date or time.');
    const values = {instant_utc: instant, timezone: format('timezone')};
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
    for (const element of form.elements) if (['INPUT', 'SELECT'].includes(element.tagName)) element.disabled = value;
    cityInput.disabled = value;
    document.getElementById('ephemera-location').disabled = value;
    document.getElementById('ephemera-now').disabled = value;
    for (const button of cityOptions.querySelectorAll('button')) button.disabled = value;
  }
  function showProgress(message, completed) {
    progressPanel.hidden = false;
    progressLabel.textContent = Number.isFinite(completed) ?
      `${completed === 11 ? 'Complete — ' : ''}${completed} of 11 bodies calculated.` : 'Loading…';
    if (Number.isFinite(completed)) progressBar.value = completed;
    else progressBar.removeAttribute('value');
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
    showProgress('Complete — 11 of 11 bodies calculated.', 11);
    document.getElementById('results-heading').focus();
  }
  function stop() {
    if (worker) worker.terminate();
    worker = null;
    setBusy(false);
    progressPanel.hidden = true;
  }
  form.addEventListener('submit', event => {
    event.preventDefault();
    if (busy) return;
    try {
      const values = validate();
      results.hidden = true;
      setBusy(true);
      status.textContent = 'Starting the calculation engine…';
      showProgress('Preparing calculation…');
      if (!worker) {
        worker = new Worker(new URL('ephemera-worker.js?v=20261022-progress', scriptURL));
        worker.onmessage = ({data}) => {
          if (data.type === 'progress') {
            status.textContent = data.message;
            showProgress(data.message, data.completed);
          }
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
      refreshOccurrences();
      status.textContent = `Coordinates filled. Timezone is your device's setting (${zone}); verify it for this location. Your coordinates stay on your device.`;
    }, () => { status.textContent = 'Location not available or permission not granted. Choose a city or enter coordinates.'; },
    {enableHighAccuracy: false, timeout: 12000, maximumAge: 300000});
  });
})();
