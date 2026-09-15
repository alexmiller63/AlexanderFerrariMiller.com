# The Mathematics of the Star Almanack

**About this file.** This file is the technical mathematical reference for the *Star Almanack*. It records the definitions, equations, astronomical models, numerical conventions, algorithms, and validation rules underlying the calculations used throughout the project. It is intended both to explain the mathematics and to make the calculations reproducible. The ordinary reader does not need this material in order to use the *Star Almanack*; the reader-facing explanation of the project's mathematics is maintained separately in `mathematics.md`.

## 1. Time and the Celestial Sphere

The apparent motion of the stars begins with a simple fact: Earth rotates.

Relative to the Sun, an average day is 24 hours long. Relative to the distant stars, however, Earth completes one rotation in approximately

$$

23^{\mathrm h}56^{\mathrm m}4^{\mathrm s}.

$$

This is the **sidereal day**.

Because Earth also travels around the Sun while it rotates, it must turn slightly more than one complete rotation for the Sun to return to the same position in the sky. The difference is approximately 4 minutes per day.

This produces one of the most useful rules in the Almanac:

> **At the same civil time, the stars appear approximately 4 minutes earlier each successive night.**

Equivalently, a particular star reaches the same position in the sky about 2 hours earlier after 1 month.

### Right Ascension and Declination

A star's position on the celestial sphere can be described using **right ascension** and **declination**.

Right ascension, written

$$

\alpha,

$$

is analogous to longitude on Earth. It is normally measured in hours, minutes, and seconds:

$$

0^{\mathrm h} \leq \alpha < 24^{\mathrm h}.

$$

Declination, written

$$

\delta,

$$

is analogous to latitude and is measured north or south of the celestial equator:

$$

-90^\circ \leq \delta \leq +90^\circ.

$$

A star therefore has celestial coordinates of the form

$$

(\alpha,\delta).

$$

These coordinates provide the starting point for calculating when a star culminates, when it is visible, and where it appears in the sky.

### Hour Angle

The **hour angle** of a celestial object measures how far Earth's rotation has carried the object from the local meridian.

If

$$

\theta

$$

is the local sidereal time and

$$

\alpha

$$

is the object's right ascension, then its hour angle is

$$

H=\theta-\alpha.

$$

When

$$

H=0,

$$

the object is on the local meridian. It is then said to **culminate**.

Thus culmination occurs when

$$

\theta=\alpha.

$$

This simple relationship is fundamental to the calculation of the stars' visible dates used throughout the *Star Almanack*.

## Ephemerides

An **ephemeris** is a table of calculated positions of an astronomical object at specified times.

The basic problem is straightforward to state:

> Given a particular instant, where is the object?

The calculation is more complicated because astronomical positions are not fixed. The Sun, Moon, and planets move continuously against the background stars, while even stellar coordinates change slowly because of effects such as precession and proper motion.

### Julian Date

Astronomical calculations benefit from representing time as a continuously increasing number rather than as a combination of years, months, days, hours, minutes, and seconds.

The standard astronomical system is the **Julian Date**, abbreviated JD.

Julian Date counts days continuously from an astronomical epoch. Fractions of a day represent the time within the day.

For example, a difference between 2 Julian Dates can be written simply as

$$

\Delta t = JD_2 - JD_1.

$$

If

$$

\Delta t = 1,

$$

the 2 instants are exactly 1 day apart.

If

$$

\Delta t = 0.5,

$$

they are 12 hours apart.

Thus calendar dates can first be converted into Julian Dates, calculations can be performed using ordinary arithmetic, and the results can then be converted back into calendar dates and times.

### Rounding Julian Dates at Civil Midnight

When a calculated Julian Date is converted back into a civil UTC time, the *Star Almanack* first rounds and normalizes the **instant itself** to the resolution that will be displayed, and only then decomposes that instant into a Gregorian date and a clock time.

That order is deliberate.

