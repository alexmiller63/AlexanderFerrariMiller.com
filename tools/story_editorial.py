"""Source presentation shared by evergreen story generators and readers.

No research approvals or factual corrections are implied by presentation cleanup.
"""
import html
import re

EDITORIAL_RULE = (
    "Keep routine SIMBAD and other database mentions out of the narrative unless "
    "the database itself is intrinsically relevant. Preserve measured values, "
    "uncertainties and qualifications. Put clickable source citations together in "
    "one compact Sources section at the bottom; do not invent references."
)

LINK = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s]+?)\)")
URL = re.compile(r"https?://[^\s<>]+")


def source_urls(text):
    # Markdown destination parentheses are delimiters, not part of the URL.
    masked = LINK.sub(lambda m: m.group(2), text)
    return {m.group().rstrip(".,;:)*\"'") for m in URL.finditer(masked)}


def clean_story(text):
    """Move citations, retaining every URL and all source notes.

    Existing research snapshots and response payloads remain untouched. This acts
    on editable manuscripts only, never on external source text.
    """
    front = ""
    if text.startswith("---\n"):
        end = text.index("\n---\n", 4) + 5
        front, text = text[:end], text[end:]
    # Detach source sections, including any descriptive annotations.
    parts = re.split(r"(?im)^#{1,6} +Sources?[^\n]*\n|^\*\*Sources?(?: and observing tool)?:(?:\*\*)? *", text, maxsplit=1)
    body = parts[0]
    notes = parts[1].strip() if len(parts) > 1 else ""
    citations = []
    tokens = []

    def link(m):
        label, url = m.groups()
        citations.append(f"[{label}]({url})")
        token = f"ZZCITATION{len(tokens)}ZZ"
        tokens.append((token, label))
        return token

    body = LINK.sub(link, body)

    def bare(m):
        raw = m.group()
        url = raw.rstrip(".,;:)*\"'")
        suffix = raw[len(url):]
        citations.append(f"[{url}]({url})")
        token = f"ZZCITATION{len(tokens)}ZZ"
        tokens.append((token, ""))
        return token + suffix

    body = URL.sub(bare, body)
    # Explicit citation clauses become source notes. Stop before a following
    # sentence so its scientific or observing content stays in the narrative.
    clause = re.compile(r"(?:\*\*)?Sources?(?: for [^:\n]+)?:(?:\*\*)? *[^\n]*?(?=\. +[A-Z]|\n|$)")
    moved = []
    body = re.sub(r"\([^()\n]*ZZCITATION\d+ZZ[^()\n]*\)", lambda m: moved.append(m.group()[1:-1]) or "", body)
    body = clause.sub(lambda m: moved.append(m.group().strip()) or "", body)
    # Remove the complete attribution only when its link label is discarded.
    # A factual link label remains in the sentence; URLs stay in the footer.
    for token, label in tokens:
        if re.match(r"(?i)SIMBAD\b|Research:|Sources?:", label):
            body = re.sub(r",? +according to +" + token + r"(?=[.!?]|$)", "", body, flags=re.I)
            body = re.sub(r"(?i)\baccording to +" + token + r", +", "", body)
            body = re.sub(r"(?i)(\b(?:listed|recorded|reported|provided) (?:by|in) +)" + token,
                          r"\1the catalogue", body)
    for token, label in tokens:
        # A link label can itself be part of a factual sentence. Keep it unless
        # it is a stand-alone reference, in which case the footer carries it.
        body = re.sub(r"(?m)^ *\(?" + token + r"\)?[.;]? *$", "", body)
        body = body.replace(token, "" if re.match(r"(?i)SIMBAD\b|Research:|Sources?:", label) else label)
        notes = notes.replace(token, label)
    for item in moved:
        for i, (token, label) in enumerate(tokens):
            item = item.replace(token, citations[i])
        item = re.sub(r"^(?:\*\*)?Sources?[^:]*:(?:\*\*)? *", "", item).strip(" .,;:")
        if item:
            notes += ("\n\n" if notes else "") + "- " + item
    # Remove database boilerplate without altering physical claims or qualifiers.
    body = re.sub(r"According to the SIMBAD astronomical database, *", "", body)
    body = re.sub(r"(?i)\bthe SIMBAD (?:astronomical )?database\b", "the catalogue", body)
    body = re.sub(r"(?i)\bSIMBAD(?:[’']s)? (?:astronomical )?database\b", "the catalogue", body)
    body = re.sub(r"\b[Tt]he SIMBAD\b", "the catalogue", body)
    body = re.sub(r"\bSIMBAD[’']s\b", "the catalogue’s", body)
    body = re.sub(r"\bSIMBAD\b", "the catalogue", body)
    body = re.sub(r"(^|[.!?] +|\n\n)the catalogue", r"\1The catalogue", body)
    body = re.sub(r"(?m)^([*#]+ +)the catalogue", r"\1The catalogue", body)
    body = re.sub(r"[.:;] +\.(?=\s|$)", ".", body)
    body = body.replace("Official star-name guidance.", "")
    body = re.sub(r" +([,.;:])", r"\1", body)
    body = re.sub(r"\( *\)|\( *[.;] *\)", "", body)
    body = re.sub(r"(?m)^ *[.;] *$", "", body)
    body = re.sub(r"(?m)^ *\. +", "", body)
    body = re.sub(r"(?m) +$", "", body)
    body = re.sub(r" {2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body).strip()
    # Preserve footer annotations and deduplicate identical labelled citations.
    additions = []
    footer_seen = notes
    for citation in citations:
        if citation not in footer_seen:
            additions.append("- " + citation)
            footer_seen += "\n" + citation
    footer = notes
    if additions:
        footer += ("\n\n" if footer else "") + "\n".join(additions)
    result = front + ("\n" if front else "") + body
    if footer:
        result += "\n\n## Sources\n\n" + footer
    return result.rstrip() + "\n"


def render_inline(value):
    value = html.escape(value)
    anchors = []
    def stash(label, url):
        token = f"ZZANCHOR{len(anchors)}ZZ"
        anchors.append('<a href="' + html.escape(html.unescape(url), quote=True) + '">' + label + '</a>')
        return token
    value = LINK.sub(lambda m: stash(m[1], m[2]), value)
    def bare_link(m):
        raw = m[0]
        url = raw.rstrip(".,;:)*")
        return stash(url, url) + raw[len(url):]
    value = URL.sub(bare_link, value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    value = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", value)
    for i, anchor in enumerate(anchors):
        value = value.replace(f"ZZANCHOR{i}ZZ", anchor)
    return value

def render_markdown(text):
    """Escape raw HTML and render the Markdown used by story manuscripts.

    Only http(s) destinations become links. This keeps source lists clickable
    without adding a dependency to every story-producing workflow.
    """
    blocks = []
    pending = []
    in_list = False
    def flush():
        if pending:
            blocks.append("<p>" + render_inline(" ".join(pending)) + "</p>")
            pending.clear()
    for line in text.splitlines() + [""]:
        heading = re.match(r"^(#{1,6}) +(.+)$", line)
        item = re.match(r"^[-*] +(.+)$", line)
        if not item and in_list:
            blocks.append("</ul>")
            in_list = False
        if heading:
            flush()
            level = len(heading[1])
            blocks.append(f"<h{level}>" + render_inline(heading[2]) + f"</h{level}>")
        elif item:
            flush()
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            blocks.append("<li>" + render_inline(item[1]) + "</li>")
        elif not line.strip():
            flush()
        else:
            pending.append(line.strip())
    return "\n".join(blocks)
