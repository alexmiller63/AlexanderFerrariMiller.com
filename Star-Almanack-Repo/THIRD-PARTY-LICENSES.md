# Third-Party Licenses

Star Almanack uses or validates against the following third-party software.

## eclipse-calc

Source: https://github.com/lkangas/eclipse-calc

Pinned diagnostic revision: `23853a8f9e0d1a25e026203207aca16de1d7bb31`

License: MIT

The following notice is reproduced from the LICENSE file at that pinned revision.

```text
MIT License

Copyright (c) 2026 komakallio

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Skyfield

Source: https://github.com/skyfielders/python-skyfield

Production version: `1.55`

License: MIT

Copyright notice in the upstream LICENSE: Copyright © 2013–2018 Brandon Rhodes.

Star Almanack imports Skyfield as a runtime dependency for JPL SPK reading,
apparent-position calculations, reference-frame conversion, and supported
major-planet magnitude calculations. Skyfield source code is not copied into
Star Almanack. The installed Python package retains its upstream license.

For astronomical/data provenance associated with the ephemeris calculation
path, see `EPHEMERIS-PROVENANCE.md`.

## Integration rule

Any Star Almanack production code that copies or incorporates a substantial
portion of a third-party implementation must retain the copyright and
permission notice required by that implementation's license. Files derived
from such an implementation must identify the upstream project and pinned
revision in their source header. Code independently implemented from published
astronomical methods should be documented separately so provenance is
unambiguous.