Suppose a computed instant lies less than half a second before midnight. At whole-second resolution, the correct result is not

**23:59:60**

and it is not

**86400 seconds on the previous day**.

It is

**00:00:00 on the following day.**

In symbols, if $JD$ is the computed Julian Date and the displayed resolution is 1 second, the implementation first forms an integer number of whole seconds,

$$

S=\left\lfloor 86400\,JD+\frac{1}{2}\right\rfloor,

$$

and then uses

$$

JD_{\mathrm{norm}}=\frac{S}{86400}.

$$

The normalized Julian Date is then converted into the Gregorian date and UTC clock time.

This makes the day boundary part of the arithmetic rather than a special repair performed afterward. Rounding across midnight naturally advances the civil date before the calendar is decomposed.

This detail is also a software-safety rule. An earlier implementation decomposed the calendar first, rounded the seconds afterward, and then attempted to repair a value of 86400 seconds by recursively calling the same conversion routine. At the exact boundary, the correction could leave the Julian Date unchanged. The routine therefore encountered the same condition again, called itself again, and eventually failed with an infinite-recursion error.

The Almanack now follows the stronger invariant:

> **Normalize the astronomical instant first; decompose it into date and time exactly once.**

The aggregate validation harness contains explicit regression cases on both sides of midnight, including values just below and just above the rounding threshold. These tests are release-blocking because every astronomical result that is eventually presented as a UTC timestamp depends on this conversion behaving correctly.

### Epochs

A celestial coordinate is meaningful only in relation to time.

For stars, coordinates are commonly given for a standard **epoch**, such as J2000.0. Because Earth's rotational axis slowly changes direction, the celestial coordinate grid changes with time.

This motion is called **precession**.

A star whose coordinates are given as

$$

(\alpha_0,\delta_0)

$$

at one epoch will therefore generally have slightly different coordinates

$$

(\alpha,\delta)

$$

at another epoch.

For sufficiently precise calculations, the coordinates must be transformed from the catalog epoch to the epoch of observation.

Stars may also possess **proper motion**: an actual change in their apparent direction caused by their motion through space relative to the Sun.

Thus a modern stellar position may require both

$$

\text{catalog position}

\rightarrow

\text{proper-motion correction}

\rightarrow

\text{precession correction}.

$$

### Moving Objects

For the Sun, Moon, and planets, the situation is different.

Their changing positions are not merely corrections to nearly fixed coordinates. Their motion across the celestial sphere is itself one of the quantities the ephemeris is intended to describe.

At a given time $t$, we can think of an ephemeris as providing a function

$$

(\alpha,\delta)=f(t),

$$

where $\alpha$ is right ascension and $\delta$ is declination.

For calculations involving the zodiac, it is often more useful to express the same position in ecliptic coordinates:

$$

(\lambda,\beta)=g(t),

$$

where $\lambda$ is ecliptic longitude and $\beta$ is ecliptic latitude.

Ecliptic longitude is particularly important because the Sun's annual motion, the zodiac, planetary positions, and lunar phase calculations can all be related naturally to the ecliptic.

### Interpolation

An ephemeris does not necessarily need to calculate and store a position for every possible instant.

Suppose an object's ecliptic longitude is known at 2 nearby times:

$$

\lambda_1=\lambda(t_1)

$$

and

$$

\lambda_2=\lambda(t_2).

$$

For sufficiently short intervals and sufficiently smooth motion, an intermediate value can be estimated by linear interpolation:

$$

\lambda(t)

=

\lambda_1

+

\frac{t-t_1}{t_2-t_1}

(\lambda_2-\lambda_1).

$$

More accurate work may require higher-order interpolation or direct recalculation of the object's position.

The principle, however, remains the same:

**calculate the astronomical position with sufficient precision for the purpose of the Almanack, then present the result in a form useful to the reader.**

