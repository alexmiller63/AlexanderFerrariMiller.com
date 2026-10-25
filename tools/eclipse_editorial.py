"""Shared reader-facing eclipse explanations; no ephemeris calculations."""
import html
import json
import re
from datetime import datetime, timezone

ARISTOTLE_QUOTE = "As it is, the shapes which the moon itself each month shows are of every kind—straight, gibbous, and concave—but in eclipses the outline is always curved: and, since it is the interposition of the earth that makes the eclipse, the form of this line will be caused by the form of the earth’s surface, which is therefore spherical."

ARISTOTLE = "https://classics.mit.edu/Aristotle/heavens.2.ii.html"

# Explain both the geometry and the experience, rather than merely naming a type.
EXPLANATIONS = {
    ("lunar", "partial"): (
        "Earth passes between the Sun and the full Moon. Part of the Moon enters the umbra, "
        "Earth’s dark central shadow, while the rest stays outside it. A curved dark bite "
        "advances across the lunar surface; the Moon never becomes completely immersed.",
        "Follow the shadow’s curved edge as it crosses familiar lunar features. Compare the "
        "bright portion with the shadowed portion through binoculars, then watch the Moon "
        "emerge again. The gradual change gives you time to see the geometry unfold.",
    ),
    ("lunar", "total"): (
        "Earth passes between the Sun and the full Moon, and the entire Moon enters the "
        "umbra, Earth’s dark central shadow. Some sunlight still reaches the Moon after "
        "passing through Earth’s atmosphere, which preferentially scatters blue light and "
        "bends redder light into the shadow. The eclipsed Moon can glow copper or red; its "
        "brightness and color vary with atmospheric conditions.",
        "Watch Earth’s curved shadow advance during the partial phases. During totality, "
        "compare the Moon’s colors and brightness across its disk and notice how nearby "
        "stars become easier to see as moonlight fades. Watch the bright rim return as "
        "the Moon begins leaving the umbra.",
    ),
    ("lunar", "penumbral"): (
        "The full Moon passes through Earth’s penumbra, the outer shadow where Earth blocks "
        "only part of the Sun. It misses the dark central umbra. The effect is a subtle "
        "shading of the lunar disk rather than a sharp dark bite or a total eclipse’s red glow.",
        "Look for a gentle uneven dimming near greatest eclipse, especially on the side "
        "nearest the umbra. A shallow penumbral eclipse can be difficult to detect by eye; "
        "photographs taken with the same exposure before and during the event can make "
        "the difference easier to compare.",
    ),
    ("solar", "partial"): (
        "The Moon passes between Earth and the Sun, but their alignment is not close enough "
        "for the Moon’s central shadow to reach Earth. From the visible region the Moon "
        "covers part of the Sun, leaving a bright crescent. No location sees totality or "
        "a complete ring during this event.",
        "With proper solar protection, follow the changing solar crescent. A pinhole "
        "projector can show its shape indirectly; small gaps between leaves may also "
        "project crescent-shaped images onto the ground. The amount covered depends "
        "on your location.",
    ),
    ("solar", "annular"): (
        "The Moon passes in front of the Sun but appears too small to cover it completely. "
        "Along the narrow path of annularity, a bright ring of the Sun remains around the "
        "Moon. Outside that path, observers in the wider visibility region see a partial "
        "eclipse. The Sun’s bright surface is never completely hidden.",
        "From the annular path, watch the crescent become a ring through approved solar "
        "viewers or a properly filtered instrument. Elsewhere, follow the crescent’s "
        "changing shape. The ring is a direct demonstration that the Sun and Moon’s "
        "apparent sizes change with their distances.",
    ),
    ("solar", "total"): (
        "The Moon passes between Earth and the Sun and completely covers the Sun’s bright "
        "surface for observers inside a narrow path of totality. The much fainter outer "
        "atmosphere, the corona, becomes visible around the Moon. Observers outside that "
        "path but within the wider visibility region see a partial eclipse.",
        "Inside the path of totality, look for the corona’s delicate structure and the "
        "sudden change in daylight. Notice the surrounding sky and horizon as well as "
        "the eclipsed Sun. Outside the totality path, follow the changing crescent with "
        "proper solar protection; totality does not occur at every viewing location.",
    ),
    ("solar", "hybrid"): (
        "The Moon’s apparent size is very close to the Sun’s. Earth’s curvature changes "
        "the distance to the Moon enough that some places along the central path see a "
        "total eclipse and others see an annular ring. Outside the central path, the "
        "wider visibility region sees a partial eclipse.",
        "Check which phase your particular location receives before planning to watch. "
        "This rare geometry makes Earth’s curvature part of the spectacle: the same "
        "eclipse can hide the Sun completely at one location and leave a ring at another.",
    ),
}


