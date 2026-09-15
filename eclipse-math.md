## Eclipses

An eclipse is not inserted into the *Star Almanack* from a published eclipse table. It is calculated from the geometry of the Sun, Earth, and Moon.

The calculation begins with the same ephemerides used elsewhere in the Almanack.

For a solar eclipse, we first find a new moon:

\[
\lambda_{\rm Moon}-\lambda_{\odot}=0^\circ.
\]

For a lunar eclipse, we first find a full moon:

\[
\lambda_{\rm Moon}-\lambda_{\odot}=180^\circ.
\]

A new moon or full moon by itself is not enough. The Moon's orbit is tilted by about \(5^\circ\) to the ecliptic, so most syzygies miss the relevant shadow. An eclipse is possible only when the Moon is sufficiently near one of its orbital nodes.

### Solar-eclipse geometry

Let

\[
\mathbf{s}
\]

be the geocentric position vector of the Sun and

\[
\mathbf{m}
\]

the geocentric position vector of the Moon.

The direction of the shadow axis behind the Moon is

\[
\hat{\mathbf{u}}
=
\frac{\mathbf{m}-\mathbf{s}}
{\left|\mathbf{m}-\mathbf{s}\right|}.
\]

A point on the shadow axis can then be written

\[
\mathbf{x}(q)=\mathbf{m}+q\hat{\mathbf{u}}.
\]

The value of \(q\) that brings the axis nearest Earth's center is

\[
q_{\min}=-\mathbf{m}\cdot\hat{\mathbf{u}}.
\]

The corresponding distance of the shadow axis from Earth's center is

\[
\rho
=
\left|
\mathbf{m}
+
q_{\min}\hat{\mathbf{u}}
\right|.
\]

This is the fundamental geometric test. If the penumbral cone misses Earth, there is no solar eclipse. If it intersects Earth, a partial eclipse occurs somewhere on Earth. If the central shadow also reaches Earth, the eclipse is central.

Let \(R_{\odot}\), \(R_{\rm Moon}\), and \(R_{\oplus}\) be the radii of the Sun, Moon, and Earth, and let

\[
L=|\mathbf{m}-\mathbf{s}|
\]

be the Sun-to-Moon distance.

At a distance \(q\) behind the Moon, the radius of the central shadow is approximately

\[
r_{\rm core}
=
R_{\rm Moon}
-
q
\frac{R_{\odot}-R_{\rm Moon}}{L}.
\]

If

\[
r_{\rm core}>0,
\]

the umbra still exists there and a central intersection produces a total solar eclipse.

If

\[
r_{\rm core}<0,
\]

the umbral cone has already closed and the antumbra reaches Earth; a central intersection produces an annular eclipse.

The outer penumbral radius is approximately

\[
r_{\rm pen}
=
R_{\rm Moon}
+
q
\frac{R_{\odot}+R_{\rm Moon}}{L}.
\]

Contact times are found by treating the relevant cone-to-Earth tangencies as root-finding problems and solving for the instants when the corresponding boundaries first touch and finally leave Earth.

### Lunar-eclipse geometry

For a lunar eclipse we compare the Moon with Earth's shadow on the anti-solar side of Earth.

Let \(D_{\rm M}\) be the geocentric distance of the Moon and \(D_{\odot}\) the geocentric distance of the Sun.

At the Moon's distance, the physical radius of Earth's umbra is approximately

\[
R_{\rm U}
=
R_{\oplus}
-
D_{\rm M}
\frac{R_{\odot}-R_{\oplus}}
{D_{\odot}}.
\]

The corresponding penumbral radius is approximately

\[
R_{\rm P}
=
R_{\oplus}
+
D_{\rm M}
\frac{R_{\odot}-R_{\oplus}}
{D_{\odot}}.
\]

Their apparent angular radii, as seen from Earth at the Moon's distance, are

\[
u=\tan^{-1}\left(\frac{R_{\rm U}}{D_{\rm M}}\right)
\]

and

\[
p=\tan^{-1}\left(\frac{R_{\rm P}}{D_{\rm M}}\right).
\]

The Moon's angular radius is

\[
r_{\rm M}
=
\sin^{-1}
\left(
\frac{R_{\rm Moon}}{D_{\rm M}}
\right).
\]

Let

\[
d
\]

be the angular separation between the center of the Moon and the center of Earth's anti-solar shadow.

Then:

\[
d>p+r_{\rm M}
\]

means there is no eclipse;

\[
d\le p+r_{\rm M}
\]

means the Moon enters the penumbra;

\[
d\le u+r_{\rm M}
\]

means the Moon enters the umbra;

and

\[
d+r_{\rm M}\le u
\]

means the Moon is completely inside the umbra and the eclipse is total.

Each contact is again a root-finding problem. For example, first umbral contact is the instant satisfying

\[
d-(u+r_{\rm M})=0.
\]

The beginning and end of totality satisfy

\[
d-(u-r_{\rm M})=0.
\]

### 2026 independent calculation

Applying this procedure to every new moon and full moon in 2026 leaves four eclipse events:

- Feb 17: annular solar eclipse.
- Mar 3: total lunar eclipse.
- Aug 12: total solar eclipse.
- Aug 28: partial lunar eclipse.

These events are therefore outputs of the Almanack's Sun–Earth–Moon calculation, not copied entries from an external eclipse catalogue.

The numerical values stored in `eclipse.yaml` are a first-pass calculation. Before final publication they should be regression-tested against an independent implementation or published observations. The purpose of that comparison is validation of our calculation, not substitution for it.
