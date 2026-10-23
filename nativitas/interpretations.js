/* Nativitas: concise traditional Western tropical astrology reference.
   Sources: William Lilly, Christian Astrology (1647), Book I (planetary natures);
   H. L. Cornell, Encyclopaedia of Medical Astrology (1933) (sign keywords);
   C. E. O. Carter, The Astrological Aspects (1930) (aspect conventions).
   These are editorial summaries of traditions, not quotations or validated predictions.
*/
(() => {
  'use strict';
  const signs = ['Aries','Taurus','Gemini','Cancer','Leo','Virgo','Libra','Scorpio','Sagittarius','Capricorn','Aquarius','Pisces'];
  const qualities = [
    'initiative, directness and beginnings','persistence, stability and material concerns',
    'communication, curiosity and adaptability','nurture, protection and belonging',
    'self-expression, pride and creativity','analysis, service and discrimination',
    'balance, partnership and fairness','intensity, secrecy and transformation',
    'exploration, philosophy and freedom','discipline, duty and ambition',
    'independence, collective concerns and unconventional thinking',
    'imagination, sympathy and receptivity'
  ];
  const planets = {
    sun:'identity, vitality and purpose',moon:'emotion, habits and receptivity',
    mercury:'thought, language and exchange',venus:'affection, attraction and harmony',
    mars:'action, assertion and conflict',jupiter:'growth, belief and generosity',
    saturn:'limits, responsibility and endurance',uranus:'change, disruption and independence',
    neptune:'ideals, dreams and uncertainty',pluto:'power, depth and transformation',
    ceres:'nurturing and cycles of care'
  };
  const aspectMeaning = {
    conjunction:'Traditionally read as a blending or intensification of the two planetary principles; not automatically beneficial or difficult.',
    sextile:'Traditionally considered an opportunity for cooperation or ease between the planetary principles.',
    square:'Traditionally associated with friction, tension or the need for effort between the planetary principles.',
    trine:'Traditionally associated with ease and a natural flow between the planetary principles.',
    opposition:'Traditionally associated with polarity, contrast or the need for balance between the planetary principles.'
  };
  const title = s => s[0].toUpperCase()+s.slice(1);
  function render(data) {
    const target = document.getElementById('natal-interpretations');
    if (!target) return;
    target.replaceChildren();
    const heading = document.createElement('h2');
    heading.textContent = 'Traditional interpretations';
    target.append(heading);
    const caveat = document.createElement('p');
    caveat.textContent = 'Historical Western tropical astrological associations, not scientifically established descriptions of personality or relationships. The summaries below describe conventional symbolic themes; they are not individualized predictions.';
    target.append(caveat);
    const placements = document.createElement('details');
    placements.open = true;
    const psummary = document.createElement('summary');
    psummary.textContent = 'Planetary placements';
    placements.append(psummary);
    const list = document.createElement('div');
    for (const row of data.bodies || []) {
      const sign = Math.floor((((row.longitude % 360)+360)%360)/30);
      const p = document.createElement('p');
      const strong = document.createElement('strong');
      strong.textContent = title(row.body)+' in '+signs[sign]+': ';
      p.append(strong, document.createTextNode('In traditional symbolism, '+title(row.body)+' concerns '+(planets[row.body] || 'its associated themes')+'; '+signs[sign]+' is associated with '+qualities[sign]+'.'));
      list.append(p);
    }
    placements.append(list);
    target.append(placements);
    const aspects = document.createElement('details');
    aspects.open = true;
    const asummary = document.createElement('summary');
    asummary.textContent = 'Major aspects ('+(data.aspects || []).length+')';
    aspects.append(asummary);
    for (const a of data.aspects || []) {
      const p = document.createElement('p');
      const strong = document.createElement('strong');
      strong.textContent = title(a.first.body)+' '+a.symbol+' '+title(a.second.body)+': ';
      p.append(strong, document.createTextNode(aspectMeaning[a.name] || 'Traditional aspect.'));
      aspects.append(p);
    }
    target.append(aspects);
    const source = document.createElement('p');
    source.textContent = 'Reference traditions: William Lilly, Christian Astrology (1647), Book I; H. L. Cornell, Encyclopaedia of Medical Astrology (1933); C. E. O. Carter, The Astrological Aspects (1930). These are broad editorial summaries, not verbatim extracts or claims that each author endorsed every modern planetary association. Ceres, Uranus, Neptune and Pluto are later additions to the older tradition.';
    target.append(source);
    if (data.unknown_time) {
      const note = document.createElement('p');
      note.textContent = 'Unknown birth time: positions use local noon. The Moon may have occupied a neighboring sign; aspects involving the Moon may change over the birth day. No house interpretations are provided.';
      target.append(note);
    }
  }
  // The shared ephemera renderer publishes a JSON report as a Blob URL.
  // Observe completed chart rendering so the interpretation module stays separate.
  const chart = document.getElementById('natal-chart-output');
  const download = document.getElementById('ephemera-download');
  if (chart && download) {
    let revision = 0;
    const observer = new MutationObserver(async () => {
      const current = ++revision;
      // The form finishes setting the download URL in the same JS task.
      await new Promise(resolve => setTimeout(resolve, 0));
      if (current !== revision || !download.href.startsWith('blob:')) return;
      try {
        const response = await fetch(download.href);
        const report = await response.json();
        if (current === revision && report.calculator !== 'ephemera' && Array.isArray(report.bodies) && Array.isArray(report.aspects)) {
          render(report);
        }
      } catch (error) {
        const target = document.getElementById('natal-interpretations');
        if (target) target.textContent = 'Interpretations are unavailable for this chart.';
      }
    });
    observer.observe(chart, {childList: true});
  }
  window.NativitasInterpretations = {render};
})();