def load_events(root):
    """Keep calculated catalog values authoritative; retain earlier calculation records."""
    path = root / "generated/eclipse-catalog/eclipses-2025-2036.json"
    events = {e["id"]: dict(e) for e in json.loads(path.read_text())["eclipses"]}
    source = root / "eclipse.yaml"
    if source.exists():
        # This repository's Calendar source uses flat, quoted publication fields.
        # Do not interpret nested geometry or substitute these notes for catalog times.
        for block in re.split(r"(?m)^  - id: ", source.read_text())[1:]:
            day = re.search(r"(?m)^    date: (\d{4}-\d{2}-\d{2})$", block)
            kind = re.search(r"(?m)^    kind: (solar|lunar)$", block)
            if not day or not kind:
                continue
            eid = f"ECL-{day[1]}-{kind[1][0].upper()}"
            if eid not in events:
                continue
            # Keep the earlier numerical calculation, excluding borrowed publication fields.
            calculation = re.sub(r'(?m)^    (?:magnitude|visibility|observing_note):.*\n?', '', block)
            events[eid]["earlier_calculation"] = "  - id: " + calculation.rstrip()
            events[eid]["earlier_method"] = source.read_text().split("\neclipses:", 1)[0]
    return events


def explanation(event):
    key = (event["kind"].lower(), event["type"].lower())
    if key not in EXPLANATIONS:
        raise ValueError(f"Unsupported eclipse type: {key}")
    return EXPLANATIONS[key]


def title(event):
    return f"{event['type'].capitalize()} {event['kind']} eclipse"


def observing(event):
    if event["kind"] == "lunar":
        return ("A lunar eclipse is safe to watch directly, with binoculars, or through a "
                "telescope. You can see a phase only while the Moon is above your horizon; "
                "clouds and twilight also affect the view.")
    text = ("Use eclipse glasses or a handheld solar viewer meeting ISO 12312-2 for direct "
            "viewing. Ordinary sunglasses are not suitable. Binoculars, cameras, and "
            "telescopes require purpose-made solar filters secured over the front of "
            "the optics; never look through them using eclipse glasses alone.")
    if event["type"] in ("total", "hybrid"):
        text += (" Only at a location experiencing totality, while the Sun’s bright surface "
                 "is completely covered, may you look directly without a solar viewer. "
                 "Replace it before the bright surface reappears.")
    else:
        text += " Keep solar protection in place throughout this eclipse, including any annular ring."
    return text


def history(event):
    if event["kind"] != "lunar" or event["type"] == "penumbral":
        return ""
    return ("More than 2,300 years ago, Aristotle used the curved shadow seen in lunar "
            "eclipses to argue that Earth is spherical. Watch that curved bite during "
            "the partial phases: you can see the same evidence he described.")


def render_history(event):
    context = history(event)
    if not context:
        return ""
    return (paragraphs([context]) +
            f'<blockquote><p>{html.escape(ARISTOTLE_QUOTE)}</p></blockquote>'
            '<p class="eclipse-quotation-credit">—Aristotle, <cite>On the Heavens</cite>, '
            'Book II, chapter 14; translated by J. L. Stocks.</p>')




def utc_parts(value):
    """Separate the UTC date and clock for readable display."""
    instant = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    instant = instant.astimezone(timezone.utc)
    return f"{instant.strftime('%B')} {instant.day}, {instant.year}", instant.strftime("%H:%M:%S")


