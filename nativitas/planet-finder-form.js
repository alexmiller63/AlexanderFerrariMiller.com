(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const generate = byId('finder-generate');
  const status = byId('finder-availability');
  const result = byId('finder-result');
  const progress = window.PlanetFinderProgress;
  let worker = null;
  let downloadURL = null;
  const toggles = byId('finder-toggles');
  const download = byId('finder-download');
  const downloadWrap = byId('finder-download-wrap');
  const modeKeys = {'1': 'greek', '2': 'latin', '3': 'mixed'};
  const modeLabels = {greek: 'Greek/Symbols', latin: 'English', mixed: 'Mixed Learner'};
  let charts = new Map();
  function showMode(mode) {
    const active = charts.get(mode);
    if (!active) return;
    for (const [key, svg] of charts) svg.style.display = key === mode ? '' : 'none';
    toggles.querySelectorAll('[data-bayer-mode]').forEach(button => {
      button.setAttribute('aria-pressed', String(modeKeys[button.dataset.bayerMode] === mode));
    });
    if (downloadURL) URL.revokeObjectURL(downloadURL);
    downloadURL = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(active)], {type: 'image/svg+xml'}));
    download.href = downloadURL;
    download.download = 'planet-finder-' + mode + '.svg';
  }
  toggles.querySelectorAll('[data-bayer-mode]').forEach(button => {
    button.addEventListener('click', () => showMode(modeKeys[button.dataset.bayerMode]));
  });
  function prepareChart(source, title, mode, instant) {
    const doc = new DOMParser().parseFromString(source, 'image/svg+xml');
    if (doc.querySelector('parsererror') || doc.documentElement.localName !== 'svg')
      throw Error('Chart returned invalid SVG; no chart was displayed.');
    const svg = document.importNode(doc.documentElement, true);
    // Replace the renderer's UTC subtitle inside the SVG, including exported charts.
    const subtitle = svg.querySelector('text[y="110"]');
    if (!subtitle) throw Error('Chart title is missing; no chart was displayed.');
    subtitle.textContent = title;
    subtitle.setAttribute('font-size', '20');
    // Keep long city names inside the chart without changing the layout solver.
    if (title.length > 110) {
      subtitle.setAttribute('textLength', '1280');
      subtitle.setAttribute('lengthAdjust', 'spacingAndGlyphs');
    }
    const metadata = document.createElementNS('http://www.w3.org/2000/svg', 'desc');
    metadata.textContent = modeLabels[mode] + ' · UTC instant: ' + instant;
    svg.prepend(metadata);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', 'Planet Finder · ' + title + ' · ' + modeLabels[mode]);
    svg.style.width = '100%';
    svg.style.height = 'auto';
    return svg;
  }

  // City choices resolve to IANA zones; the chart remains geocentric.
  const cities = [
    ['Los Angeles, California, USA','America/Los_Angeles'],
    ['Long Beach, California, USA','America/Los_Angeles'],
    ['San Bernardino, California, USA','America/Los_Angeles'],
    ['San Francisco, California, USA','America/Los_Angeles'],
    ['Seattle, Washington, USA','America/Los_Angeles'],
    ['Las Vegas, Nevada, USA','America/Los_Angeles'],
    ['Phoenix, Arizona, USA','America/Phoenix'],
    ['Denver, Colorado, USA','America/Denver'],
    ['Salt Lake City, Utah, USA','America/Denver'],
    ['Chicago, Illinois, USA','America/Chicago'],
    ['Dallas, Texas, USA','America/Chicago'],
    ['Houston, Texas, USA','America/Chicago'],
    ['New Orleans, Louisiana, USA','America/Chicago'],
    ['Minneapolis, Minnesota, USA','America/Chicago'],
    ['New York, New York, USA','America/New_York'],
    ['Manhattan, New York, USA','America/New_York'],
    ['Manhattan, NY','America/New_York'],
    ['New York City, NY','America/New_York'],
    ['Boston, Massachusetts, USA','America/New_York'],
    ['Washington, DC, USA','America/New_York'],
    ['Miami, Florida, USA','America/New_York'],
    ['Atlanta, Georgia, USA','America/New_York'],
    ['Detroit, Michigan, USA','America/Detroit'],
    ['Honolulu, Hawaii, USA','Pacific/Honolulu'],
    ['Anchorage, Alaska, USA','America/Anchorage'],
    ['Toronto, Canada','America/Toronto'],
    ['Vancouver, Canada','America/Vancouver'],
    ['Montreal, Canada','America/Toronto'],
    ['Mexico City, Mexico','America/Mexico_City'],
    ['Bogota, Colombia','America/Bogota'],
    ['Lima, Peru','America/Lima'],
    ['Buenos Aires, Argentina','America/Argentina/Buenos_Aires'],
    ['Sao Paulo, Brazil','America/Sao_Paulo'],
    ['London, United Kingdom','Europe/London'],
    ['Dublin, Ireland','Europe/Dublin'],
    ['Paris, France','Europe/Paris'],
    ['Berlin, Germany','Europe/Berlin'],
    ['Rome, Italy','Europe/Rome'],
    ['Madrid, Spain','Europe/Madrid'],
    ['Athens, Greece','Europe/Athens'],
    ['Moscow, Russia','Europe/Moscow'],
    ['Cairo, Egypt','Africa/Cairo'],
    ['Johannesburg, South Africa','Africa/Johannesburg'],
    ['Lagos, Nigeria','Africa/Lagos'],
    ['Dubai, United Arab Emirates','Asia/Dubai'],
    ['Mumbai, India','Asia/Kolkata'],
    ['Delhi, India','Asia/Kolkata'],
    ['Bangkok, Thailand','Asia/Bangkok'],
    ['Singapore, Singapore','Asia/Singapore'],
    ['Hong Kong, China','Asia/Hong_Kong'],
    ['Shanghai, China','Asia/Shanghai'],
    ['Beijing, China','Asia/Shanghai'],
    ['Tokyo, Japan','Asia/Tokyo'],
    ['Seoul, South Korea','Asia/Seoul'],
    ['Sydney, Australia','Australia/Sydney'],
    ['Melbourne, Australia','Australia/Melbourne'],
    ['Brisbane, Australia','Australia/Brisbane'],
    ['Perth, Australia','Australia/Perth'],
    ['Auckland, New Zealand','Pacific/Auckland']
  ];
  const cityInput = byId('finder-city');
  const cityList = byId('finder-cities');
  const zoneInput = byId('finder-zone');
  const cityMap = new Map(cities.map(([name, zone]) => [name.toLocaleLowerCase(), zone]));
  for (const [name] of cities) {
    const option = document.createElement('option');
    option.value = name;
    cityList.append(option);
  }
  cityInput.addEventListener('change', () => {
    const zone = cityMap.get(cityInput.value.trim().toLocaleLowerCase());
    if (zone) {
      zoneInput.value = zone;
      status.textContent = 'Time zone set to ' + zone + '. Historical clock rules will be applied for the selected date.';
    } else if (cityInput.value.trim()) {
      status.textContent = 'City not in suggestions. Choose a suggested city or enter its IANA time zone directly.';
    }
  });
  zoneInput.addEventListener('input', () => { cityInput.value = ''; });

  function clockParts(instant, zone) {
    const formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
    });
    return Object.fromEntries(formatter.formatToParts(instant).map(part => [part.type, part.value]));
  }
  function utcInstant() {
    const date = byId('finder-date').value, time = byId('finder-time').value;
    let zone = zoneInput.value.trim();
    if (cityInput.value.trim() && !cityMap.has(cityInput.value.trim().toLocaleLowerCase()))
      throw Error('Select a suggested city or clear the city field and enter an IANA time zone.');
    if (cityInput.value.trim()) zone = zoneInput.value = cityMap.get(cityInput.value.trim().toLocaleLowerCase());
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || !/^\d{2}:\d{2}$/.test(time))
      throw Error('Choose a valid date and local time.');
    if (date < '1900-01-01' || date > '2099-12-31') throw Error('Date outside 1900–2099.');
    try { new Intl.DateTimeFormat('en', {timeZone: zone}); }
    catch { throw Error('Choose a valid IANA time zone, such as UTC or America/Los_Angeles.'); }
    const wall = Date.parse(date + 'T' + time + ':00Z');
    if (!Number.isFinite(wall) || new Date(wall).toISOString().slice(0,16) !== date + 'T' + time)
      throw Error('Invalid calendar date or clock time.');
    const offsets = new Set();
    for (let h = -36; h <= 36; h += 6) {
      const probe = wall + h * 3600000, p = clockParts(probe, zone);
      offsets.add(Date.parse(p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute+':'+p.second+'Z') - probe);
    }
    const matches = [...offsets].map(offset => wall - offset).filter(instant => {
      const p = clockParts(instant, zone);
      return p.year+'-'+p.month+'-'+p.day+'T'+p.hour+':'+p.minute === date+'T'+time;
    }).sort((a,b)=>a-b);
    if (!matches.length) throw Error('This local time does not exist because of a clock change.');
    if (matches.length > 1) throw Error('This time occurs twice because of a clock change. Select UTC or an unambiguous time.');
    const iso = new Date(matches[0]).toISOString();
    if (iso.slice(0,4) < '1900' || iso.slice(0,4) > '2099') throw Error('UTC instant outside source-data coverage.');
    return iso;
  }
  function stop() {
    if (worker) worker.terminate();
    worker = null;
    generate.disabled = false;
  }
  generate.addEventListener('click', () => {
    let instant;
    try { instant = utcInstant(); }
    catch (error) { status.textContent = error.message; return; }
    const request = {calculator:'planet-finder', instant_utc:instant, mode:byId('finder-mode').value,
      timezone:zoneInput.value.trim(), city:cityInput.value.trim()};
    stop();
    charts = new Map();
    toggles.hidden = true;
    downloadWrap.hidden = true;
    if (downloadURL) URL.revokeObjectURL(downloadURL);
    downloadURL = null;
    result.hidden = true;
    result.replaceChildren();
    generate.disabled = true;
    status.textContent = 'Starting the calculation engine…';
    progress.start(() => {
      stop();
      progress.finish('Cancelled.');
      status.textContent = 'Calculation cancelled.';
    });
    worker = new Worker(new URL('../star-almanack/js/ephemera-worker.js?v=20261027-issue40', location.href));
    worker.onmessage = ({data}) => {
      if (data.type === 'progress') {
        progress.update(data.message);
        status.textContent = data.message;
      } else if (data.type === 'result') {
        stop();
        try {
          const completedTitle = data.data.local_title;
          if (!completedTitle) throw Error('Local chart title is missing; no chart was displayed.');
          const modes = request.mode === 'all' ? ['greek', 'latin', 'mixed'] : [request.mode];
          const prepared = new Map(modes.map(mode => {
            const source = data.data.charts?.[mode];
            if (!source) throw Error('A requested notation mode is missing; no chart was displayed.');
            return [mode, prepareChart(source, completedTitle, mode, request.instant_utc)];
          }));
          charts = prepared;
          result.replaceChildren(...charts.values());
          showMode(modes[0]);
          toggles.hidden = request.mode !== 'all';
          downloadWrap.hidden = false;
          result.hidden = false;
          progress.finish('Chart generated.', true);
          status.textContent = 'Planet Finder generated for ' + completedTitle + '. UTC instant: ' + request.instant_utc + '.';
        } catch (error) {
          progress.finish('Calculation unsuccessful.');
          status.textContent = error.message;
        }
      } else if (data.type === 'error') {
        stop();
        progress.finish('Calculation unsuccessful.');
        status.textContent = 'No chart was produced. ' + data.message +
          ' Some dates cannot be rendered because all labels must fit without overlap.';
      }
    };
    worker.onerror = event => {
      stop();
      progress.finish('Calculation unsuccessful.');
      status.textContent = 'The calculation worker failed to start or load: ' + (event.message || 'Unknown error') + (event.filename ? ' (' + event.filename.split('/').pop() + ':' + event.lineno + ')' : '') + '. No chart was produced.';
      event.preventDefault();
    };
    worker.postMessage(request);
  });
})();
