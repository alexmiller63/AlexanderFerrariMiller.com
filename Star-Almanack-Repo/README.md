# star-almanack
An Natural Philosopher's Guide to the Night Sky

## ISO Week Calendar

Star Almanac should include the ISO week-numbering calendar as an additional way of organizing the year.

Under ISO 8601:

- weeks begin on Monday

- weeks are numbered `01` through `52` or `53`

- ISO week `01` is the week containing January 4

- an ISO week can straddle December and January

- the ISO week-numbering year therefore does not always begin on January 1

- dates near the beginning or end of a calendar year may belong to the adjacent ISO week-numbering year

For example, a date in early January can still belong to week `52` or `53` of the preceding ISO year, while a date in late December can belong to week `01` of the following ISO year.

Star Almanac should eventually display the ISO week number alongside the ordinary calendar date.

This provides a continuous week-by-week structure for the year and is especially useful for planning, observation schedules, recurring events, and comparing corresponding weeks between years.


# Star Almanack

## A Natural Philosopher’s Guide to the Night Sky

> The mathematics may be precise even when the reader's interface to the sky is deliberately simple.

Star Almanack is an astronomical almanack designed around the experience of looking at the sky.

It uses precise astronomical calculations underneath, but presents the results in terms that are useful to an observer: seasons, directions, familiar constellations, dates, times, and recognizable objects.

The reader should not need to know right ascension and declination to find Betelgeuse.

## The Basic Idea

Traditional astronomical references often describe objects using celestial coordinates.

Star Almanack takes a different approach.

For each important star, constellation, planet, Messier object, or astronomical event, the Almanack asks practical questions:

- What is it called?

- How is its name pronounced?

- When is it best visible?

- Where should I look?

- What will it look like?

- What familiar objects can help me find it?

Technical coordinate systems remain available to the calculations, but they do not have to dominate the reader's experience.

## Best Visibility

Star Almanack uses a specific definition of **best visibility** for stars and other objects with essentially fixed celestial coordinates.

An object reaches best visibility at the annual moment when it transits the local meridian at:

**9:00 PM local apparent solar time.**

This definition provides a single reproducible annual reference point rather than a vague statement such as "best seen in winter."

At meridian transit, the object's hour angle is 0, so:

\[

\mathrm{LST}=\alpha_{\text{object}}

\]

At 9:00 PM local apparent solar time, the apparent Sun has an hour angle of 9h:

\[

\mathrm{LST}=\alpha_\odot+9\mathrm{h}

\]

Therefore:

\[

\alpha_{\text{object}}=\alpha_\odot+9\mathrm{h}

\]

and:

\[

\boxed{\alpha_\odot=\alpha_{\text{object}}-9\mathrm{h}}

\]

The calculation therefore becomes:

1. Obtain the object's right ascension.

2. Subtract 9h, wrapping through 24h when necessary.

3. Find the annual instant when the apparent Sun reaches that right ascension.

4. Round that instant to the nearest calendar date.

5. Express the result using the Almanack's calendar conventions.

An important consequence of using **local apparent solar time** is that longitude drops out of the core calculation.

The Sun and the object themselves provide the clocks.

## Validation

The best-visibility calculation was initially tested against a set of bright stars.

The calculated dates were compared with established descriptions of the stars as winter, spring, summer, or autumn objects.

The initial test produced results consistent with the expected observing seasons.

A later reconstruction of the calculation was tested against 15 preserved results from the original work.

The reconstructed algorithm reproduced all 15 dates:

**15/15 PASS**

The preserved regression cases include:

- Aldebaran — Jan 12

- Rigel — Jan 21

- Capella — Jan 22

- Betelgeuse — Jan 31

- Sirius — Feb 13

- Procyon — Feb 27

- Pollux — Feb 28

- Regulus — Apr 8

- Spica — May 29

- Arcturus — Jun 11

- Antares — Jul 13

- Vega — Aug 15

- Albireo — Aug 29

- Altair — Sep 4

- Deneb — Sep 18

These dates now form a regression suite for future implementations of the calculation.

Any replacement implementation should reproduce them before being accepted.

## Expanded Test Set

The calculation was also applied to another 20 familiar astronomical objects: 10 stars and 10 Messier objects.

For 2026, the resulting best-visibility dates include:

- Canopus — Feb 7

- Alpha Centauri — Jun 16

- Achernar — Dec 3

- Acrux — May 15

- Bellatrix — Jan 24

- Fomalhaut — Oct 25

- Castor — Feb 26

- Alkaid — Jun 4

- Dubhe — Apr 23

- Polaris — Dec 16

- M31 Andromeda Galaxy — Nov 20

- M42 Orion Nebula — Jan 26

- M45 Pleiades — Jan 1

- M44 Beehive Cluster — Mar 15

- M13 Hercules Cluster — Jul 16

- M57 Ring Nebula — Aug 19

- M8 Lagoon Nebula — Aug 6

- M20 Trifid Nebula — Aug 6

- M27 Dumbbell Nebula — Sep 6

- M51 Whirlpool Galaxy — May 31

These produced numerous useful "it fits" checks.

Objects associated with Orion fall in the northern winter. The Sagittarius nebulae fall in summer. M13 falls in summer. M31 falls in late autumn. Familiar Big Dipper stars fall in the spring and early-summer portion of the calendar.

The expanded set therefore provides another useful test of the observational meaning of the calculation.

## ISO Week Calendar

Star Almanack uses the ISO 8601 week calendar as an important part of its date system.

