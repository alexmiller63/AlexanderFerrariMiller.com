from pathlib import Path
import html
import re
import markdown

source = Path('/tmp/almanack.md').read_text(encoding='utf-8')
out = Path('almanack')

pattern = re.compile(r'^## ISO 2026-W(\d{2})\s*$', re.M)
matches = list(pattern.finditer(source))
if not matches:
    raise SystemExit('No ISO 2026 week sections found')

week_numbers = [int(match.group(1)) for match in matches]
if week_numbers != sorted(set(week_numbers)):
    raise SystemExit(f'ISO week headings are duplicated or out of order: {week_numbers}')


def shell(title, body, prev_week=None, next_week=None):
    links = [
        '<a href="index.html">Almanack Home</a>',
        '<a href="2026.html">2026 Weeks</a>',
    ]
    if prev_week is not None:
        links.append(f'<a href="ISO2026-W{prev_week:02d}.html">← Week {prev_week:02d}</a>')
    if next_week is not None:
        links.append(f'<a href="ISO2026-W{next_week:02d}.html">Week {next_week:02d} →</a>')
    weeknav = ' '.join(links)
    return f'''---
layout: null
---
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="css/almanack.css">
</head>
<body>
  {{% include_relative includes/nav.html %}}
  <main class="page-shell almanack-week">
    <nav class="week-nav" aria-label="Week navigation">{weeknav}</nav>
    {body}
    <nav class="week-nav" aria-label="Week navigation">{weeknav}</nav>
  </main>
  {{% include_relative includes/footer.html %}}
</body>
</html>
'''


rows = []
for i, match in enumerate(matches):
    week = week_numbers[i]
    start = match.start()
    end = matches[i + 1].start() if i + 1 < len(matches) else len(source)
    section = source[start:end].strip()
    civil = re.search(r'^\*\*Civil dates:\*\*\s*(.+)$', section, re.M)
    civil_text = civil.group(1).strip() if civil else ''
    body = markdown.markdown(section, extensions=['tables'])
    prev_week = week_numbers[i - 1] if i > 0 else None
    next_week = week_numbers[i + 1] if i + 1 < len(week_numbers) else None
    page = shell(f'Star Almanack — ISO 2026-W{week:02d}', body, prev_week, next_week)
    (out / f'ISO2026-W{week:02d}.html').write_text(page, encoding='utf-8')
    rows.append((week, civil_text))

cards = '\n'.join(
    f'''      <article class="card">
        <h2>Week {week:02d}</h2>
        <p>{html.escape(civil)}</p>
        <a class="button" href="ISO2026-W{week:02d}.html">Open week</a>
      </article>'''
    for week, civil in rows
)

count = len(rows)
last_week = rows[-1][0]
index = f'''---
layout: null
---
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Star Almanack — 2026</title>
  <link rel="stylesheet" href="css/almanack.css">
</head>
<body>
  {{% include_relative includes/nav.html %}}
  <main class="page-shell">
    <section class="hero">
      <p class="eyebrow">Star Almanack · ISO 2026</p>
      <h1>2026 Weeks of the Night Sky</h1>
      <p class="tagline">{count} ISO weeks are currently published from the working Almanack, through Week {last_week:02d}.</p>
    </section>
    <section class="cards week-cards" aria-label="2026 ISO weeks">
{cards}
    </section>
  </main>
  {{% include_relative includes/footer.html %}}
</body>
</html>
'''
(out / '2026.html').write_text(index, encoding='utf-8')

home = out / 'index.html'
text = home.read_text(encoding='utf-8')
marker = '    <section class="cards" aria-label="Almanack sections">'
card = f'''    <section class="cards" aria-label="Almanack sections">
      <article class="card">
        <h2>2026 Almanack</h2>
        <p>The working Star Almanack arranged by ISO week. {count} weeks are currently published.</p>
        <a class="button" href="2026.html">Browse 2026</a>
      </article>'''
if 'href="2026.html"' not in text:
    if marker not in text:
        raise SystemExit('Almanack cards section not found')
    home.write_text(text.replace(marker, card, 1), encoding='utf-8')

css = out / 'css' / 'almanack.css'
css_text = css.read_text(encoding='utf-8')
style_marker = '/* Almanack weekly pages */'
if style_marker not in css_text:
    css_text += '''

/* Almanack weekly pages */
.week-cards {
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.almanack-week {
  padding-top: 36px;
  padding-bottom: 48px;
}

.almanack-week table {
  width: 100%;
  border-collapse: collapse;
  margin: 18px 0 28px;
}

.almanack-week th,
.almanack-week td {
  padding: 9px 10px;
  border: 1px solid var(--border);
  text-align: left;
  vertical-align: top;
}

.almanack-week code {
  color: var(--accent);
}

.week-nav {
  display: flex;
  flex-wrap: wrap;
  gap: 12px 20px;
  margin: 0 0 28px;
  padding: 14px 0;
  border-bottom: 1px solid var(--border);
}

.week-nav:last-child {
  margin: 32px 0 0;
  border-top: 1px solid var(--border);
  border-bottom: 0;
}

.week-nav a {
  color: var(--accent);
  text-decoration: none;
}
'''
    css.write_text(css_text, encoding='utf-8')
