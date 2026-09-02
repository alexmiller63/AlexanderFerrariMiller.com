from pathlib import Path
import html
import re
import markdown

SOURCE = Path('/tmp/almanack.md')
OUT = Path('almanack/weeks')

source = SOURCE.read_text(encoding='utf-8')
OUT.mkdir(parents=True, exist_ok=True)

parts = re.split(r'(?=^## ISO 2026-W\d{2}\s*$)', source, flags=re.M)
weeks = []

for part in parts:
    lines = part.splitlines()
    if not lines:
        continue
    match = re.match(r'^## ISO 2026-W(\d{2})\s*$', lines[0])
    if not match:
        continue
    week = int(match.group(1))
    label = f'ISO 2026-W{week:02d}'
    civil = re.search(r'\*\*Civil dates:\*\*\s*(.+)', part)
    civil_dates = civil.group(1).strip() if civil else ''
    weeks.append((week, label, civil_dates, part))

if len(weeks) != 53:
    raise SystemExit(f'Expected 53 ISO weeks, found {len(weeks)}')

nav = '''<nav class="almanack-nav" aria-label="Almanack navigation">
  <a class="almanack-site-mark" href="../index.html">STAR ALMANACK · MINISITE</a>
  <a href="../index.html">Almanack Home</a>
  <a href="index.html">2026 Almanack</a>
  <a href="../../projects.html">All Projects</a>
</nav>'''

footer = '''<footer class="almanack-footer">
<nav class="almanack-nav" aria-label="Almanack footer navigation">
  <a class="almanack-site-mark" href="../index.html">STAR ALMANACK · MINISITE</a>
  <a href="../index.html">Almanack Home</a>
  <a href="index.html">2026 Almanack</a>
  <a href="../../projects.html">All Projects</a>
</nav>
</footer>'''

for i, (week, label, civil_dates, part) in enumerate(weeks):
    body = markdown.markdown(part, extensions=['tables'])
    previous = ''
    following = ''
    if i > 0:
        previous = f'<a class="button" href="W{weeks[i - 1][0]:02d}.html">← Previous week</a>'
    if i + 1 < len(weeks):
        following = f'<a class="button" href="W{weeks[i + 1][0]:02d}.html">Next week →</a>'

    week_nav = f'<div class="week-nav">{previous}<a class="button" href="index.html">All weeks</a>{following}</div>'
    page = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(label)} · Star Almanack</title>
  <link rel="stylesheet" href="../css/almanack.css">
</head>
<body>
{nav}
<main class="page-shell week-content">
  {week_nav}
  {body}
  {week_nav}
</main>
{footer}
</body>
</html>
'''
    (OUT / f'W{week:02d}.html').write_text(page, encoding='utf-8')

cards = []
for week, label, civil_dates, _ in weeks:
    cards.append(f'''<article class="card">
  <h2><a href="W{week:02d}.html">{html.escape(label)}</a></h2>
  <p>{html.escape(civil_dates)}</p>
</article>''')

index = f'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Star Almanack · ISO 2026</title>
  <link rel="stylesheet" href="../css/almanack.css">
</head>
<body>
{nav}
<main class="page-shell">
  <section class="hero">
    <p class="eyebrow">Star Almanack · 2026</p>
    <h1>ISO Weeks</h1>
    <p class="tagline">A Natural Philosopher’s Guide to the Night Sky</p>
  </section>
  <section class="cards week-grid" aria-label="ISO 2026 weeks">
    {''.join(cards)}
  </section>
</main>
{footer}
</body>
</html>
'''

(OUT / 'index.html').write_text(index, encoding='utf-8')
print(f'Built {len(weeks)} Almanack week pages.')
