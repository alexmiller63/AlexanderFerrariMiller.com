"""Cross-check the browser converter against Python's ISO calendar."""
import datetime as dt
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CalendarConverterTests(unittest.TestCase):
    def test_iso_dates_and_published_destinations(self):
        cases = []
        for year in (1, 4, 99, 100, 400, 1900, 2000, 2024, 2025, 2026, 2027, 2028, 2100, 9999):
            day = dt.date(year, 1, 1)
            while day.year == year:
                iso = day.isocalendar()
                cases.append([year, day.month, day.day, iso.year, iso.week])
                if day == dt.date.max:
                    break
                day += dt.timedelta(days=1)
        script = r"""
const assert = require('node:assert/strict');
const fs = require('fs');
const {isoWeek} = require('./star-almanack/calendar-converter.js');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
for (const [y,m,d,iy,iw] of cases) {
  const result = isoWeek(y,m,d);
  assert.equal(result.year, iy, `${y}-${m}-${d}`);
  assert.equal(result.week, iw, `${y}-${m}-${d}`);
  assert.equal(Boolean(result.href), [2025,2026,2027].includes(iy));
  if (result.href) assert.ok(fs.existsSync('.' + result.href + 'index.html'));
}
for (const date of [[2025,2,29],[2026,4,31],[0,1,1],[2026,13,1],[2026,1,0],[2026,1,1.5]]) {
  assert.equal(isoWeek(...date), null);
}
assert.deepEqual([2025,2026,2027].map(y => isoWeek(y,1,16).week), [3,3,2]);
assert.equal(isoWeek(2028,1,1).href, '/almanack/2027/W52/');
assert.equal(isoWeek(2030,1,16).href, null);
"""
        result = subprocess.run(['node', '-e', script], cwd=ROOT,
                                input=json.dumps(cases), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_rendered_results_and_submit(self):
        script = r"""
const assert = require('node:assert/strict');
class Element {
  constructor() { this.children = []; }
  append(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
}
const results = new Element(), heading = new Element();
let submit;
const form = {elements: {
  month: {value:'1', selectedOptions:[{textContent:'January'}]},
  day: {value:'16'}, year: {value:''}
}, addEventListener: (type, fn) => { submit = fn; }, reportValidity: () => true};
global.document = {
 getElementById: id => ({'calendar-converter':form,'converter-results':results,'converter-heading':heading})[id],
 createElement: () => new Element()
};
require('./star-almanack/calendar-converter.js');
assert.equal(heading.textContent, 'January 16');
assert.equal(results.children.length, 5);
assert.equal(results.children.filter(c => c.children.some(e => e.href)).length, 3);
assert.equal(results.children.filter(c => c.children.some(e => (e.textContent || '').startsWith('Pending'))).length, 2);
form.elements.year.value = '2030';
submit({preventDefault(){}});
assert.equal(results.children.length, 6);
form.elements.month.value = '2';
form.elements.month.selectedOptions[0].textContent = 'February';
form.elements.day.value = '29';
submit({preventDefault(){}});
assert.ok(results.children.find(c => c.children[0].textContent === '2025').children[1].textContent.includes('does not occur'));
assert.ok(results.children.find(c => c.children[0].textContent === '2024').children[1].textContent.includes('week 09'));
"""
        result = subprocess.run(['node', '-e', script], cwd=ROOT, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == '__main__':
    unittest.main()
