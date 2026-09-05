(function () {
  const greekNames = {
    'α':'Alpha','β':'Beta','γ':'Gamma','δ':'Delta','ε':'Epsilon','ζ':'Zeta','η':'Eta','θ':'Theta',
    'ι':'Iota','κ':'Kappa','λ':'Lambda','μ':'Mu','ν':'Nu','ξ':'Xi','ο':'Omicron','π':'Pi',
    'ρ':'Rho','σ':'Sigma','τ':'Tau','υ':'Upsilon','φ':'Phi','χ':'Chi','ψ':'Psi','ω':'Omega'
  };

  const constellationNames = {
    And:'Andromedae',Ant:'Antliae',Aps:'Apodis',Aqr:'Aquarii',Aql:'Aquilae',Ara:'Arae',Ari:'Arietis',Aur:'Aurigae',Boo:'Bootis',Cae:'Caeli',Cam:'Camelopardalis',Cnc:'Cancri',CVn:'Canum Venaticorum',CMa:'Canis Majoris',CMi:'Canis Minoris',Cap:'Capricorni',Car:'Carinae',Cas:'Cassiopeiae',Cen:'Centauri',Cep:'Cephei',Cet:'Ceti',Cha:'Chamaeleontis',Cir:'Circini',Col:'Columbae',Com:'Comae Berenices',CrA:'Coronae Australis',CrB:'Coronae Borealis',Crv:'Corvi',Crt:'Crateris',Cru:'Crucis',Cyg:'Cygni',Del:'Delphini',Dor:'Doradus',Dra:'Draconis',Equ:'Equulei',Eri:'Eridani',For:'Fornacis',Gem:'Geminorum',Gru:'Gruis',Her:'Herculis',Hor:'Horologii',Hya:'Hydrae',Hyi:'Hydri',Ind:'Indi',Lac:'Lacertae',Leo:'Leonis',LMi:'Leonis Minoris',Lep:'Leporis',Lib:'Librae',Lup:'Lupi',Lyn:'Lyncis',Lyr:'Lyrae',Men:'Mensae',Mic:'Microscopii',Mon:'Monocerotis',Mus:'Muscae',Nor:'Normae',Oct:'Octantis',Oph:'Ophiuchi',Ori:'Orionis',Pav:'Pavonis',Peg:'Pegasi',Per:'Persei',Phe:'Phoenicis',Pic:'Pictoris',Psc:'Piscium',PsA:'Piscis Austrini',Pup:'Puppis',Pyx:'Pyxidis',Ret:'Reticuli',Sge:'Sagittae',Sgr:'Sagittarii',Sco:'Scorpii',Scl:'Sculptoris',Sct:'Scuti',Ser:'Serpentis',Sex:'Sextantis',Tau:'Tauri',Tel:'Telescopii',Tri:'Trianguli',TrA:'Trianguli Australis',Tuc:'Tucanae',UMa:'Ursae Majoris',UMi:'Ursae Minoris',Vel:'Velorum',Vir:'Virginis',Vol:'Volantis',Vul:'Vulpeculae'
  };

  const zodiacNames = {
    '♈':'Aries','♉':'Taurus','♊':'Gemini','♋':'Cancer','♌':'Leo','♍':'Virgo',
    '♎':'Libra','♏':'Scorpio','♐':'Sagittarius','♑':'Capricorn','♒':'Aquarius','♓':'Pisces'
  };

  const bodyNames = {'☉':'Sun','☽':'Moon','☿':'Mercury','♀':'Venus','♂':'Mars','♃':'Jupiter','♄':'Saturn'};
  const VS = '\ufe0e';

  function notationSpan(greek, latin, mixed) {
    const span = document.createElement('span');
    span.className = 'notation-item';
    span.dataset.greek = greek;
    span.dataset.latin = latin;
    span.dataset.mixed = mixed;
    span.textContent = greek;
    return span;
  }

  document.querySelectorAll('.zodiac-glyph').forEach(function (item) {
    const glyph = item.textContent.charAt(0);
    if (!zodiacNames[glyph]) return;
    item.classList.add('notation-item');
    item.dataset.greek = glyph + VS;
    item.dataset.latin = zodiacNames[glyph];
    item.dataset.mixed = glyph + VS + '\n' + zodiacNames[glyph];
  });

  const main = document.querySelector('main');
  if (main) {
    const pattern = /([αβγδεζηθικλμνξοπρστυφχψω])(\d+)?\s+([A-Z][A-Za-z]{2})\b|[☉☽☿♀♂♃♄]|([αβγδεζηθικλμνξοπρστυφχψω])(\d+)?/g;
    const nodes = [];
    const walker = document.createTreeWalker(main, NodeFilter.SHOW_TEXT);

    while (walker.nextNode()) {
      const parent = walker.currentNode.parentElement;
      if (parent && !parent.closest('.notation-item') && pattern.test(walker.currentNode.nodeValue)) {
        nodes.push(walker.currentNode);
      }
      pattern.lastIndex = 0;
    }

    nodes.forEach(function (node) {
      const text = node.nodeValue;
      const fragment = document.createDocumentFragment();
      let last = 0;
      let match;
      pattern.lastIndex = 0;

      while ((match = pattern.exec(text))) {
        fragment.append(document.createTextNode(text.slice(last, match.index)));
        const token = match[0];
        let greek = token;
        let latin = token;
        let mixed = token;
        const bayer = token.match(/^([αβγδεζηθικλμνξοπρστυφχψω])(\d+)?\s+([A-Z][A-Za-z]{2})$/);
        const greekOnly = token.match(/^([αβγδεζηθικλμνξοπρστυφχψω])(\d+)?$/);

        if (bayer) {
          const suffix = bayer[2] || '';
          const constellation = constellationNames[bayer[3]] || bayer[3];
          greek = bayer[1] + suffix + ' ' + constellation;
          latin = greekNames[bayer[1]] + suffix + ' ' + constellation;
          mixed = bayer[1] + suffix + ' ' + greekNames[bayer[1]] + suffix + ' ' + constellation;
        } else if (bodyNames[token]) {
          greek = token + VS;
          latin = bodyNames[token];
          mixed = token + VS + ' ' + bodyNames[token];
        } else if (greekOnly) {
          greek = greekOnly[1] + (greekOnly[2] || '');
          latin = greekNames[greekOnly[1]] + (greekOnly[2] || '');
          mixed = greek + ' ' + latin;
        }

        fragment.append(notationSpan(greek, latin, mixed));
        last = match.index + token.length;
      }

      fragment.append(document.createTextNode(text.slice(last)));
      node.replaceWith(fragment);
    });
  }

  document.querySelectorAll('table.calendar tbody td:nth-child(3)').forEach(function (cell) {
    const visibilityPattern = /(?:👁|B|🔭)\s+V\s+\d+(?:\.\d+)?/g;
    const nodes = [];
    const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);

    while (walker.nextNode()) {
      if (visibilityPattern.test(walker.currentNode.nodeValue)) nodes.push(walker.currentNode);
      visibilityPattern.lastIndex = 0;
    }

    nodes.forEach(function (node) {
      const text = node.nodeValue;
      const fragment = document.createDocumentFragment();
      let last = 0;
      let match;
      visibilityPattern.lastIndex = 0;

      while ((match = visibilityPattern.exec(text))) {
        fragment.append(document.createTextNode(text.slice(last, match.index)));
        const span = document.createElement('span');
        span.className = 'visibility-magnitude';
        span.textContent = match[0];
        fragment.append(span);
        last = match.index + match[0].length;
      }

      fragment.append(document.createTextNode(text.slice(last)));
      node.replaceWith(fragment);
    });
  });

  document.querySelectorAll('table.calendar tbody td:nth-child(2)').forEach(function (cell) {
    const text = cell.textContent.trim();
    const match = text.match(/^([^\d]*?)(\d+)$/);
    if (!match) return;
    const number = match[2];
    cell.classList.add('zodiac-day');
    Array.from(cell.childNodes).forEach(function (node) {
      if (node.nodeType === 3) node.nodeValue = node.nodeValue.replace(/\s*\d+\s*$/, '');
    });
    const day = document.createElement('span');
    day.className = 'zodiac-day-number';
    day.textContent = number;
    cell.append(day);
  });

  const buttons = document.querySelectorAll('[data-bayer-mode]');

  function setMode(mode) {
    document.querySelectorAll('.notation-item').forEach(function (item) {
      item.textContent = item.dataset[mode] || item.dataset.greek || item.textContent;
    });
    buttons.forEach(function (button) {
      button.setAttribute('aria-pressed', button.dataset.bayerMode === mode ? 'true' : 'false');
    });
    try { localStorage.setItem('star-almanack-bayer-mode', mode); } catch (_) {}
  }

  buttons.forEach(function (button) {
    button.addEventListener('click', function () { setMode(button.dataset.bayerMode); });
  });

  let initial = 'greek';
  try {
    const saved = localStorage.getItem('star-almanack-bayer-mode');
    if (saved === 'greek' || saved === 'latin' || saved === 'mixed') initial = saved;
  } catch (_) {}

  setMode(initial);
})();
