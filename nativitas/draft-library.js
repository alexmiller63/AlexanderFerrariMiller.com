/* Nativitas interpretations: qualified natal aspect reviews and separate editorial drafts. */
(() => {
  'use strict';
  const source = new URL('data/paid-interpretation-drafts.json', document.currentScript.src);
  const signs = ['aries','taurus','gemini','cancer','leo','virgo','libra','scorpio','sagittarius','capricorn','aquarius','pisces'];
  const natalSource = new URL("data/natal-aspects-reviewed.json", document.currentScript.src);
  let reviewedPending;
  const reviewed = () => reviewedPending ||= fetch(natalSource).then(r => { if (!r.ok) throw Error("Reviewed natal aspects unavailable"); return r.json(); }).then(d => d.entries).catch(error => { reviewedPending = undefined; throw error; });
  const placementSource = new URL('data/natal-placements-reviewed.json', document.currentScript.src);
  let placementPending;
  const reviewedPlacements = () => placementPending ||= fetch(placementSource).then(r => {
    if (!r.ok) throw Error('Reviewed natal placements unavailable');
    return r.json();
  }).then(d => d.entries).catch(error => { placementPending = undefined; throw error; });
  let pending;
  const catalog = () => pending ||= fetch(source).then(r => { if (!r.ok) throw Error('Interpretation catalog unavailable'); return r.json(); }).then(d => d.entries || {});
  const cap = s => String(s).replace(/\b\w/g, c => c.toUpperCase());
  const sign = degrees => signs[Math.floor((((degrees % 360) + 360) % 360) / 30)];
  function paragraph(root, heading, item) {
    if (!item?.text) return;
    const article = document.createElement('article');
    const h = document.createElement('h4'); h.textContent = heading;
    const p = document.createElement('p'); p.textContent = item.text;
    article.append(h,p);
    if (item.status === 'prepared-dignity-synthesis-adapted-source-checked') {
      const label = document.createElement('p');
      label.textContent = 'Traditional sign dignity: an editorial application of checked rules, not a complete personality reading.';
      article.append(label);
    }
    for (const reference of item.sources || []) {
      const note = document.createElement('p');
      const link = document.createElement('a');
      link.href = reference.url; link.textContent = reference.title || reference.url;
      note.append('Sources: ', link, '. ' + (reference.scope || '') + '. ' + (reference.qualification || ''));
      article.append(note);
    }
    root.append(article);
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
    const [drafts, natalAspects, replacements] = await Promise.all([catalog(), reviewed(), reviewedPlacements()]);
    const entries = {...drafts, ...replacements}; target.replaceChildren();
    const intro = document.createElement('p');
    intro.textContent = 'Symbolic Western astrological interpretations. Natal aspects are passage-checked against a historical transcription; edition verification is pending. Selected sign-dignity and house readings have qualified Lilly sources beneath them; other placement readings remain editorial drafts awaiting source verification. Astrology is not scientifically validated.';
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
      if (first && second && kind) paragraph(aspects, `${cap(first)} ${cap(kind)} ${cap(second)}`, unorderedKey('natal-aspect', first, second, String(kind).toLowerCase(), natalAspects));
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