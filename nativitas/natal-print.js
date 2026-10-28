(() => {
  'use strict';
  let folded = null, pdfURL = null;
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
  const handled = new WeakSet();
  async function handlePrint(event) {
    if (handled.has(event)) return;
    const button = event.target.closest?.('[data-natal-print]');
    if (!button || button.disabled) return;
    handled.add(event);
    const chart = output();
    chart.querySelector('.natal-print-actions')?.remove();
    if (pdfURL) { URL.revokeObjectURL(pdfURL); pdfURL = null; }
    const panel = document.createElement('section');
    panel.className = 'natal-print-actions';
    panel.setAttribute('aria-label', 'Print or save your chart');
    const status = document.createElement('p');
    status.setAttribute('role', 'status');
    status.textContent = 'Preparing your black-on-white PDF…';
    panel.append(status);
    button.parentElement.after(panel);
    button.disabled = true;
    try {
      const blob = await window.NativitasPDF(chart);
      // A replacement chart discards its old export rather than showing mixed data.
      if (!panel.isConnected) return;
      pdfURL = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = pdfURL;
      link.target = '_blank'; link.rel = 'noopener';
      link.textContent = 'Open PDF';
      panel.append(link);
      const download = document.createElement('a');
      download.href = pdfURL; download.download = 'Nativitas-Natal-Chart.pdf';
      download.textContent = 'Save PDF'; panel.append(download);
      const file = new File([blob], 'Nativitas-Natal-Chart.pdf', {type: 'application/pdf'});
      if (navigator.canShare?.({files: [file]})) {
        const share = document.createElement('button');
        share.type = 'button'; share.textContent = 'Share PDF';
        share.addEventListener('click', async () => {
          try { await navigator.share({files: [file], title: 'Nativitas Natal Chart'}); }
          catch (error) { if (error.name !== 'AbortError') status.textContent = 'Sharing is unavailable. Use Open PDF or Save PDF instead.'; }
        });
        panel.append(share);
      }
      const print = document.createElement('button');
      print.type = 'button'; print.textContent = 'Print this page';
      print.addEventListener('click', () => {
        status.textContent = 'If no print dialog opens, choose Open PDF and print or share the PDF.';
        try { window.print(); }
        catch { status.textContent = 'Printing is unavailable here. Choose Open PDF to print or share the PDF.'; }
      });
      panel.append(print);
      status.textContent = 'Your PDF is ready. Open it to view, print or share, or save a copy.';
    } catch (error) {
      status.textContent = `Could not prepare the PDF. ${error.message || 'Please try again.'}`;
    } finally { button.disabled = false; }
  }
  const bound = new WeakSet();
  function bind(root) {
    for (const button of root?.querySelectorAll('[data-natal-print]') || []) {
      if (bound.has(button)) continue;
      bound.add(button);
      button.textContent = 'Prepare printable PDF';
      button.addEventListener('click', handlePrint);
    }
  }
  window.NativitasPrint = {bind};
  bind(output());
  document.addEventListener('click', handlePrint);
})();
