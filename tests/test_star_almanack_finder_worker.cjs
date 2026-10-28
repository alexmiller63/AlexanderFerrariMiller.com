const {test}=require('node:test');const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const vm=require('node:vm');const root=path.resolve(__dirname,'..');
test('real worker message contract returns every mode and local title atomically',async()=>{
  const messages=[];let pythonCode='';
  const python={globals:{set(){}},async runPythonAsync(code){pythonCode=code;return JSON.stringify({charts:{greek:'g',latin:'e',mixed:'m'},local_title:'local'});}};
  const context={self:{location:{href:'http://localhost/star-almanack/js/planet-finder-worker.js'},postMessage:x=>messages.push(x)},URL,console};
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root,'star-almanack/js/planet-finder-worker.js'),'utf8'),context);
  context.python=python;
  vm.runInContext('ready = Promise.resolve(python)',context);
  await context.self.onmessage({data:{calculator:'planet-finder',mode:'all',instant_utc:'1963-10-09T12:00:00Z',timezone:'America/New_York'}});
  assert.deepEqual(Object.keys(messages.at(-1).data.charts),['greek','latin','mixed']);
  assert.equal(messages.at(-1).data.local_title,'local');
  assert.match(pythonCode, /ZoneInfo/);
});