def format_utc(value):
    if not value:
        return "Not available"
    try:
        day, clock = utc_parts(value)
    except ValueError:
        return str(value)
    return f"{day} at {clock} UTC"


def utc_cell(value):
    day, clock = utc_parts(value)
    return (f'<time datetime="{html.escape(str(value), quote=True)}">'
            f'<span class="utc-date">{html.escape(day)}</span>'
            f'<span class="utc-clock">{clock} UTC</span></time>')


def facts(event):
    items = [("Greatest eclipse (UTC)", format_utc(event.get("greatest_utc")))]
    if event.get("position_source"):
        items.append(("Position source", event["position_source"]))
    if event.get("shadow_earth_radius_factor") is not None:
        items.append(("Effective Earth-radius factor for lunar shadow", str(event["shadow_earth_radius_factor"])))
    if event.get("magnitude"):
        definition = ("Umbral magnitude, measured along the Moon’s diameter; not the "
                      "fraction of its area covered." if event["kind"] == "lunar" else
                      "Solar magnitude, measured along the Sun’s diameter; not the fraction of its area covered.")
        items.append(("Magnitude", f"{event['magnitude']}. {definition}"))
    if event.get("visibility") and not event.get("central_path", {}).get("points"):
        items.append(("Visibility", event["visibility"]))
    return items


def sources(event):
    links = []
    if event["kind"] == "solar":
        links.append(("https://science.nasa.gov/eclipses/safety/", "NASA: solar viewing safety"))
    if history(event):
        links.append((ARISTOTLE, "Aristotle, On the Heavens, II.14"))
    if not links:
        return ""
    return '<p class="eclipse-sources"><strong>Sources:</strong> ' + " · ".join(
        f'<a href="{html.escape(url, quote=True)}">{html.escape(label)}</a>' for url, label in links) + '</p>'


def paragraphs(texts):
    return "".join(f"<p>{html.escape(text)}</p>" for text in texts if text)


def render_note(event, *, highlights=False):
    meaning, watching = explanation(event)
    circumstances = " ".join(f"{label}: {value}" for label, value in facts(event))
    if highlights:
        brief = meaning.split(". ")[0] + "."
        return paragraphs([circumstances, brief, "Safe to view directly." if event["kind"] == "lunar"
                           else "Proper solar protection is required; see the eclipse page for observing guidance."])
    return (paragraphs([circumstances, meaning, watching]) + render_history(event) +
            paragraphs([observing(event)]) + sources(event))


def render_visibility(event):
    if event['kind'] == 'lunar':
        return ('<section id="eclipse-visibility"><h2>Where to watch</h2><p>'
                'The calculated chart above maps where the Moon’s center is above the '
                'geometric horizon at penumbral ingress, greatest eclipse, and penumbral egress. '
                'These are three snapshots; they do not establish whole-event visibility or account '
                'for terrain, refraction, weather, or twilight.</p></section>')
    if event.get("central_path", {}).get("points"):
        from eclipse_path_display import render_central_path
        return render_central_path(event)
    return '<section id="eclipse-visibility"><h2>Where to watch</h2>' + paragraphs([
        "Star Almanack has not yet calculated geographic visibility for this event."
    ]) + '</section>'