The ephemeris is therefore part of the mathematical machinery underneath several other parts of the *Star Almanack*. Lunar phases require the positions of the Sun and Moon. Zodiac positions require ecliptic longitude. Horoscope calculations require the positions of the relevant astronomical bodies.

The tables may look simple.

The simplicity is deliberate.

## Lunar Phases

The phases of the Moon are a consequence of geometry.

The Moon does not generate its own visible light. One half of the Moon is illuminated by the Sun, and as the Moon moves around Earth we see different portions of that illuminated hemisphere.

For calculating the principal lunar phases, the important quantity is the angular separation of the Sun and Moon along the ecliptic.

Let

$$

\lambda_{\text{Moon}}

$$

be the Moon's apparent ecliptic longitude and

$$

\lambda_{\odot}

$$

be the Sun's apparent ecliptic longitude.

Define the elongation

$$

D =

\lambda_{\text{Moon}}

-

\lambda_{\odot}.

$$

Because longitude wraps around after $360^\circ$, we reduce the result modulo $360^\circ$:

$$

D =

(\lambda_{\text{Moon}}-\lambda_{\odot})

\bmod 360^\circ.

$$

The 4 principal lunar phases occur when this angle reaches particular values.

### New Moon

At new moon,

$$

D=0^\circ.

$$

The Sun and Moon have approximately the same ecliptic longitude.

From Earth, the illuminated hemisphere of the Moon faces predominantly away from us.

### First Quarter

At first quarter,

$$

D=90^\circ.

$$

The Moon has moved approximately one quarter of the way around its cycle relative to the Sun.

### Full Moon

At full moon,

$$

D=180^\circ.

$$

The Moon is approximately opposite the Sun in ecliptic longitude, and the hemisphere facing Earth is illuminated.

### Last Quarter

At last quarter,

$$

D=270^\circ.

$$

Equivalently, the Moon may be regarded as $90^\circ$ west of the Sun.

The sequence can therefore be summarized mathematically as

$$

0^\circ

\rightarrow

90^\circ

\rightarrow

180^\circ

\rightarrow

270^\circ

\rightarrow

360^\circ.

$$

At $360^\circ$, the cycle begins again at $0^\circ$.

## The Synodic Month

The interval from one new moon to the next is called the **synodic month**.

Its mean length is approximately

$$

29.53059\text{ days}.

$$

This is longer than the Moon's orbital period relative to the distant stars.

The reason is that Earth and the Moon are traveling around the Sun together. During the time the Moon completes one orbit relative to the stars, the Sun has moved eastward against the stellar background. The Moon must therefore travel farther before it again reaches the same angular relationship with the Sun.

The distinction is between the **sidereal month**, measured relative to the stars, and the **synodic month**, measured relative to the Sun.

Lunar phases depend upon the synodic cycle.

## Finding the Instant of a Phase

An ephemeris can provide the apparent ecliptic longitudes of the Sun and Moon as functions of time:

$$

\lambda_{\odot}(t)

$$

and

$$

\lambda_{\text{Moon}}(t).

$$

Their difference gives

$$

D(t)

=

\left(

\lambda_{\text{Moon}}(t)

-

\lambda_{\odot}(t)

\right)

\bmod 360^\circ.

$$

Finding a lunar phase then becomes a root-finding problem.

For a full moon, for example, we seek the time $t$ for which

$$

D(t)-180^\circ=0.

$$

For a first quarter, we seek

$$

D(t)-90^\circ=0.

$$

The calculation can first locate an interval containing the desired phase and then successively narrow that interval until the required precision is reached.

The final result can then be converted from astronomical time into the civil date and time presented in the *Star Almanack*.

Once again, the reader does not need to perform any of this mathematics.

The Almanack can simply say:

**Full Moon — Aug 28, 2026**

The equations explain where that simple statement comes from.

## The ISO Week Calendar

The familiar Gregorian calendar divides the year into months of unequal length. For an almanac organized around repeating weeks, another calendar is useful: the **ISO week-date calendar**.