For example:

**2026-W32-7**

means:

**2026, week 32, day 7**

which is Sunday, Aug 9, 2026.

Best-visibility dates can therefore be presented in ISO week-date form.

The detailed calendar convention will be explained in the Almanack's preface rather than repeatedly explained in individual entries.

## Zodiac Calendar

Star Almanack will also record the exact moment when the Sun enters each **zodiac sign**.

The zodiac signs are not treated as equivalent to the astronomical constellations bearing similar names.

The date containing an ingress becomes day 1 of that sign.

For example, when the Sun enters Libra, that date becomes:

**Libra 1**

The following date becomes:

**Libra 2**

and the count continues until the next zodiac ingress.

The exact ingress time will also be recorded.

This creates a secondary solar calendar tied directly to the Sun's annual motion.

## Pronunciation

Star and constellation names are often difficult to pronounce from their English spelling alone.

Star Almanack therefore uses the **International Phonetic Alphabet (IPA)**.

An entry may include multiple established English pronunciations when actual usage varies.

For example:

**Betelgeuse — α Orionis**

Pronunciation:

/ˈbiːtəldʒuːz/

/ˈbɛtəldʒuːz/

/ˈbɛtəldʒɜːz/

The Almanack does not need to manufacture a single "correct" English pronunciation when several established pronunciations exist.

Pronunciation conventions and the English accents represented by the transcriptions will be documented in the preface.

## Almanack Entries

Entries should remain compact.

The Almanack is not intended to look like a database dump.

A typical entry might resemble:

**Betelgeuse — α Orionis.** Pronunciation: /ˈbiːtəldʒuːz/, /ˈbɛtəldʒuːz/, /ˈbɛtəldʒɜːz/. A red supergiant and variable star in Orion, prominent in the northern winter sky.

Look for the conspicuously reddish-orange star marking Orion's shoulder. Best visibility: Jan 31, with the corresponding ISO week date supplied by the Almanack.

The precise astronomical machinery belongs underneath the entry rather than overwhelming it.

## Familiar Landmarks

Star Almanack assumes that many readers will begin with only a few recognizable patterns in the sky.

That is enough.

Familiar constellations and asterisms such as Orion and the Big Dipper can serve as landmarks from which less familiar objects are introduced.

The Almanack should help readers progressively build a mental map of the sky rather than requiring that map as a prerequisite.

## Precision Without Complexity

Star Almanack deliberately separates **computational precision** from **observational complexity**.

The software may use right ascension, apparent solar coordinates, precession models, epochs, and other astronomical machinery.

The reader can be told:

**Look south.**

**Look near Orion.**

**Look during northern winter.**

**This is the week when the object is best placed at 9:00 PM.**

This principle is related to a more general problem: how much information can be recovered when an observer has access only to simple distinctions such as up and down?

The internal model may be sophisticated.

The interface does not have to be.

## Reproducibility

Star Almanack calculations should be reproducible.

Astronomical source data, computational assumptions, rounding conventions, and algorithms should therefore be documented.

In particular, the best-visibility calculation currently specifies:

- meridian transit as the observing condition

- 9:00 PM local apparent solar time

- apparent solar right ascension

- object right ascension

- nearest-calendar-date rounding

- ISO week-date output

The existing regression cases should remain with the project so that future changes can be tested against known results.

## Future Work

Star Almanack can eventually include:

- bright stars

- constellations

- Messier objects

- planets

- the Moon

- meteor showers

- eclipses

- conjunctions

- oppositions

- solstices and equinoxes

- zodiac ingresses

- seasonal observing guides

- pronunciation data

- finding instructions based on familiar landmarks

The goal is not merely to publish astronomical data.

The goal is to translate the machinery of astronomy into the experience of walking outside, looking up, and knowing what you are looking at.

### What Makes a Most Ordinary Day?

A Most Ordinary Day should be deliberately unremarkable. It should not mark the beginning or end of a month, season, or year, and it should not fall conveniently in the middle of one. It should avoid solstices, equinoxes, major holidays, leap-day effects, and other dates that already carry obvious calendrical or astronomical significance.

Its time should be similarly ordinary. Midnight, noon, the top of an hour, and other neat boundaries should be avoided. A time such as 10:53 UTC is preferable precisely because neither the hour nor the minute looks specially chosen.

At the same time, a Most Ordinary Day must be useful. When converted into civil time around the world, it should demonstrate a variety of results. It should encounter both standard time and daylight-saving time where those systems are used, illustrate that different parts of the world can be on different calendar dates at the same instant, and work naturally with unusual civil-time offsets such as India's half-hour offset and Nepal's 45-minute offset.

The convention should also remain useful from year to year. A candidate should therefore avoid dates whose character changes substantially because of leap years or recurring clock changes.

No single candidate satisfying these requirements is uniquely the most ordinary. Choosing one by preference would give arbitrary importance to the chooser's taste. Star Almanack therefore selected several equally acceptable candidates and allowed a physical random process—a real quarter flipped twice—to make the final choice.

The 4 candidates were:

- **HH — February 7, 03:17 UTC**

- **HT — May 23, 18:41 UTC**

- **TH — August 9, 10:53 UTC**

- **TT — November 17, 22:29 UTC**

A real quarter was then flipped twice.

**First flip: Tails**

**Second flip: Heads**

The result was **TH**.

Therefore, the Most Ordinary Day is:

**August 9 at 10:53 UTC**

The Most Ordinary Day is thus carefully designed to be useful and deliberately prevented from being special.