def render_geometry(event):
    lunar = event["kind"] == "lunar"
    fields = {
        "axis_distance_km": ("Shadow-axis distance", "Moon-center distance from Earth’s shadow axis at greatest eclipse." if lunar else "Closest distance of the Sun–Moon shadow axis from Earth’s center at greatest eclipse."),
        "penumbra_margin_km": ("Penumbral margin", "Axis distance minus the sum of penumbral and lunar radii; a negative value indicates overlap." if lunar else "Axis distance minus the sum of Earth’s radius and the penumbral radius; negative indicates overlap in the engine’s geometry."),
        "central_margin_km": ("Umbral overlap margin" if lunar else "Shadow-axis margin", "Axis distance minus the sum of umbral and lunar radii; negative indicates umbral overlap, not necessarily totality." if lunar else "Axis distance minus Earth’s radius; negative means the shadow axis passes inside Earth’s radius."),
        "core_radius_km": ("Earth’s umbral radius" if lunar else "Signed central-shadow radius", "Radius of Earth’s umbra at the Moon’s projected distance behind Earth." if lunar else "Shadow-core radius at the plane of closest axis approach to Earth’s center. Positive denotes umbra; negative denotes antumbra."),
        "surface_core_radius_min_km": ("Minimum surface shadow-core radius", "Smallest sampled signed core radius where the shadow axis meets the near-side spherical Earth surface. Negative indicates annularity."),
        "surface_core_radius_max_km": ("Maximum surface shadow-core radius", "Largest sampled signed core radius along that surface path. Positive indicates totality. Opposite signs between the extrema indicate a hybrid eclipse."),
    }
    rows = []
    for key, (label, meaning) in fields.items():
        if key in event:
            value = str(event[key])
            rows.append(f'<tr><th scope="row">{html.escape(label)}<br><small>{key}</small></th>'
                        f'<td class="geometry-value">{html.escape(value)} km</td>'
                        f'<td>{html.escape(meaning)}</td></tr>')
    return ('<h2>Calculated geometry</h2><p>Stored catalog values at greatest eclipse. '
            'Signs and precision are retained as calculated.</p><div class="data-table-scroll">'
            '<table><thead><tr><th>Quantity</th><th>Value</th><th>Meaning</th></tr></thead>'
            '<tbody>' + ''.join(rows) + '</tbody></table></div>')


def record_downloads(event):
    """Downloadable records preserve the exact values formerly displayed inline."""
    record = {key: value for key, value in event.items()
              if key not in ("earlier_calculation", "earlier_method")}
    from eclipse_artwork import svg
    files = {f'{event["id"]}-shadow.svg': svg(event), f'{event["id"]}-record.json':
             json.dumps(record, indent=2, ensure_ascii=False) + "\n"}
    if event['kind'] == 'lunar':
        from lunar_eclipse_chart import downloads
        files.update(downloads(event))
    if event.get("earlier_calculation"):
        files[f'{event["id"]}-earlier-calculation.yaml'] = (
            event["earlier_method"].rstrip() + "\n\neclipses:\n" +
            event["earlier_calculation"].rstrip() + "\n")
    return files


def render_records(event):
    eid = html.escape(event["id"], quote=True)
    result = ('<h2>Calculation records</h2>'
              f'<p><a href="{eid}-record.json" download>Download complete stored record (JSON)</a></p>')
    if event.get("earlier_calculation"):
        result += (f'<p><a href="{eid}-earlier-calculation.yaml" download>'
                   'Download earlier calculation and method notes (YAML)</a></p>')
    return result


def render_contacts(event):
    contacts = event.get("contacts_utc", {})
    if isinstance(contacts, str):
        contacts = json.loads(contacts)
    labels = {"P1": "Penumbral phase begins", "U1": "Partial phase begins",
              "axis_entry": "Shadow axis enters Earth’s spherical surface",
              "axis_exit": "Shadow axis leaves Earth’s spherical surface",
              "U2": "Totality begins", "U3": "Totality ends", "U4": "Partial phase ends",
              "P4": "Penumbral phase ends", "global_begin": "Eclipse begins somewhere on Earth",
              "global_end": "Eclipse ends everywhere on Earth"}
    if not contacts:
        return ""
    timeline = {**contacts, "greatest_utc": event.get("greatest_utc")}
    labels["greatest_utc"] = "Greatest eclipse"
    rows = "".join(f"<tr><th scope=\"row\">{html.escape(labels.get(key, key))}<br><small>{html.escape(key)}</small></th>"
                   f"<td>{utc_cell(value) if value else 'Not available'}</td></tr>"
                   for key, value in sorted(timeline.items(), key=lambda kv: kv[1] or ""))
    durations = []
    pairs = (("P1", "P4", "Entire penumbral event"), ("U1", "U4", "Partial-or-total umbral phases"),
             ("U2", "U3", "Totality")) if event["kind"] == "lunar" else (
                 ("global_begin", "global_end", "Global event window; not duration at one location"),)
    for start, end, label in pairs:
        if contacts.get(start) and contacts.get(end):
            seconds = round((datetime.fromisoformat(contacts[end].replace("Z", "+00:00")) -
                             datetime.fromisoformat(contacts[start].replace("Z", "+00:00"))).total_seconds())
            sign = "−" if seconds < 0 else ""
            value = abs(seconds)
            durations.append(f'<li>{html.escape(label)} ({start}–{end}): '
                             f'{sign}{value // 3600} h {value % 3600 // 60} min {value % 60} s</li>')
    duration = ('<h3>Durations derived from the stored times</h3><ul>' + ''.join(durations) + '</ul>') if durations else ""
    qualifier = ("These lunar phases happen at the same instants for everyone; only phases "
                 "with the Moon above your horizon can be seen." if event["kind"] == "lunar" else
                 "These are global limits, not contact times or duration at your location.")
    return '<h2>Timing and phases</h2><p>All times are UTC. Convert both date and time to your local time.</p>' + paragraphs([qualifier]) + '<table><thead><tr><th>Phase</th><th>UTC</th></tr></thead><tbody>' + rows + '</tbody></table>' + duration


