# IAU constellation-boundary snapshot

This directory is the repository-owned snapshot of the IAU J2000 constellation boundary coordinate files used by Star Almanack calculations.

Normal Almanack builds MUST read these local files and MUST NOT download boundary data from a live reference website.

Source used by the historical computation: `https://iauarchive.eso.org/static/public/constellations/txt`

The snapshot should contain one lowercase `<abbr>.txt` file for each constellation, except Serpens, which uses `ser1.txt` and `ser2.txt`.

Reference data should be refreshed only by an explicit maintenance operation, reviewed, and committed. A missing snapshot file is a build error rather than permission to fetch from the network.
