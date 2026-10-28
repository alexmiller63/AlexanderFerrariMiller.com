"""Editorial migration: routine database attribution belongs in Sources, not prose.

Never fetches sources, changes review status, or grants research approval.
"""
from __future__ import annotations
import re

SOURCE_STYLE_RULE = 'Keep routine SIMBAD mentions out of the narrative. Put SIMBAD and other source citations together in a compact Sources section at the bottom, using clickable Markdown links. Mention SIMBAD in prose only when the database itself is intrinsically relevant. '

LINK = re.compile(r'\[([^\]\n]+)\]\((https?://[^\s<>]+?)\)')
URL = re.compile(r'https?://[^\s<>\]\)]+')
SOURCE = re.compile(r'(?<![\w\[])(?:\*\*)?Sources?(?: for [^:.\n]{1,60})?(?:\*\*)?\s*:\s*(?:\*\*)?')
HEADER = re.compile(r'(?i)^\s*(?:#{1,6}\s+|\*\*)?(?:Sources?|References)\s*:?(?:\*\*)?\s*:?\s*$')


def clean_story_sources(text: str) -> str:
    """Relocate citations while preserving measurements and qualification prose."""
    if not re.search(r'\bSIMBAD\b', text):
        return text
    citations = {}
    for m in LINK.finditer(text):
        citations.setdefault(m[2], m[1])
    for m in URL.finditer(text):
        u = m[0].rstrip('.,;:')
        if 'simbad.' in u:
            citations.setdefault(u, 'SIMBAD')
    notes, paragraphs = [], []
    in_sources = False
    for part in re.split(r'\n\s*\n', text.strip()):
        if HEADER.fullmatch(part):
            in_sources = True
            continue
        if in_sources and not (URL.search(part) or part.lstrip().startswith(('- ', '[', 'SIMBAD')) or SOURCE.match(part.strip())):
            in_sources = False
        if in_sources or SOURCE.match(part.strip()):
            # Preserve source notes, including non-URL provenance.
            notes.append(SOURCE.sub('', part, count=1).strip())
            continue
        # An inline Source declaration ends at its last URL, not at the end of
        # the paragraph: subsequent narrative must remain in the story.
        match = next((m for m in SOURCE.finditer(part) if not any(link.start() <= m.start() < link.end() for link in LINK.finditer(part))), None)
        if match:
            tail = part[match.end():]
            links = list(LINK.finditer(tail))
            urls = list(URL.finditer(tail))
            ends = [m.end() for m in links] + [m.end() for m in urls]
            if ends:
                end = max(ends)
                while end < len(tail) and tail[end] in '.)':
                    end += 1
                notes.append(tail[:end].strip())
                part = part[:match.start()] + tail[end:]
            elif re.match(r'(?i)SIMBAD,?\s+above\.?', tail):
                part = part[:match.start()] + re.sub(r'(?i)^SIMBAD,?\s+above\.?', '', tail)
        # Remove routine inline SIMBAD links, retaining them in the footer.
        part = LINK.sub(lambda m: '' if 'simbad.' in m[2] else m[0], part)
        def bare(m):
            u = m[0].rstrip('.,;:')
            return m[0][len(u):] if 'simbad.' in u else m[0]
        part = URL.sub(bare, part)
        dangling = re.search(r'\[([^\]]+)\]\(\s*$', part)
        if dangling:
            notes.append(dangling[1])
            part = part[:dangling.start()]
        part = re.sub(r'(?i)\(\s*SIMBAD\s*:\s*[.;]?\s*\)', '', part)
        part = re.sub(r'(?i)According to (?:the )?SIMBAD(?: astronomical database)?,\s*', '', part)
        part = re.sub(r'(?i)(?:the )?SIMBAD(?: astronomical database| database)?([’\']s)?',
                      lambda m: "the catalogue's" if m[1] else 'the catalogue', part)
        part = re.sub(r'\(\s*(?:the catalogue)?\s*[,;:.]*\s*\)', '', part, flags=re.I)
        part = re.sub(r'\(\s*;\s*', '(', part)

        part = re.sub(r':\s*\.', '.', part)
        part = re.sub(r' +([.,;])', r'\1', part)
        part = re.sub(r'\s+\.\s*\.', '.', part)
        part = re.sub(r' {2,}', ' ', part).strip()
        part = re.sub(r'(?<=[a-z’”])\.\.(?=\s|$)', '.', part)
        part = re.sub(r'\(\s*$', '', part).rstrip()
        part = re.sub(r'(^|[.!?]\s+)the catalogue', r'\1The catalogue', part)
        part = '\n'.join(line.rstrip() for line in part.splitlines()
                         if line.strip() != '-' and not HEADER.fullmatch(line)).strip()
        if part:
            paragraphs.append(part)
    # Keep original source annotations; append only URLs not already recorded.
    sources = '\n\n'.join(n for n in notes if n)
    existing = {m[0].rstrip('.,;:') for m in URL.finditer(sources)}
    extras = ['- [' + label + '](' + url + ')' for url, label in citations.items()
              if 'simbad.' in url and url not in existing]
    footer = '\n\n'.join(x for x in [sources, '\n'.join(extras)] if x)
    if not footer:
        # Keep uncited attribution visible rather than silently losing it.
        return text
    return '\n\n'.join(paragraphs) + '\n\n## Sources\n\n' + footer + '\n'


def render_story_body(body: str) -> str:
    """Render story paragraphs and a clickable Sources footer with escaped text."""
    import html
    def inline(text):
        chunks, position = [], 0
        tokens = re.compile(r'\[([^\]\n]+)\]\((https?://[^\s<>]+?)\)|https?://[^\s<>\]\)]+')
        for m in tokens.finditer(text):
            chunks.append(html.escape(text[position:m.start()]))
            url = m[2] if m[2] else m[0].rstrip('.,;:')
            label = m[1] if m[2] else url
            chunks.append('<a href="' + html.escape(url, quote=True) + '">' + html.escape(label) + '</a>')
            if not m[2]:
                chunks.append(html.escape(m[0][len(url):]))
            position = m.end()
        chunks.append(html.escape(text[position:]))
        return ''.join(chunks)
    parts = []
    for part in re.split(r'\n\s*\n', body.strip()):
        if not part.strip():
            continue
        if HEADER.fullmatch(part):
            parts.append('<h2>Sources</h2>')
        elif all(line.startswith('- ') for line in part.splitlines()):
            parts.append('<ul>' + ''.join('<li>' + inline(line[2:]) + '</li>' for line in part.splitlines()) + '</ul>')
        else:
            parts.append('<p>' + inline(' '.join(part.splitlines())) + '</p>')
    return '\n'.join(parts)