def render_page(event):
    from eclipse_artwork import render_artwork
    meaning, watching = explanation(event)
    heading = html.escape(title(event))
    details = "".join(f"<dt>{html.escape(label)}</dt><dd>{html.escape(value)}</dd>" for label, value in facts(event))
    past = ('<h2>Earth’s shape, written in shadow</h2>' + render_history(event)) if history(event) else ""
    return ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{heading} — Star Almanack</title>'
            '<style>body{max-width:760px;margin:2rem auto;padding:0 1rem;font:1.12rem/1.65 Georgia,serif;'
            'color:#202833;background:#fffdf8}h1,h2{line-height:1.2;color:#17344d}a{color:#245c86}'
            'dt{font-weight:bold}dd{margin:0 0 .75rem}table{width:100%;border-collapse:collapse}'
            'th,td{padding:.6rem;text-align:left;vertical-align:top;border-bottom:1px solid #ccc}'
            '.utc-date,.utc-clock{display:block}.utc-date{font-size:.88em}'
            '.utc-clock{white-space:nowrap;font-variant-numeric:tabular-nums}'
            '.data-table-scroll{overflow-x:auto}small{font-size:.75em;overflow-wrap:anywhere}'
            '.eclipse-map{display:block;width:100%;height:auto;margin:1rem 0}'
            '.geometry-value{white-space:nowrap;font-variant-numeric:tabular-nums}'
            '.calculation-record{white-space:pre-wrap;overflow-wrap:anywhere;font-size:.82em;'
            'padding:1rem;background:#f0ede5;border-radius:.3rem}'
            'blockquote{margin:1.25rem 0;padding:.2rem 1rem;border-left:3px solid #c5a45c}'
            '.eclipse-quotation-credit,.eclipse-sources{font-size:.9em}</style>'
            '</head><body><main><nav><a href="/star-almanack/">Star Almanack</a> / '
            '<a href="/almanack/eclipses/">Eclipses</a></nav>'
            f'<h1>{heading}</h1><p>{html.escape(event["date_utc"])}</p>' +
            render_artwork(event) + render_visibility(event) +
            '<h2>What this eclipse means</h2>' + paragraphs([meaning]) +
            '<h2>What to look for</h2>' + paragraphs([watching]) + past +
            '<h2>This event</h2><dl>' + details + '</dl>' +
            render_contacts(event) + render_geometry(event) +
            '<h2>Watching the eclipse</h2>' + paragraphs([observing(event)]) +
            render_records(event) +
            '<h2>Sources</h2>' + sources(event) +
            '<p>Explanatory text and eclipse calculations are original work by Star Almanack. The calculations use Sun, Earth, and Moon positions from <a href="https://ssd.jpl.nasa.gov/planets/eph_export.html">JPL’s DE440s ephemeris kernel</a>. Event times, shadow geometry, and the supplied central-path coordinates are calculated by Star Almanack from those positions.</p>'
            '</main></body></html>')
