/* Civil month/day to ISO week, independent of the browser's time zone. */
(function () {
  'use strict';
  const published = new Set([2025, 2026, 2027]);
  function isoWeek(year, month, day) {
    if (![year, month, day].every(Number.isInteger) || year < 1 || year > 9999 || month < 1 || month > 12 || day < 1 || day > 31) return null;
    const date = new Date(0);
    date.setUTCFullYear(year, month - 1, day);
    if (date.getUTCMonth() !== month - 1 || date.getUTCDate() !== day) return null;
    date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
    const isoYear = date.getUTCFullYear();
    const first = new Date(0);
    first.setUTCFullYear(isoYear, 0, 1);
    const week = Math.ceil(((date - first) / 86400000 + 1) / 7);
    return {year: isoYear, week, href: published.has(isoYear) ? `/almanack/${isoYear}/W${String(week).padStart(2, '0')}/` : null};
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = {isoWeek};
  if (typeof document === 'undefined') return;
  const form = document.getElementById('calendar-converter');
  if (!form) return;
  const results = document.getElementById('converter-results');
  const heading = document.getElementById('converter-heading');
  function render() {
    const month = Number(form.elements.month.value);
    const day = Number(form.elements.day.value);
    const extra = form.elements.year.value;
    const years = new Set([2024, 2025, 2026, 2027, 2028]);
    if (extra) years.add(Number(extra));
    const monthName = form.elements.month.selectedOptions[0].textContent;
    heading.textContent = `${monthName} ${day}`;
    results.replaceChildren();
    for (const year of [...years].sort((a, b) => a - b)) {
      const result = isoWeek(year, month, day);
      const card = document.createElement('article');
      card.className = 'card';
      const title = document.createElement('h3');
      title.textContent = String(year);
      card.append(title);
      const description = document.createElement('p');
      if (!result) {
        description.textContent = `${monthName} ${day} does not occur in ${year}.`;
        card.append(description);
      } else {
        description.textContent = `ISO ${result.year} · week ${String(result.week).padStart(2, '0')}`;
        card.append(description);
        if (result.href) {
          const link = document.createElement('a');
          link.className = 'button';
          link.href = result.href;
          link.textContent = `Open ${result.year} week ${String(result.week).padStart(2, '0')}`;
          card.append(link);
        } else {
          const status = document.createElement('p');
          status.textContent = 'Pending — Almanack not yet published for this ISO year.';
          card.append(status);
        }
      }
      results.append(card);
    }
  }
  form.addEventListener('submit', event => { event.preventDefault(); if (form.reportValidity()) render(); });
  document.getElementById('converter-now').addEventListener('click', () => {
    const today = new Date();
    form.elements.month.value = String(today.getMonth() + 1);
    form.elements.day.value = String(today.getDate());
    form.elements.year.value = String(today.getFullYear());
    if (form.reportValidity()) render();
  });
  render();
}());
