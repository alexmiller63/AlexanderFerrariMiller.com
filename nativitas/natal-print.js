(() => {
  'use strict';
  let folded = null, current = null;
  const output = () => document.getElementById('natal-chart-output') || document.querySelector('main');
  window.addEventListener('beforeprint', () => {
    if (folded !== null) return;
    folded = [...(output()?.querySelectorAll('details:not([open])') || [])];
    folded.forEach(section => { section.open = true; });
  });
  window.addEventListener('afterprint', () => {
    folded?.forEach(section => { section.open = false; });
    folded = null;
  });
  const choices = [
    ['wheel', 'Chart wheel'], ['positions', 'Planet positions'],
    ['aspects', 'Major aspects'], ['houses', 'House cusps'],
    ['interpretations', 'Interpretations']
  ];
  const bound = new WeakMap(), handled = new WeakSet();
  function clearPDF(state) {
    state.revision++;
    state.file = null;
    if (state.url) URL.revokeObjectURL(state.url);
    state.url = null;
    state.panel.replaceChildren();
    state.panel.append(state.status);
    state.status.textContent = 'Choose what to include, then tap Print or save PDF.';
  }
  function interpretationReady(state) {
    const ready = (state.chart.querySelector('.synastry-interpretations') || document.getElementById('natal-interpretations'))?.getAttribute('data-print-ready') === 'true';
    const input = state.inputs.interpretations;
    if (input.disabled === !ready) return;
    input.disabled = !ready;
    state.interpretationLabel.textContent = ready ? 'Interpretations' : 'Interpretations (loading or unavailable)';
    clearPDF(state);
  }
  document.addEventListener('nativitas-interpretations-ready', () => {
    if (current?.button.isConnected) interpretationReady(current);
  });
  async function handlePrint(event) {
    if (handled.has(event)) return;
    const button = event.target.closest?.('[data-natal-print]');
    if (!button || button.disabled) return;
    handled.add(event);
    const state = bound.get(button);
    if (!state) return;
    const {status} = state;
    if (state.file) {
      // This click supplies activation; do not load or render before sharing.
      if (state.canShare) {
        status.textContent = 'Choose Print in the share sheet. If Print is missing, choose Save to Files, then open the PDF in Files and choose Share → Print.';
        try { await navigator.share({files: [state.file]}); }
        catch (error) {
          if (error.name !== 'AbortError') status.textContent = 'Sharing is unavailable. Choose Save PDF, then open the downloaded PDF in Files and choose Share → Print.';
        }
      } else if (state.homeScreen) {
        status.textContent = 'Open the saved PDF in Files and choose Share → Print.';
        state.save.click();
      } else {
        status.textContent = 'Open the PDF to print it, or choose Save PDF to keep a copy.';
        try { window.open(state.url, '_blank', 'noopener'); }
        catch { status.textContent = 'Choose Open PDF or Save PDF below to print or keep your PDF.'; }
      }
      return;
    }
    const selection = Object.fromEntries(Object.entries(state.inputs).map(([key, input]) => [key, input.checked && !input.disabled]));
    if (!Object.values(selection).some(Boolean)) {
      status.textContent = 'Choose at least one section to print.';
      return;
    }
    const revision = state.revision;
    button.disabled = true;
    status.textContent = 'Preparing your selected sections as a black-on-white PDF…';
    try {
      const blob = await window.NativitasPDF(state.chart, selection);
      if (!button.isConnected || state.revision !== revision) return;
      state.file = new File([blob], state.chart.id === 'synastry-results' ? 'Nativitas-Synastry.pdf' : 'Nativitas-Natal-Chart.pdf', {type: 'application/pdf'});
      state.url = URL.createObjectURL(blob);
      state.canShare = false;
      try { state.canShare = typeof navigator.share === 'function' && !!navigator.canShare?.({files: [state.file]}); } catch { /* Download remains available. */ }
      // Keep the working iPhone file handoff, rather than a standalone blob viewer.
      const homeScreen = navigator.standalone === true || window.matchMedia?.('(display-mode: standalone)').matches === true;
      state.homeScreen = homeScreen;
      if (!homeScreen) {
        const open = document.createElement('a');
        open.href = state.url; open.target = '_blank'; open.rel = 'noopener';
        open.textContent = 'Open PDF'; state.panel.append(open);
      }
      const save = document.createElement('a');
      save.href = state.url; save.download = state.file.name;
      save.textContent = 'Save PDF'; state.panel.append(save);
      state.save = save;
      status.textContent = state.canShare
        ? 'Your selected PDF is ready. Tap Print or save PDF again to choose Print or Save to Files.'
        : homeScreen
          ? 'Your selected PDF is ready. Tap Print or save PDF again to save it, then open it in Files and choose Share → Print.'
          : 'Your selected PDF is ready. Tap Print or save PDF again to open it, or choose Save PDF below.';
    } catch (error) {
      if (state.revision === revision && button.isConnected) status.textContent = `Could not prepare the PDF. ${error.message || 'Please try again.'}`;
    } finally { button.disabled = false; }
  }
  function bind(root) {
    for (const button of root?.querySelectorAll('[data-natal-print]') || []) {
      if (bound.has(button)) continue;
      if (current) clearPDF(current);
      const interpretations = root.querySelector('.synastry-interpretations') || document.getElementById('natal-interpretations');
      interpretations?.setAttribute('data-print-ready', 'false');
      const fieldset = document.createElement('fieldset');
      fieldset.className = 'natal-print-options';
      const legend = document.createElement('legend');
      legend.textContent = 'Include in your PDF'; fieldset.append(legend);
      const state = {button, chart: root, inputs: {}, revision: 0};
      for (const [key, title] of choices) {
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox'; input.checked = true;
        input.setAttribute('data-print-section', key);
        if (key === 'houses' && ![...root.querySelectorAll('summary')].some(el => el.textContent.startsWith('House'))) { input.checked = false; input.disabled = true; }
        const text = document.createElement('span'); text.textContent = key === 'houses' && root.id === 'synastry-results' ? 'House overlays' : title;
        label.append(input, text); fieldset.append(label);
        state.inputs[key] = input;
        if (key === 'interpretations') state.interpretationLabel = text;
        input.addEventListener('change', () => clearPDF(state));
      }
      const wheel = root.querySelector('.wheel');
      if (wheel) {
        const sizes = document.createElement('fieldset');
        sizes.className = 'natal-view-controls';
        const sizeTitle = document.createElement('legend'); sizeTitle.textContent = 'On-screen chart size'; sizes.append(sizeTitle);
        for (const size of ['small', 'large']) {
          const label = document.createElement('label');
          const input = document.createElement('input');
          input.type = 'radio'; input.name = 'natal-screen-chart-size'; input.value = size;
          input.checked = size === 'large';
          input.setAttribute('data-chart-view-size', size);
          const text = document.createElement('span'); text.textContent = size === 'small' ? 'Small' : 'Large';
          label.append(input, text); sizes.append(label);
          input.addEventListener('change', () => {
            if (!input.checked) return;
            wheel.setAttribute('data-chart-view-size', size);
            root.setAttribute('data-chart-view-size', size);
          });
        }
        wheel.setAttribute('data-chart-view-size', 'large');
        root.setAttribute('data-chart-view-size', 'large');
        wheel.before(sizes);
      }
      button.parentElement.before(fieldset);
      state.panel = document.createElement('section');
      state.panel.className = 'natal-print-actions';
      state.panel.setAttribute('aria-label', 'Printable PDF');
      state.status = document.createElement('p'); state.status.setAttribute('role', 'status');
      button.parentElement.after(state.panel);
      bound.set(button, state); current = state;
      button.textContent = 'Print or save PDF';
      button.addEventListener('click', handlePrint);
      clearPDF(state);
      interpretationReady(state);
    }
  }
  window.NativitasPrint = {bind, invalidate: () => { if (current) clearPDF(current); }};
  bind(output());
  document.addEventListener('click', handlePrint);
})();