An ISO date has 3 components:

$$

(\text{week-year},\text{week number},\text{weekday}).

$$

The weekdays are numbered

$$

1,2,3,4,5,6,7

$$

from Monday through Sunday.

Thus Monday is day 1 and Sunday is day 7.

### The First Week of the Year

The central rule is simple:

> **ISO week 1 is the week containing the first Thursday of the Gregorian year.**

An equivalent definition is that week 1 is the week containing January 4.

Because every ISO week begins on Monday, the beginning of the ISO year may occur in the final days of December of the preceding Gregorian year.

Similarly, the final ISO week may extend into the first days of January of the following Gregorian year.

This means that the ISO week-year of a date is not always the same as its Gregorian year.

For example, January 1 can sometimes belong to the final ISO week of the preceding year.

### Why Thursday?

Thursday provides an elegant way to determine which year owns a week.

Every Monday-through-Sunday week contains exactly 1 Thursday. The Gregorian year containing that Thursday determines the ISO week-year.

Equivalently, a week belongs to the year containing the majority of its days.

At least 4 of the week's 7 days must therefore fall within its ISO week-year.

### 52 or 53 Weeks

An ordinary ISO week-year contains

$$

52\times7=364

$$

days represented by 52 complete weeks.

Because a Gregorian year contains 365 days, or 366 in a leap year, the calendar cannot always fit into exactly 52 ISO weeks.

Some ISO years therefore contain a 53rd week.

An ISO year has 53 weeks when January 1 falls on a Thursday, or when a leap year begins on a Wednesday.

Thus

$$

W_{\max}\in\{52,53\}.

$$

### Calculating the ISO Week Number

Let $N$ be the ordinal day of the Gregorian year, with January 1 equal to 1.

Let $d$ be the ISO weekday number:

$$

1\leq d\leq7.

$$

A useful preliminary expression for the week number is

$$

W=

\left\lfloor

\frac{N-d+10}{7}

\right\rfloor.

$$

The floor function

$$

\lfloor x\rfloor

$$

means the greatest integer less than or equal to $x$.

Values near the beginning and end of the Gregorian year require checking whether the date actually belongs to the preceding or following ISO week-year.

That apparent complication is not an error in the system.

It is the feature that allows every ISO week to remain an intact Monday-through-Sunday unit.

### Why the Almanack Uses It

For the *Star Almanack*, the ISO calendar provides something the ordinary month calendar does not:

**a continuous sequence of complete, consistently numbered weeks.**

Astronomical events do not care whether a civil month contains 28, 29, 30, or 31 days. Observing plans are often naturally expressed in weeks.

The Gregorian calendar can tell us:

**Aug 17, 2026**

The ISO week calendar can tell us:

**2026-W34-1**

The first expression identifies a civil date.

The second tells us immediately that the date is Monday of week 34.

Both describe the same day.

They organize it differently.

The *Star Almanack* uses both because each answers a different question.

## DE441 and the Reduced Eclipse Kernel

The eclipse calculations in the *Star Almanack* use the JPL DE441 planetary and lunar ephemeris as an authoritative source of solar-system positions. DE441 contains considerably more information than an eclipse calculation necessarily requires. This raises a useful computational and scientific question:

> **How much of DE441 is actually necessary to reproduce the eclipse calculations used by the Star Almanack?**

Rather than assume that every body represented in the source ephemeris must be retained, the project constructs a reduced SPICE kernel containing only the bodies required for the calculation under test.

### The Sun–Earth–Moon Kernel

For the initial reduction experiment, the retained system is the Sun, Earth, and Moon, together with the necessary reference data required by SPICE to represent their positions correctly.

Everything else that can be removed without breaking that representation is deliberately excluded.

This is not an assertion that the other bodies exert no gravitational influence. DE441 has already incorporated the dynamical model used to generate its ephemerides. The reduced kernel is a subset of the resulting ephemeris data; it is not a new three-body numerical integration in which the rest of the Solar System has been assumed not to exist.

