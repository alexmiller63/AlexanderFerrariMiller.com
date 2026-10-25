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
    """Keep numerical catalog data authoritative; add existing Calendar publication notes."""
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
            for field in ("magnitude", "visibility", "observing_note"):
                value = re.search(rf'(?m)^    {field}: "([^"\n]*)"$', block)
                if value:
                    events[eid][field] = value[1]
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
    if event.get("magnitude"):
        definition = ("Umbral magnitude, measured along the Moon’s diameter; not the "
                      "fraction of its area covered." if event["kind"] == "lunar" else
                      "Solar magnitude, measured along the Sun’s diameter; not the fraction of its area covered.")
        items.append(("Magnitude", f"{event['magnitude']}. {definition}"))
    if event.get("visibility"):
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


def render_contacts(event):
    contacts = event.get("contacts_utc", {})
    if isinstance(contacts, str):
        contacts = json.loads(contacts)
    labels = {"P1": "Penumbral phase begins", "U1": "Partial phase begins",
              "U2": "Totality begins", "U3": "Totality ends", "U4": "Partial phase ends",
              "P4": "Penumbral phase ends", "global_begin": "Eclipse begins somewhere on Earth",
              "global_end": "Eclipse ends everywhere on Earth"}
    if not contacts:
        return ""
    rows = "".join(f"<tr><th scope=\"row\">{html.escape(labels.get(key, key))}</th>"
                   f"<td>{utc_cell(value)}</td></tr>" for key, value in sorted(contacts.items(), key=lambda kv: kv[1]) if value)
    duration = ""
    start, end = ("U1", "U4") if event["kind"] == "lunar" else (None, None)
    if start and contacts.get(start) and contacts.get(end):
        seconds = (datetime.fromisoformat(contacts[end].replace("Z", "+00:00")) -
                   datetime.fromisoformat(contacts[start].replace("Z", "+00:00"))).total_seconds()
        if seconds >= 0:
            duration = f"<p>Partial-or-total umbral phase duration: {int(seconds // 3600)} h {int(seconds % 3600 // 60)} min.</p>"
    qualifier = ("These lunar phases happen at the same instants for everyone; only phases "
                 "with the Moon above your horizon can be seen." if event["kind"] == "lunar" else
                 "These are global limits, not contact times or duration at your location.")
    return '<h2>Timing and phases</h2><p>All times are UTC. Convert both date and time to your local time.</p>' + paragraphs([qualifier]) + '<table><thead><tr><th>Phase</th><th>UTC</th></tr></thead><tbody>' + rows + '</tbody></table>' + duration


def render_page(event):
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
            'blockquote{margin:1.25rem 0;padding:.2rem 1rem;border-left:3px solid #c5a45c}'
            '.eclipse-quotation-credit,.eclipse-sources{font-size:.9em}</style>'
            '</head><body><main><nav><a href="/star-almanack/">Star Almanack</a> / '
            '<a href="/almanack/eclipses/">Eclipses</a></nav>'
            f'<h1>{heading}</h1><p>{html.escape(event["date_utc"])}</p>'
            '<h2>What this eclipse means</h2>' + paragraphs([meaning]) +
            '<h2>What to look for</h2>' + paragraphs([watching]) + past +
            '<h2>This event</h2><dl>' + details + '</dl>' +
            render_contacts(event) + '<h2>Watching the eclipse</h2>' + paragraphs([observing(event)]) +
            '<h2>Sources</h2>' + sources(event) +
            '<p>Event times and geometry: Star Almanack’s calculated eclipse catalog. '
            'Visibility and magnitude, where supplied: the Calendar’s publication metadata.</p>'
            '</main></body></html>')
