(function () {
  const greekNames = {
    'α':'Alpha','β':'Beta','γ':'Gamma','δ':'Delta','ε':'Epsilon','ζ':'Zeta','η':'Eta','θ':'Theta',
    'ι':'Iota','κ':'Kappa','λ':'Lambda','μ':'Mu','ν':'Nu','ξ':'Xi','ο':'Omicron','π':'Pi',
    'ρ':'Rho','σ':'Sigma','τ':'Tau','υ':'Upsilon','φ':'Phi','χ':'Chi','ψ':'Psi','ω':'Omega'
  };

  const zodiacNames = {
    '♈':'Aries','♉':'Taurus','♊':'Gemini','♋':'Cancer','♌':'Leo','♍':'Virgo',
    '♎':'Libra','♏':'Scorpio','♐':'Sagittarius','♑':'Capricorn','♒':'Aquarius','♓':'Pisces'
  };

  const bodyNames = {'☉':'Sun','☽':'Moon','☿':'Mercury','♀':'Venus','♂':'Mars','♃':'Jupiter','♄':'Saturn'};
  const VS = '\ufe0e';

  function setMode(mode) {
    document.querySelectorAll('.notation-item').forEach(function (item) {
      item.textContent = item.dataset[mode] || item.dataset.greek || item.textContent;
    });

    document.querySelectorAll('[data-bayer-mode]').forEach(function (button) {
      button.setAttribute('aria-pressed', button.dataset.bayerMode === mode ? 'true' : 'false');
    });

    try { localStorage.setItem('star-almanack-bayer-mode', mode); } catch (_) {}
  }

  document.querySelectorAll('.zodiac-glyph').forEach(function (item) {
    const glyph = item.textContent.charAt(0);
    if (!zodiacNames[glyph]) return;
    item.classList.add('notation-item');
    item.dataset.greek = glyph + VS;
    item.dataset.latin = zodiacNames[glyph];
    item.dataset.mixed = glyph + VS + '\n' + zodiacNames[glyph];
  });

  document.querySelectorAll('[data-bayer-mode]').forEach(function (button) {
    button.addEventListener('click', function () { setMode(button.dataset.bayerMode); });
  });

  let initial = 'greek';
  try {
    const saved = localStorage.getItem('star-almanack-bayer-mode');
    if (saved === 'greek' || saved === 'latin' || saved === 'mixed') initial = saved;
  } catch (_) {}

  setMode(initial);
})();