That distinction is essential.

The experiment asks whether the stored Sun–Earth–Moon trajectories needed by the *Star Almanack* can be extracted from DE441 without carrying the remainder of the large source kernel along with them.

### Size of the Reduction

The reduction should be measured rather than described merely as “large” or “small.”

STAR-ALMANACK-TODO-001 — Record the size of the complete DE441 source data used for the build.

STAR-ALMANACK-TODO-002 — Record the size of the particular DE441 source kernel from which the relevant records are extracted.

STAR-ALMANACK-TODO-003 — Record the size of the resulting reduced Sun–Earth–Moon kernel.

STAR-ALMANACK-TODO-004 — Calculate and record the percentage reduction relative to each appropriate source size.

These measurements serve two purposes. They quantify the practical storage advantage of the reduced kernel, and they make the experiment reproducible.

### What Has Been Removed?

The reduced kernel deliberately omits ephemeris records that are not required to obtain the Sun–Earth–Moon positions used by the eclipse calculation.

That immediately raises a deeper question: which bodies matter physically, which bodies matter computationally, and which bodies appear in astronomical datasets primarily because of historical convention?

The distinction is easy to overlook.

For example, Pluto has traditionally received individual treatment in major planetary ephemerides despite its present classification as a dwarf planet. Ceres, also a dwarf planet and considerably closer to Earth, does not necessarily receive equivalent treatment in simplified lists of “planetary” bodies.

The point is not that Ceres must therefore perturb an eclipse calculation more than Pluto. Gravitational influence depends on mass, distance, geometry, and the dynamical model. Rather, the comparison warns against treating a familiar list of named bodies as though the list itself were a physical law.

Pluto's presence can reflect the history of planetary astronomy as well as numerical necessity. Ceres provides a particularly interesting comparison because it was discovered by the Italian astronomer Giuseppe Piazzi in 1801, was initially regarded as a planet, was later grouped with the asteroids, and is now classified as a dwarf planet.

The *Star Almanack* therefore treats inclusion in a conventional astronomical list as a question to investigate, not as proof that the included body's contribution is important at the precision required for a particular calculation.

### Validation

A smaller file is useful only if it preserves the astronomical information required by the calculation.

The reduced kernel must therefore be tested against the unreduced DE441 data using the same eclipse calculation.

The comparison should use at least one eclipse whose calculation has already been independently validated. The same computational procedure should then be run using the full DE441 data and the reduced kernel.

STAR-ALMANACK-TODO-005 — Identify the eclipse or eclipses used for the full-versus-reduced validation.

STAR-ALMANACK-TODO-006 — Record the result calculated from the full DE441 data.

STAR-ALMANACK-TODO-007 — Record the result calculated from the reduced Sun–Earth–Moon kernel.

STAR-ALMANACK-TODO-008 — Record the numerical difference between the two results, including the relevant units and precision.

STAR-ALMANACK-TODO-009 — Define the acceptance tolerance before interpreting the comparison as a PASS or FAIL.

Only after this comparison has been performed should the project state that the reduced kernel is adequate for the eclipse calculations.

Until then, the reduced kernel is a successful data-reduction experiment awaiting astronomical validation.

### General Principle

The purpose of the experiment is broader than saving disk space.

Scientific software should distinguish between information that is present, information that is necessary, and information that has been retained merely because it was present in the original source.

The *Star Almanack* therefore follows a simple rule:

> **Do not remove astronomical information merely because it appears unnecessary. Test whether it is unnecessary.**

The reduced DE441 kernel turns that rule into an experiment. The source ephemeris supplies the authoritative trajectories. The reduced kernel isolates the information believed to be required. Eclipse calculations then provide the test.

The final authority is not the size of the file or the elegance of the reduction.

It is whether the sky comes out the same.

