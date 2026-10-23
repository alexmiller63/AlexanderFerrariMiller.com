/* The engine, packages and source kernels are all served by this site. */
'use strict';
const assets = new URL('../assets/ephemera/', self.location.href).href;
let ready;
const progress = message => self.postMessage({type: 'progress', message});
async function bytes(name) {
  const response = await fetch(new URL(name, assets));
  if (!response.ok) throw Error(`Could not load ${name} (${response.status}). Please retry.`);
  return new Uint8Array(await response.arrayBuffer());
}
async function initialize() {
  progress('Loading the calculation engine… The first visit downloads about 60 MB.');
  importScripts(assets + 'pyodide/pyodide.js');
  const python = await loadPyodide({indexURL: assets + 'pyodide/',
    stdout: message => {
      if (message.startsWith('COMPUTED ')) progress(message.replace('COMPUTED ', 'Calculated '));
    }});
  await python.loadPackage('numpy');
  progress('Loading the local astronomy data…');
  python.FS.mkdirTree('/app/.cache/skyfield');
  for (const name of ['application.zip', 'de440s.bsp', 'ceres_1900_2100.bsp']) {
    const data = await bytes(name);
    python.FS.writeFile(name.endsWith('.bsp') ? '/app/.cache/skyfield/' + name : '/app/' + name, data);
  }
  await python.runPythonAsync(`
import sys, zipfile, json
from datetime import datetime
with zipfile.ZipFile('/app/application.zip') as archive:
    archive.extractall('/app')
sys.path[:0] = ['/app/tools', '/app/site-packages']
from generate_observer_ephemera import calculate
from star_almanack_ephemeris import StarAlmanackEphemeris
engine = StarAlmanackEphemeris('/app/.cache/skyfield')
`);
  return python;
}
self.onmessage = async event => {
  try {
    ready = ready || initialize().catch(error => { ready = null; throw error; });
    const python = await ready;
    progress('Calculating positions and local-day rise/set times…');
    python.globals.set('request_json', JSON.stringify(event.data));
    const result = await python.runPythonAsync(`
request = json.loads(request_json)
json.dumps(calculate(datetime.fromisoformat(request['instant_utc'].replace('Z', '+00:00')),
    request['latitude'], request['longitude'], request['elevation_m'], request['timezone'], engine=engine))
`);
    self.postMessage({type: 'result', data: JSON.parse(result)});
  } catch (error) {
    self.postMessage({type: 'error', message: String(error.message || error)});
  }
};
