(() => {
  'use strict';
  const form = document.getElementById('ephemera-form');
  if (!form) return;
  const status = document.getElementById('ephemera-status');
  const config = document.getElementById('ephemera-config');
  const workflow = 'https://github.com/alexmiller63/AlexanderFerrariMiller.com/actions/workflows/observer-ephemera.yml';
  const fields = ['instant_utc', 'latitude', 'longitude', 'elevation_m'];
  const btn = document.getElementById('ephemera-copy');
  const now = new Date();
  form.elements.instant_utc.value = now.toISOString().replace(/\.\d{3}Z$/, 'Z');

  const format = (name) => form.elements[name].value.trim();
  const validate = () => {
    const instant = format('instant_utc');
    if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:\d{2})$/.test(instant) || !Number.isFinite(Date.parse(instant))) {
      throw Error('Enter a date/time with Z or a timezone offset, e.g. 2026-10-22T21:00:00Z.');
    }
    const year = new Date(instant).getUTCFullYear();
    if (year < 1900 || year > 2100) throw Error('The current source kernels support years 1900–2100.');
    const lat = Number(format('latitude'));
    const lon = Number(format('longitude'));
    const elev = Number(format('elevation_m'));
    if (!Number.isFinite(lat) || Math.abs(lat) > 90 || !format('latitude')) throw Error('Latitude must be −90 to +90.');
    if (!Number.isFinite(lon) || Math.abs(lon) > 180 || !format('longitude')) throw Error('Longitude must be −180 to +180.');
    if (!Number.isFinite(elev) || elev < -500 || elev > 10000 || !format('elevation_m')) throw Error('Elevation must be −500 to 10,000 metres.');
    return Object.fromEntries(fields.map(x => [x, format(x)]));
  };
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    try {
      const values = validate();
      config.textContent = fields.map(x => x + ': ' + values[x]).join('\n');
      config.hidden = false;
      btn.hidden = false;
      status.textContent = 'Inputs ready. Open GitHub Actions, choose Run workflow, and enter these four values. Download the HTML report from the completed run.';
      document.getElementById('ephemera-run').href = workflow;
      document.getElementById('ephemera-run').focus();
    } catch (error) {
      status.textContent = error.message;
      config.hidden = true;
      btn.hidden = true;
    }
  });
  btn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(config.textContent);
      status.textContent = 'Inputs copied. Paste the values into the corresponding GitHub Actions fields.';
    } catch {
      status.textContent = 'Select and copy the values below; clipboard access is unavailable.';
    }
  });
  document.getElementById('ephemera-location').addEventListener('click', () => {
    if (!navigator.geolocation) { status.textContent = 'Your browser does not provide geolocation.'; return; }
    status.textContent = 'Requesting your permission to use your coordinates locally in this form…';
    navigator.geolocation.getCurrentPosition((p) => {
      form.elements.latitude.value = p.coords.latitude.toFixed(6);
      form.elements.longitude.value = p.coords.longitude.toFixed(6);
      form.elements.elevation_m.value = Number.isFinite(p.coords.altitude) ? String(Math.round(p.coords.altitude)) : '0';
      status.textContent = 'Coordinates filled locally. They have not been sent anywhere.';
    }, () => {
      status.textContent = 'Location not available or permission not granted. You can type coordinates manually.';
    }, { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 });
  });
})();
