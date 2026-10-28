/* Local PDF export: no chart or birth details leave the device. */
(() => {
  'use strict';
  const libraryURL = new URL('vendor/pdf-lib/pdf-lib-1.17.1.min.js', document.currentScript.src).href;
  let library;
  function loadLibrary() {
    if (window.PDFLib) return Promise.resolve(window.PDFLib);
    if (!library) library = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = libraryURL;
      script.onload = () => resolve(window.PDFLib);
      script.onerror = () => { library = null; script.remove(); reject(Error('Could not load PDF tools. Check your connection and try again.')); };
      document.head.append(script);
    });
    return library;
  }
  async function wheelImage(svg) {
    const copy = svg.cloneNode(true);
    copy.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    copy.setAttribute('width', '1500');
    copy.setAttribute('height', '1500');
    copy.setAttribute('style', 'font-family:"DejaVu Sans","Segoe UI Symbol","Apple Symbols",sans-serif;text-anchor:middle;dominant-baseline:central');
    copy.querySelectorAll('circle').forEach(el => { el.setAttribute('fill', 'none'); el.setAttribute('stroke', '#000'); });
    copy.querySelectorAll('rect').forEach(el => el.setAttribute('fill', '#fff'));
    copy.querySelectorAll('text').forEach(el => el.setAttribute('fill', '#000'));
    copy.querySelectorAll('line,path').forEach(el => el.setAttribute('stroke', '#000'));
    const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(copy)], {type: 'image/svg+xml'}));
    try {
      const image = new Image();
      const ready = new Promise((resolve, reject) => {
        image.onload = resolve;
        image.onerror = () => reject(Error('Could not render the chart wheel. Please try again.'));
      });
      image.src = url;
      await ready;
      return image;
    } finally { URL.revokeObjectURL(url); }
  }
  window.NativitasPDF = async (source, selection = {}) => {
    const include = {wheel: true, positions: true, aspects: true, houses: true, interpretations: false, ...selection};
    if (!['wheel', 'positions', 'aspects', 'houses', 'interpretations'].some(key => include[key])) throw Error('Choose at least one section to print.');
    if (!source?.querySelector('.wheel svg')) throw Error('Generate a chart first.');
    // Snapshot before asynchronous loading; a new calculation must not mix charts.
    const chart = source.cloneNode(true);
    const interpretationSource = include.interpretations ? (source.querySelector('.synastry-interpretations') || document.getElementById('natal-interpretations')) : null;
    if (include.interpretations && interpretationSource?.getAttribute('data-print-ready') !== 'true') throw Error('Interpretations are still loading or unavailable. Choose other sections or try again shortly.');
    const interpretations = interpretationSource?.cloneNode(true);
    chart.querySelectorAll('br').forEach(el => el.replaceWith(document.createTextNode('\n')));
    const [{PDFDocument}, wheel] = await Promise.all([loadLibrary(), include.wheel ? wheelImage(chart.querySelector('.wheel svg')) : Promise.resolve(null)]);
    const pdf = await PDFDocument.create();
    const reportTitle = source.getAttribute('data-report-title') || 'Nativitas Natal Report';
    pdf.setTitle(reportTitle);
    const W = 595, H = 842, M = 36, WIDTH = W - M * 2;
    let canvas, ctx, y;
    function newPage() {
      canvas = document.createElement('canvas');
      canvas.width = W * 2; canvas.height = H * 2;
      ctx = canvas.getContext('2d');
      if (!ctx) throw Error('PDF drawing is unavailable in this browser.');
      ctx.scale(2, 2); ctx.fillStyle = '#fff'; ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#000'; ctx.textBaseline = 'top'; y = M;
    }
    async function flush() {
      const image = await pdf.embedPng(canvas.toDataURL('image/png'));
      pdf.addPage([W, H]).drawImage(image, {x: 0, y: 0, width: W, height: H});
    }
    async function room(height) {
      if (y + height > H - M) { await flush(); newPage(); }
    }
    function lines(text, width) {
      const result = [];
      for (const paragraph of text.split('\n')) {
        let line = '';
        for (const word of paragraph.split(/\s+/)) {
          const next = line ? `${line} ${word}` : word;
          if (ctx.measureText(next).width <= width) { line = next; continue; }
          if (line) result.push(line);
          line = '';
          // Long citation URLs must wrap within the page margins too.
          for (const character of word) {
            if (line && ctx.measureText(line + character).width > width) { result.push(line); line = ''; }
            line += character;
          }
        }
        result.push(line);
      }
      return result;
    }
    async function text(value, size = 11, bold = false, keepTogether = true) {
      ctx.font = `${bold ? 'bold ' : ''}${size}px system-ui, sans-serif`;
      const wrapped = lines(value, WIDTH);
      // Keep a short paragraph together rather than orphaning its final line.
      if (keepTogether && wrapped.length * size * 1.5 <= H - 2 * M) await room(wrapped.length * size * 1.5);
      for (const line of wrapped) {
        await room(size * 1.5);
        ctx.font = `${bold ? 'bold ' : ''}${size}px system-ui, sans-serif`;
        ctx.fillText(line, M, y); y += size * 1.5;
      }
      y += 6;
    }
    newPage();
    await text(reportTitle, 21, true);
    const intro = chart.querySelector('.chart-intro');
    if (intro) await text(intro.textContent);
    const location = chart.querySelector('.chart-print-location');
    if (location) await text(location.textContent);
    const chartNote = chart.querySelector('.wheel + .chart-note');
    if (!wheel && chartNote) await text(chartNote.textContent, 10);
    if (wheel) {
      await room(WIDTH);
      ctx.drawImage(wheel, M, y, WIDTH, WIDTH); y += WIDTH + 12;
      const note = chart.querySelector('.wheel + .chart-note');
      if (note) await text(note.textContent);
      if (include.positions || include.aspects || include.houses || include.interpretations) { await flush(); newPage(); }
    }
    for (const table of chart.querySelectorAll('table')) {
      const detail = table.closest('details');
      const heading = table.getAttribute('data-print-heading') || detail?.querySelector('summary')?.textContent || table.caption?.textContent || 'Chart positions';
      const category = table.getAttribute('data-print-section') || (heading.startsWith('Major aspects') ? 'aspects' : heading.startsWith('House') ? 'houses' : 'positions');
      if (!include[category]) continue;
      await room(90); await text(heading, 15, true);
      if (table.caption) await text(table.caption.textContent, 10);
      const rows = [...table.rows];
      const headerRow = table.tHead?.rows[0];
      const columns = rows[0]?.cells.length || 1;
      const widths = columns === 3 ? [WIDTH * .47, WIDTH * .32, WIDTH * .21] : Array(columns).fill(WIDTH / columns);
      async function row(element, header) {
        ctx.font = `${header ? 'bold ' : ''}11px system-ui, sans-serif`;
        const cells = [...element.cells].map((cell, i) => lines(cell.textContent.trim(), widths[i] - 12));
        const height = Math.max(...cells.map(cell => cell.length)) * 16 + 10;
        if (y + height > H - M) {
          await flush(); newPage();
          await text(`${heading} (continued)`, 15, true);
          if (!header && headerRow) await row(headerRow, true);
        }
        ctx.font = `${header ? 'bold ' : ''}11px system-ui, sans-serif`;
        ctx.strokeStyle = '#777'; ctx.lineWidth = .5;
        let x = M;
        cells.forEach((cell, i) => {
          ctx.strokeRect(x, y, widths[i], height);
          cell.forEach((line, j) => ctx.fillText(line, x + 6, y + 5 + j * 16));
          x += widths[i];
        });
        y += height;
      }
      for (const element of rows) await row(element, element === headerRow);
      y += 12;
      for (const note of detail?.querySelectorAll('.chart-note') || []) await text(note.textContent, 10);
    }
    const key = chart.querySelector('.print-aspect-key');
    if (key && include.wheel) await text(key.textContent, 10);
    const sourceNote = [...chart.querySelectorAll('.chart-note')].find(el => el.textContent.includes('DE440s'));
    if (sourceNote) await text(sourceNote.textContent, 10);
    if (interpretations) {
      if (y > M && (include.wheel || include.positions || include.aspects || include.houses)) { await flush(); newPage(); }
      await text('Interpretations', 21, true);
      // Preserve document order, closed details, source notes and inline text.
      const blocks = [...interpretations.querySelectorAll('h2,h3,h4,summary,p,li')];
      for (let i = 0; i < blocks.length; i++) {
        const block = blocks[i];
        if (block.tagName === 'LI' && block.querySelector('p')) continue;
        let value = block.textContent.trim();
        for (const link of block.querySelectorAll('a')) {
          const href = link.getAttribute('href');
          if (/^https?:\/\//.test(href || '') && !value.includes(href)) value += ` (${href})`;
        }
        if (!value) continue;
        const heading = /^(H[234]|SUMMARY)$/.test(block.tagName);
        if (heading) {
          // Keep consecutive headings with the start of their paragraph.
          let reserve = 33;
          ctx.font = 'bold 14px system-ui, sans-serif';
          for (let j = i; j < blocks.length && /^(H[234]|SUMMARY)$/.test(blocks[j].tagName); j++) reserve += lines(blocks[j].textContent.trim(), WIDTH).length * 21 + 6;
          await room(Math.min(reserve, H - 2 * M));
        }
        await text(value, heading ? 14 : 11, heading, false);
      }
    }
    await flush();
    return new Blob([await pdf.save()], {type: 'application/pdf'});
  };
})();


