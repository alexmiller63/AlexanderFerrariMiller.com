#!/usr/bin/env python3
"""Build the self-hosted browser runtime. Download once; reuse local inputs.

Run from the repository root. Generated assets are versioned with the site, so
visitors never query a third-party runtime, city API, or ephemeris service.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'star-almanack/assets/ephemera'
CACHE = ROOT / '.cache/ephemera-browser'
VERSION = '0.27.7'
CDN = f'https://cdn.jsdelivr.net/pyodide/v{VERSION}/full/'
PACKAGES = ['skyfield==1.55', 'jplephem==2.24', 'sgp4==2.27',
            'certifi==2026.2.25', 'tzdata==2025.2']


def download(url, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print('Downloading', url, flush=True)
        temporary = path.with_name(path.name + '.part')
        urlretrieve(url, temporary)
        temporary.replace(path)
    return path


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    runtime = OUTPUT / 'pyodide'
    runtime.mkdir(exist_ok=True)
    for name in ['pyodide.js', 'pyodide.asm.js', 'pyodide.asm.wasm',
                 'python_stdlib.zip', 'pyodide-lock.json']:
        shutil.copyfile(download(CDN + name, CACHE / name), runtime / name)
    lock = json.loads((runtime / 'pyodide-lock.json').read_text())
    required = set()

    def include(name):
        if name in required:
            return
        required.add(name)
        package = lock['packages'][name]
        for dep in package['depends']:
            include(dep)
        filename = package['file_name']
        path = download(CDN + filename, CACHE / filename)
        if hashlib.sha256(path.read_bytes()).hexdigest() != package['sha256']:
            raise ValueError('Runtime package checksum mismatch: ' + filename)
        shutil.copyfile(path, runtime / filename)
    include('numpy')
    wheels = CACHE / 'wheels'
    wheels.mkdir(exist_ok=True)
    missing = [spec for spec in PACKAGES if not list(wheels.glob(
        spec.replace('==', '-') + '-*-none-any.whl'))]
    if missing:
        subprocess.run([sys.executable, '-m', 'pip', 'download', '--disable-pip-version-check',
                        '--only-binary=:all:', '--platform', 'any', '--no-deps',
                        '--dest', str(wheels), *missing], check=True)
    # A deterministic archive holds the existing engine and pure-Python packages.
    members = {}
    for spec in PACKAGES:
        name, version = spec.split('==')
        matches = list(wheels.glob(f'{name}-{version}-*-none-any.whl'))
        if len(matches) != 1:
            raise ValueError('Expected a pure-Python wheel for ' + spec)
        with zipfile.ZipFile(matches[0]) as wheel:
            for entry in wheel.namelist():
                if not entry.endswith('/'):
                    members['site-packages/' + entry] = wheel.read(entry)
    for name in ['almanack_time.py', 'star_almanack_ephemeris.py', 'generate_observer_ephemera.py']:
        members['tools/' + name] = (ROOT / 'tools' / name).read_bytes()
    with zipfile.ZipFile(OUTPUT / 'application.zip', 'w', zipfile.ZIP_DEFLATED) as archive:
        for name, content in sorted(members.items()):
            entry = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, content)
    kernels = ROOT / '.cache/skyfield'
    for name, url in [
        ('de440s.bsp', 'https://ssd.jpl.nasa.gov/ftp/eph/planets/bsp/de440s.bsp'),
        ('ceres_1900_2100.bsp', 'https://naif.jpl.nasa.gov/pub/naif/generic_kernels/spk/asteroids/a_old_versions/ceres_1900_2100.bsp')
    ]:
        shutil.copyfile(download(url, kernels / name), OUTPUT / name)
    source = download('https://download.geonames.org/export/dump/cities15000.zip', CACHE / 'cities15000.zip')
    cities = []
    with zipfile.ZipFile(source) as archive:
        for line in archive.read('cities15000.txt').decode('utf-8').splitlines():
            parts = line.split('\t')
            # id, label, ASCII search name, latitude, longitude, elevation, timezone
            elevation = parts[15] or parts[16] or '0'
            cities.append([parts[0], f'{parts[1]}, {parts[10]}, {parts[8]}', parts[2],
                           float(parts[4]), float(parts[5]), max(-500, min(10000, int(elevation))), parts[17]])
    cities.sort(key=lambda row: (row[2].casefold(), row[1], row[0]))
    (OUTPUT / 'cities.json').write_text(json.dumps(cities, ensure_ascii=False, separators=(',', ':')) + '\n')
    (OUTPUT / 'NOTICE.txt').write_text('''Star Almanack browser ephemeris

Calculations: the site's Python engine using Skyfield 1.55 (MIT),
jplephem 2.24 (MIT), sgp4 2.27 (MIT), NumPy 2.0.2 (BSD-3-Clause),
Pyodide 0.27.7 (MPL-2.0) and Python 3.12 (PSF license).
certifi 2026.2.25: MPL-2.0. tzdata 2025.2: Apache-2.0; IANA data
is public domain. Package distributions include their license files.
Pyodide source and license: https://github.com/pyodide/pyodide/tree/0.27.7
NumPy source and license: https://github.com/numpy/numpy/tree/v2.0.2
Python license: https://docs.python.org/3.12/license.html

Source coefficients: JPL DE440s and NAIF-distributed Ceres 1900-2100
SPK. These files are reused locally, without a remote ephemeris API.
NAIF rules: https://naif.jpl.nasa.gov/naif/rules.html
See the repository's EPHEMERIS-PROVENANCE.md for calculation provenance.

City locations: adapted from GeoNames cities15000, CC BY 4.0.
https://www.geonames.org/ ; https://creativecommons.org/licenses/by/4.0/
Columns are selected, elevation is clamped to the supported input range,
and records are sorted. GeoNames does not endorse this application.
''')
    manifest = {str(path.relative_to(OUTPUT)): {'bytes': path.stat().st_size,
                'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
                for path in sorted(OUTPUT.rglob('*')) if path.is_file() and path.name != 'manifest.json'}
    (OUTPUT / 'manifest.json').write_text(json.dumps({'pyodide': VERSION, 'packages': PACKAGES,
                                                     'cities': len(cities), 'files': manifest}, indent=2) + '\n')
    print('Built', len(cities), 'cities;', sum(x['bytes'] for x in manifest.values()), 'bytes')


if __name__ == '__main__':
    build()
