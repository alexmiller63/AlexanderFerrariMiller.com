/* Nativitas interpretation catalog. Editorial drafts, not source-verified citations. */
(() => {
  'use strict';
  const source = new URL('data/paid-interpretation-drafts.json', document.currentScript.src);
  const signs = ['aries','taurus','gemini','cancer','leo','virgo','libra','scorpio','sagittarius','capricorn','aquarius','pisces'];
  let pending;
  const catalog = () => pending ||= fetch(source).then(r => { if (!r.ok) throw Error('Interpretation catalog unavailable'); return r.json(); }).then(d => d.entries || {});
  const cap = s => String(s).replace(/\b\w/g, c => c.toUpperCase());
  const sign = degrees => signs[Math.floor((((degrees % 360) + 360) % 360) / 30)];
  function paragraph(root, heading, item) {
    if (!item?.text) return;
    const article = document.createElement('article');
    const h = document.createElement('h4'); h.textContent = heading;
    const p = document.createElement('p'); p.textContent = item.text;
    article.append(h,p); root.append(article);
  }
  function section(root, title) {
    const box = document.createElement('section');
    const h = document.createElement('h3'); h.textContent = title; box.append(h); root.append(box); return box;
  }
  function unorderedKey(prefix, a, b, suffix, entries) {
    return entries[`${prefix}:${a}:${b}:${suffix}`] || entries[`${prefix}:${b}:${a}:${suffix}`];
  }
  function houseFor(longitude, cusps) {
    if (!Array.isArray(cusps) || cusps.length !== 12) return null;
    const norm = x => ((x % 360) + 360) % 360;
    for (let i=0;i<12;i++) if (norm(longitude-cusps[i]) < norm(cusps[(i+1)%12]-cusps[i])) return i+1;
    return null;
  }
  async function natal(report, target) {
    const entries = await catalog(); target.replaceChildren();
    const intro = document.createElement('p');
    intro.textContent = 'Symbolic Western astrological interpretations; these editorial drafts have not completed historical source verification. Astrology is not scientifically validated.';
    target.append(intro);
    const placements = section(target, 'Planets in signs');
    for (const b of report.bodies || []) paragraph(placements, `${cap(b.body)} in ${cap(sign(b.longitude))}`, entries[`natal-placement:${b.body}:${sign(b.longitude)}`]);
    if (!report.unknown_time && Array.isArray(report.houses)) {
      const houses = section(target, 'Planets in houses');
      for (const b of report.bodies || []) {
        const house = houseFor(b.longitude, report.houses);
        if (house) paragraph(houses, `${cap(b.body)} in house ${house}`, entries[`natal-planet-house:${b.body}:${house}`]);
      }
      const cusps = section(target, 'Signs on house cusps');
      report.houses.forEach((longitude, i) => paragraph(cusps, `House ${i+1} in ${cap(sign(longitude))}`, entries[`natal-house-sign:${i+1}:${sign(longitude)}`]));
    }
    const aspects = section(target, 'Planetary aspects');
    for (const a of report.aspects || []) {
      const first = a.first?.body || a.first_body, second = a.second?.body || a.second_body;
      const kind = a.name || a.aspect;
      if (first && second && kind) paragraph(aspects, `${cap(first)} ${cap(kind)} ${cap(second)}`, unorderedKey('natal-aspect', first, second, kind, entries));
    }
  }
  async function synastry(report, target) {
    const entries = await catalog(); target.replaceChildren();
    const intro = document.createElement('p');
    intro.textContent = 'Symbolic relationship interpretations, not a compatibility score or scientifically validated predictions. Historical source verification is ongoing.';
    target.append(intro);
    const aspects = section(target, 'Cross-chart aspects');
    for (const a of report.aspects || []) paragraph(aspects,
      `${cap(a.first_body)} ${cap(a.aspect)} ${cap(a.second_body)}`,
      unorderedKey('synastry-aspect', a.first_body, a.second_body, a.aspect, entries));
    const overlays = section(target, 'House overlays');
    for (const o of report.house_overlays || []) paragraph(overlays,
      `${cap(report.people[o.planet_person-1].label)}: ${cap(o.body)} in ${cap(report.people[o.house_person-1].label)}’s house ${o.house}`,
      entries[`synastry-overlay:${o.body}:${o.house}`]);
  }
  window.NativitasDraftLibrary = {natal,synastry};
})();