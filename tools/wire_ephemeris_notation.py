from pathlib import Path
import re

SCRIPT = r'''<script id="ephemeris-notation-sync">
(function(){
  const bodies={Sun:'☉',Moon:'☽',Mercury:'☿',Venus:'♀',Mars:'♂',Jupiter:'♃',Saturn:'♄',Uranus:'♅',Neptune:'♆',Ceres:'⚳'};
  const signs={'♈':'Aries','♉':'Taurus','♊':'Gemini','♋':'Cancer','♌':'Leo','♍':'Virgo','♎':'Libra','♏':'Scorpio','♐':'Sagittarius','♑':'Capricorn','♒':'Aquarius','♓':'Pisces'};
  const VS='\ufe0e';
  function item(el,g,l,m){el.classList.add('ephemeris-notation-item');el.dataset.greek=g;el.dataset.latin=l;el.dataset.mixed=m;}
  const tables=Array.from(document.querySelectorAll('table.ephemeris'));
  tables.forEach(function(table){
    table.querySelectorAll('th').forEach(function(th){
      const txt=th.textContent.trim();
      for(const [name,glyph] of Object.entries(bodies)){
        const plain=txt.replace(/\ufe0e/g,'');
        if(plain===glyph || plain===name || plain===glyph+' '+name){item(th,glyph+VS,name,glyph+VS+' '+name);break;}
      }
    });
    table.querySelectorAll('td').forEach(function(td){
      const txt=td.textContent.trim();
      const m=txt.match(/^([♈♉♊♋♌♍♎♏♐♑♒♓])\ufe0e?\s*(.*)$/);
      if(m && signs[m[1]]){
        const rest=m[2];
        item(td,m[1]+VS+(rest?' '+rest:''),signs[m[1]]+(rest?' '+rest:''),m[1]+VS+' '+signs[m[1]]+(rest?' '+rest:''));
      }
    });
  });
  function setMode(mode){
    document.querySelectorAll('.ephemeris-notation-item').forEach(function(el){el.textContent=el.dataset[mode]||el.dataset.greek;});
    document.querySelectorAll('[data-bayer-mode]').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.bayerMode===mode));});
    try{localStorage.setItem('star-almanack-bayer-mode',mode)}catch(_){}
  }
  document.addEventListener('click',function(e){const b=e.target.closest('[data-bayer-mode]');if(b)setMode(b.dataset.bayerMode);});
  let initial='greek';
  try{const s=localStorage.getItem('star-almanack-bayer-mode');if(s==='greek'||s==='latin'||s==='mixed')initial=s}catch(_){}
  setMode(initial);
})();
</script>'''

SCRIPT_2027 = r'''<script id="ephemeris-notation-sync">
(function(){
  const bodies={Sun:'☉',Moon:'☽',Mercury:'☿',Venus:'♀',Mars:'♂',Jupiter:'♃',Saturn:'♄',Uranus:'♅',Neptune:'♆',Ceres:'⚳'};
  const signs={'♈':'Aries','♉':'Taurus','♊':'Gemini','♋':'Cancer','♌':'Leo','♍':'Virgo','♎':'Libra','♏':'Scorpio','♐':'Sagittarius','♑':'Capricorn','♒':'Aquarius','♓':'Pisces'};
  const VS='\ufe0e';

  function prepare(){
    document.querySelectorAll('table.ephemeris').forEach(function(table){
      table.querySelectorAll('th').forEach(function(th){
        if(th.dataset.greek)return;
        const txt=th.textContent.trim().replace(/\ufe0e/g,'');
        for(const [name,glyph] of Object.entries(bodies)){
          if(txt===glyph || txt===name || txt===glyph+' '+name){
            th.classList.add('ephemeris-notation-item');
            th.dataset.greek=glyph+VS;
            th.dataset.latin=name;
            th.dataset.mixed=glyph+VS+' '+name;
            break;
          }
        }
      });
      table.querySelectorAll('td').forEach(function(td){
        if(td.dataset.greek)return;
        const txt=td.textContent.trim();
        const m=txt.match(/^([♈♉♊♋♌♍♎♏♐♑♒♓])\ufe0e?\s*(.*)$/);
        if(!m || !signs[m[1]])return;
        const rest=m[2];
        td.classList.add('ephemeris-notation-item');
        td.dataset.greek=m[1]+VS+(rest?' '+rest:'');
        td.dataset.latin=signs[m[1]]+(rest?' '+rest:'');
        td.dataset.mixed=m[1]+VS+' '+signs[m[1]]+(rest?' '+rest:'');
      });
    });
  }

  function setFinder(mode){
    document.querySelectorAll('[data-finder-image]').forEach(function(f){f.style.display=f.dataset.finderImage===mode?'block':'none'});
    document.querySelectorAll('.w15-finder-strip [data-finder-mode]').forEach(function(f){f.classList.toggle('is-active',f.dataset.finderMode===mode)});
  }

  function setMode(mode){
    prepare();
    document.querySelectorAll('.ephemeris-notation-item').forEach(function(el){el.textContent=el.dataset[mode]||el.dataset.greek;});
    document.querySelectorAll('[data-bayer-mode]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.bayerMode===mode?'true':'false');});
    setFinder(mode);
    try{localStorage.setItem('star-almanack-bayer-mode',mode)}catch(_){}
  }

  document.querySelectorAll('[data-bayer-mode]').forEach(function(button){
    button.addEventListener('click',function(){setMode(button.dataset.bayerMode);});
  });

  let initial='greek';
  try{const s=localStorage.getItem('star-almanack-bayer-mode');if(s==='greek'||s==='latin'||s==='mixed')initial=s}catch(_){}
  setMode(initial);
})();
</script>'''

changed = 0
pattern = re.compile(r'<script id="ephemeris-notation-sync">.*?</script>', re.S)
for year in ('2025','2026','2027'):
    root = Path('almanack') / year
    if not root.exists():
        continue
    script = SCRIPT_2027 if year == '2027' else SCRIPT
    for page in sorted(root.glob('W[0-9][0-9]/index.html')):
        html = page.read_text(encoding='utf-8')
        html2 = pattern.sub(lambda _m: script, html, count=1)
        if html2 == html and 'ephemeris-notation-sync' not in html:
            html2 = html.replace('</body>', script + '</body>', 1)
        if html2 != html:
            page.write_text(html2, encoding='utf-8')
            changed += 1
print(f'Wired ephemeris notation on {changed} weekly pages')
