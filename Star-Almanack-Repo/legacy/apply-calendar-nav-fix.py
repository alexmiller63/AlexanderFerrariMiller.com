from pathlib import Path
import re

BUTTON_CSS = """
/* year-navigation-buttons */
.yearnav { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:.8rem; margin:.4rem 0 2rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.9rem; }
.yearnav > :first-child { justify-self:start; }
.yearnav > :last-child { justify-self:end; }
.yearnav a,.yearnav a:visited,.yearnav span { display:inline-block; min-width:5.5rem; padding:.58rem .8rem; border:1px solid #c8d3dc; border-radius:.45rem; text-decoration:none; text-align:center; color:var(--link); background:#fff; white-space:nowrap; }
@media (max-width:760px) { .yearnav{gap:.4rem}.yearnav a,.yearnav a:visited,.yearnav span{min-width:0;padding:.6rem .45rem} }
@media (prefers-color-scheme:dark) { .yearnav a,.yearnav a:visited,.yearnav span{background:#1c2a36;border-color:#405567;color:#b6dcff} }
"""


def patch_html(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    text = text.replace(">Calendar Home<", ">Almanack Home<")
    if 'class="yearnav"' in text and "/* year-navigation-buttons */" not in text:
        text = text.replace("</style>", BUTTON_CSS + "</style>", 1)

    # Weekly pages live one directory deeper than year indexes.
    if re.fullmatch(r"W\d{2}", path.parent.name):
        for year in (2025, 2026, 2027):
            text = text.replace(f'href="../{year}/"', f'href="../../{year}/"')

    # 2026 crosses cleanly into the adjacent ISO years.
    if path.parent.name == "W01" and path.parent.parent.name == "2026":
        text = text.replace('<span>← Previous</span>', '<a href="../../2025/W52/">← 2025-W52</a>')
    if path.parent.name == "W53" and path.parent.parent.name == "2026":
        text = text.replace('<span>Next →</span>', '<a href="../../2027/W01/">2027-W01 →</a>')

    path.write_text(text, encoding="utf-8")


for year in (2025, 2026, 2027):
    for root in (Path("almanack") / str(year), Path("Star-Almanack-Repo/site") / str(year)):
        if root.exists():
            for path in root.rglob("index.html"):
                patch_html(path)

# Keep 2026 source generator aligned.
path = Path("Star-Almanack-Repo/publish_weekly_pages.py")
if path.exists():
    text = path.read_text(encoding="utf-8")
    text = text.replace(">Calendar Home<", ">Almanack Home<")
    text = text.replace('<nav class="yearnav"><a href="../2025/">← 2025</a><span>ISO 2026</span><a href="../2027/">2027 →</a></nav>', '<nav class="yearnav"><a href="../../2025/">← 2025</a><span>ISO 2026</span><a href="../../2027/">2027 →</a></nav>')
    old = ".yearnav { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:1.5rem; margin:.65rem 0 2rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:1.1rem; }\n.yearnav > :first-child { justify-self:start; }\n.yearnav > :last-child { justify-self:end; }\n.yearnav a,.yearnav a:visited { color:var(--link); text-decoration:underline; white-space:nowrap; }\n.yearnav span { color:var(--ink); text-align:center; white-space:nowrap; }"
    new = "/* year-navigation-buttons */\n.yearnav { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; gap:.8rem; margin:.4rem 0 2rem; font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; font-size:.9rem; }\n.yearnav > :first-child { justify-self:start; }\n.yearnav > :last-child { justify-self:end; }\n.yearnav a,.yearnav a:visited,.yearnav span { display:inline-block; min-width:5.5rem; padding:.58rem .8rem; border:1px solid #c8d3dc; border-radius:.45rem; text-decoration:none; text-align:center; color:var(--link); background:#fff; white-space:nowrap; }"
    text = text.replace(old, new)
    text = text.replace(".yearnav{gap:.8rem;font-size:1.05rem}", ".yearnav{gap:.4rem}.yearnav a,.yearnav a:visited,.yearnav span{min-width:0;padding:.6rem .45rem}")
    text = text.replace("prev=f'<a href=\"../W{week-1:02d}/\">← W{week-1:02d}</a>' if week>1 else '<span>← Previous</span>'", "prev=f'<a href=\"../W{week-1:02d}/\">← W{week-1:02d}</a>' if week>1 else '<a href=\"../../2025/W52/\">← 2025-W52</a>'")
    text = text.replace("nxt=f'<a href=\"../W{week+1:02d}/\">W{week+1:02d} →</a>' if week<53 else '<span>Next →</span>'", "nxt=f'<a href=\"../W{week+1:02d}/\">W{week+1:02d} →</a>' if week<53 else '<a href=\"../../2027/W01/\">2027-W01 →</a>'")
    path.write_text(text, encoding="utf-8")

# Keep placeholder-year generator label aligned. Its weekly year links are
# normalized in the generated output above.
path = Path("Star-Almanack-Repo/publish_placeholder_years.py")
if path.exists():
    text = path.read_text(encoding="utf-8").replace(">Calendar Home<", ">Almanack Home<")
    path.write_text(text, encoding="utf-8")
