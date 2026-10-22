// Support both TeX delimiters and the math script tags produced by Kramdown.
window.MathJax = {
  tex: { inlineMath: [['$', '$'], ['\\(', '\\)']] },
  svg: { fontCache: 'local' },
  options: {
    renderActions: {
      findScript: [10, function (doc) {
        document.querySelectorAll('script[type^="math/tex"]').forEach(function (node) {
          const display = /;\s*mode=display/.test(node.type);
          const item = new doc.options.MathItem(node.textContent, doc.inputJax[0], display);
          const marker = document.createTextNode('');
          node.replaceWith(marker);
          item.start = { node: marker, delim: '', n: 0 };
          item.end = { node: marker, delim: '', n: 0 };
          doc.math.push(item);
        });
      }, '']
    }
  }
};
