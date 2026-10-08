"""Permanent notation IDs; old names are input aliases only."""
from enum import IntEnum


class NotationMode(IntEnum):
    GREEK = 1
    ENGLISH = 2
    LATIN = 2  # Compatibility for callers using the old member name.
    MIXED = 3

    @classmethod
    def _missing_(cls, value):
        aliases = {"greek": 1, "symbols": 1, "latin": 2, "english": 2, "mixed": 3,
                   "1": 1, "2": 2, "3": 3}
        number = aliases.get(str(value).lower())
        return cls(number) if number is not None else None

    def __str__(self):
        return str(self.value)


MODE_KEYS = {1: "greek", 2: "latin", 3: "mixed"}
SVG_MODE_SCRIPT = '''
(function () {
  const root = document.documentElement;
  const aliases = {1:'1',2:'2',3:'3',greek:'1',symbols:'1',latin:'2',english:'2',mixed:'3'};
  const choices = root.querySelectorAll('[data-notation-choice]');
  function update() {
    const mode = aliases[location.hash.slice(1)] || '1';
    root.setAttribute('data-notation-mode', mode);
    choices.forEach(button => button.setAttribute('aria-pressed',
      String(button.getAttribute('data-notation-choice') === mode)));
  }
  choices.forEach(button => {
    function select() { location.hash = button.getAttribute('data-notation-choice'); update(); }
    button.addEventListener('click', select);
    button.addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); select(); }
    });
  });
  window.addEventListener('hashchange', update);
  update();
})();
'''


def refresh_document(text):
    """Migrate presentation metadata without rerunning chart geometry.

    Payload names and stable file paths remain readable by legacy consumers.
    Active mode IDs, selected state, and newly saved links use 1, 2, and 3.
    """
    import re
    for name, number in (("greek", 1), ("latin", 2), ("mixed", 3)):
        text = re.sub(r'(data-(?:bayer-mode|finder-mode|finder-image|notation-mode|notation-choice)=[\"\'])'
                      + name + r'([\"\'])', lambda m: m[1] + str(number) + m[2], text)
    text = re.sub(r'(data-(?:bayer-mode|notation-choice)=[\"\']2[\"\'][^>]*>)Latin(<)',
                  r'\1English\2', text)
    text = text.replace('>Latin</figcaption>', '>English</figcaption>')
    text = text.replace('Planet Finder — Latin', 'Planet Finder — English')
    text = text.replace('>Latin · ', '>English · ')
    if 'data-notation-choice=' in text:
        def script(match):
            return match[1] + SVG_MODE_SCRIPT + match[3] if 'data-notation-choice' in match[2] else match[0]
        text = re.sub(r'(<script\b[^>]*>)(.*?)(</script>)', script, text, flags=re.S)
    return text


def main():
    from pathlib import Path
    import argparse
    parser = argparse.ArgumentParser(description="Refresh numeric notation IDs and English labels only")
    parser.add_argument("roots", nargs="+", type=Path)
    args = parser.parse_args()
    changed = 0
    for root in args.roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*"))
        for path in paths:
            if not path.is_file() or path.suffix not in {".html", ".svg"}:
                continue
            before = path.read_text(encoding="utf-8")
            after = refresh_document(before)
            if before != after:
                path.write_text(after, encoding="utf-8")
                changed += 1
    print(f"Refreshed {changed} documents; chart geometry preserved")


if __name__ == "__main__":
    main()
