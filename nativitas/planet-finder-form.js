(() => {
  'use strict';
  const byId = id => document.getElementById(id);
  const generate = byId('finder-generate');
  const status = byId('finder-availability');
  const result = byId('finder-result');
  const progress = window.PlanetFinderProgress;
  let worker = null;
  function clockParts(instant, zone) {
    const formatter = new Intl.DateTimeFormat('en-GB', {
      timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'
    });
    return Object.fromEntries(formatter.formatToParts(instant).map(part => [part.type, part.value]));
  }
  function utcInstant() {
    const date = byId('finder-date').value, time = byId('finder-time').value;
    const zone = byId('finder-zone').value.trim();
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
    stop();
    result.hidden = true;
    result.replaceChildren();
    generate.disabled = true;
    status.textContent = 'Starting the calculation engine…';
    progress.start(() => {
      stop();
      progress.finish('Cancelled.');
      status.textContent = 'Calculation cancelled.';
    });
    worker = new Worker(new URL('../star-almanack/js/ephemera-worker.js?v=20261027-planet-finder-1', location.href));
    worker.onmessage = ({data}) => {
      if (data.type === 'progress') {
        progress.update(data.message);
        status.textContent = data.message;
      } else if (data.type === 'result') {
        stop();
        progress.finish('Chart generated.');
        const doc = new DOMParser().parseFromString(data.data.svg, 'image/svg+xml');
        if (doc.querySelector('parsererror') || doc.documentElement.localName !== 'svg') {
          status.textContent = 'Chart returned invalid SVG; no chart was displayed.';
          return;
        }
        const svg = document.importNode(doc.documentElement, true);
        svg.style.width = '100%';
        svg.style.height = 'auto';
        result.append(svg);
        result.hidden = false;
        status.textContent = 'Planet Finder generated for ' + data.data.instant_utc + '.';
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
      status.textContent = 'The calculation engine encountered an error; no chart was produced.';
      event.preventDefault();
    };
    worker.postMessage({calculator:'planet-finder', instant_utc:instant, mode:byId('finder-mode').value});
  });
})();
