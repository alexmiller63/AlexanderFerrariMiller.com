from pathlib import Path
import re
import sys

SCRIPT = r'''<script id="ephemeris-notation-sync">
(function(){
  const bodies={Sun:'☉',Moon:'☽',Mercury:'☿',Venus:'♀',Mars:'♂',Jupiter:'♃',Saturn:'♄',Uranus:'♅',Neptune:'♆',Ceres:'⚳',Pluto:'♇'};
  const signs={'♈':'Aries','♉':'Taurus','♊':'Gemini','♋':'Cancer','♌':'Leo','♍':'Virgo','♎':'Libra','♏':'Scorpio','♐':'Sagittarius','♑':'Capricorn','♒':'Aquarius','♓':'Pisces'};
  const greekNames={'α':'Alpha','β':'Beta','γ':'Gamma','δ':'Delta','ε':'Epsilon','ζ':'Zeta','η':'Eta','θ':'Theta','ι':'Iota','κ':'Kappa','λ':'Lambda','μ':'Mu','ν':'Nu','ξ':'Xi','ο':'Omicron','π':'Pi','ρ':'Rho','σ':'Sigma','τ':'Tau','υ':'Upsilon','φ':'Phi','χ':'Chi','ψ':'Psi','ω':'Omega'};
  const constellations={And:'Andromedae',Ant:'Antliae',Aps:'Apodis',Aqr:'Aquarii',Aql:'Aquilae',Ara:'Arae',Ari:'Arietis',Aur:'Aurigae',Boo:'Bootis',Cae:'Caeli',Cam:'Camelopardalis',Cnc:'Cancri',CVn:'Canum Venaticorum',CMa:'Canis Majoris',CMi:'Canis Minoris',Cap:'Capricorni',Car:'Carinae',Cas:'Cassiopeiae',Cen:'Centauri',Cep:'Cephei',Cet:'Ceti',Cha:'Chamaeleontis',Cir:'Circini',Col:'Columbae',Com:'Comae Berenices',CrA:'Coronae Australis',CrB:'Coronae Borealis',Crv:'Corvi',Crt:'Crateris',Cru:'Crucis',Cyg:'Cygni',Del:'Delphini',Dor:'Doradus',Dra:'Draconis',Equ:'Equulei',Eri:'Eridani',For:'Fornacis',Gem:'Geminorum',Gru:'Gruis',Her:'Herculis',Hor:'Horologii',Hya:'Hydrae',Hyi:'Hydri',Ind:'Indi',Lac:'Lacertae',Leo:'Leonis',LMi:'Leonis Minoris',Lep:'Leporis',Lib:'Librae',Lup:'Lupi',Lyn:'Lyncis',Lyr:'Lyrae',Men:'Mensae',Mic:'Microscopii',Mon:'Monocerotis',Mus:'Muscae',Nor:'Normae',Oct:'Octantis',Oph:'Ophiuchi',Ori:'Orionis',Pav:'Pavonis',Peg:'Pegasi',Per:'Persei',Phe:'Phoenicis',Pic:'Pictoris',Psc:'Piscium',PsA:'Piscis Austrini',Pup:'Puppis',Pyx:'Pyxidis',Ret:'Reticuli',Sge:'Sagittae',Sgr:'Sagittarii',Sco:'Scorpii',Scl:'Sculptoris',Sct:'Scuti',Ser:'Serpentis',Sex:'Sextantis',Tau:'Tauri',Tel:'Telescopii',Tri:'Trianguli',TrA:'Trianguli Australis',Tuc:'Tucanae',UMa:'Ursae Majoris',UMi:'Ursae Minoris',Vel:'Velorum',Vir:'Virginis',Vol:'Volantis',Vul:'Vulpeculae'};
  const observingNames={eye:'Naked eye',binoculars:'Binoculars',telescope:'Telescope'};
  const VS='\ufe0e';
  function item(el,g,l,m,klass){el.classList.add(klass);if(klass==='calendar-notation-item')el.classList.remove('zodiac-glyph','greek-letter');if(klass==='ephemeris-notation-item')el.classList.remove('ephemeris-symbol','zodiac-glyph','greek-letter');el.dataset.greek=g;el.dataset.latin=l;el.dataset.mixed=m;}
  function prepareCalendar(){
    document.querySelectorAll('table.calendar tbody td:nth-child(2) .zodiac-glyph').forEach(function(el){
      if(el.dataset.greek)return;
      const glyph=el.textContent.replace(/\ufe0e/g,'').trim().charAt(0);
      if(signs[glyph]) item(el,glyph+VS,signs[glyph],glyph+VS+' '+signs[glyph],'calendar-notation-item');
    });
    document.querySelectorAll('table.calendar tbody td:nth-child(3) .zodiac-glyph').forEach(function(el){
      const glyph=el.textContent.replace(/\ufe0e/g,'').trim().charAt(0); if(signs[glyph])el.textContent=glyph+VS;
    });
    /* Normalize Bayer designations whose Greek letter has already been wrapped
       by calendar generation, e.g. <span class="greek-letter">ε</span> Peg.
       Treat the Greek letter plus following 3-letter constellation abbreviation
       as one notation item so Latin mode can render the proper genitive (Pegasi). */
    document.querySelectorAll('table.calendar tbody td:nth-child(3) .greek-letter').forEach(function(el){
      if(el.closest('.calendar-notation-item'))return;
      const letter=el.textContent.replace(/\ufe0e/g,'').trim();
      if(!greekNames[letter])return;
      const next=el.nextSibling;
      if(!next||next.nodeType!==Node.TEXT_NODE)return;
      const m=next.nodeValue.match(/^(\d+)?\s+([A-Z][A-Za-z]{2})\b/);
      if(!m)return;
      const suffix=m[1]||'',abbr=m[2],constellation=constellations[abbr]||abbr;
      const span=document.createElement('span');
      const greek=letter+suffix+' '+abbr;
      const latin=(greekNames[letter]||letter)+suffix+' '+constellation;
      const mixed=letter+suffix+' '+(greekNames[letter]||letter)+suffix+' '+constellation;
      item(span,greek,latin,mixed,'calendar-notation-item');
      span.textContent=greek;
      next.nodeValue=next.nodeValue.slice(m[0].length);
      el.replaceWith(span);
    });
    const pattern=/([αβγδεζηθικλμνξοπρστυφχψω])(\d+)?\s+([A-Z][A-Za-z]{2})\b/g;
    document.querySelectorAll('table.calendar tbody td:nth-child(3)').forEach(function(cell){
      const nodes=[]; const walker=document.createTreeWalker(cell,NodeFilter.SHOW_TEXT);
      while(walker.nextNode()){const parent=walker.currentNode.parentElement;pattern.lastIndex=0;if(parent&&!parent.closest('.calendar-notation-item')&&pattern.test(walker.currentNode.nodeValue))nodes.push(walker.currentNode);}
      nodes.forEach(function(node){const text=node.nodeValue,frag=document.createDocumentFragment();let last=0,m;pattern.lastIndex=0;while((m=pattern.exec(text))){frag.append(document.createTextNode(text.slice(last,m.index)));const suffix=m[2]||'',greek=m[1]+suffix+' '+m[3],latin=(greekNames[m[1]]||m[1])+suffix+' '+(constellations[m[3]]||m[3]),mixed=m[1]+suffix+' '+(greekNames[m[1]]||m[1])+suffix+' '+(constellations[m[3]]||m[3]);const span=document.createElement('span');item(span,greek,latin,mixed,'calendar-notation-item');span.textContent=greek;frag.append(span);last=m.index+m[0].length;}frag.append(document.createTextNode(text.slice(last)));node.replaceWith(frag);});
    });
  }
  function aidKind(img){
    const src=(img.getAttribute('src')||'').split('/').pop()||'';
    return src.replace(/\.svg(?:\?.*)?$/,'');
  }
  function prepareObservingAids(){
    document.querySelectorAll('table.calendar .visibility-magnitude, table.ephemeris tr.ephemeris-visibility td').forEach(function(container){
      if(container.querySelector('.observing-notation-item'))return;
      const glyphs=Array.from(container.querySelectorAll(':scope > img.visibility-glyph, :scope > .substantial-telescope img.visibility-glyph'));
      if(!glyphs.length)return;
      const kinds=glyphs.map(aidKind);
      let label;
      if(kinds.length===2&&kinds.every(function(kind){return kind==='telescope';})){
        label='Substantial telescope';
      }else{
        label=kinds.map(function(kind){return observingNames[kind]||'';}).filter(Boolean).join(' / ');
      }
      if(!label)return;
      const greekHtml=glyphs.map(function(img){return img.outerHTML;}).join('');
      const span=document.createElement('span');
      span.className='observing-notation-item';
      span.dataset.greekHtml=greekHtml;
      span.dataset.latin=label;
      span.dataset.mixedHtml=greekHtml+' '+label;
      glyphs[0].before(span);
      glyphs.forEach(function(img){img.remove();});
    });
  }
  function prepareEphemeris(){
    document.querySelectorAll('table.ephemeris').forEach(function(table){
      table.querySelectorAll('th').forEach(function(th){
        if(th.dataset.greek)return;
        const txt=th.textContent.trim().replace(/\ufe0e/g,'');
        for(const [name,glyph] of Object.entries(bodies)){
          if(txt===glyph||txt===name||txt===glyph+' '+name){
            th.textContent=glyph+VS;
            item(th,glyph+VS,name,glyph+VS+' '+name,'ephemeris-notation-item');
            break;
          }
        }
      });
      table.querySelectorAll('td .ephemeris-symbol').forEach(function(el){
        if(el.dataset.greek)return;
        const glyph=el.textContent.replace(/\ufe0e/g,'').trim().charAt(0);
        if(signs[glyph]) item(el,glyph+VS,signs[glyph],glyph+VS+' '+signs[glyph],'ephemeris-notation-item');
      });
    });
  }
  function setObservingMode(mode){
    document.querySelectorAll('.observing-notation-item').forEach(function(el){
      if(mode==='latin')el.textContent=el.dataset.latin||'';
      else if(mode==='mixed')el.innerHTML=el.dataset.mixedHtml||el.dataset.greekHtml||'';
      else el.innerHTML=el.dataset.greekHtml||'';
    });
  }
  function setFinder(mode){
    document.querySelectorAll('[data-finder-image]').forEach(function(f){
      f.style.display=f.dataset.finderImage===mode?'block':'none';
    });
    document.querySelectorAll('.w15-finder-strip [data-finder-mode]').forEach(function(f){
      const active=f.dataset.finderMode===mode;
      f.classList.toggle('is-active',active);
      f.hidden=!active;
      f.style.display=active?'block':'none';
    });
  }
  function renderNotation(el,value,mode){el.textContent='';if(mode==='latin'){el.textContent=value;return;}const m=value.match(/^([αβγδεζηθικλμνξοπρστυφχψω♈♉♊♋♌♍♎♏♐♑♒♓☉☽☿♀♂♃♄♅♆⚳♇])(\ufe0e)?(.*)$/u);if(!m){el.textContent=value;return;}const symbol=document.createElement('span');symbol.className=el.classList.contains('ephemeris-notation-item')?'ephemeris-symbol':'calendar-symbol';symbol.textContent=m[1]+(m[2]||'');el.append(symbol);if(m[3])el.append(document.createTextNode(m[3]));}
  function setMode(mode){prepareCalendar();prepareObservingAids();prepareEphemeris();document.querySelectorAll('.calendar-notation-item,.ephemeris-notation-item').forEach(function(el){renderNotation(el,el.dataset[mode]||el.dataset.greek,mode);});setObservingMode(mode);document.querySelectorAll('[data-bayer-mode]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.bayerMode===mode?'true':'false');});setFinder(mode);try{localStorage.setItem('star-almanack-bayer-mode',mode)}catch(_){}}
  function setModeKeepingControlStill(button,mode){
    const control=button.closest('.section-notation-toggle')||button;
    const before=control.getBoundingClientRect().top;
    setMode(mode);
    const after=control.getBoundingClientRect().top;
    const delta=after-before;
    if(Math.abs(delta)>0.5) window.scrollBy(0,delta);
  }
  document.querySelectorAll('[data-bayer-mode]').forEach(function(button){button.addEventListener('click',function(){setModeKeepingControlStill(button,button.dataset.bayerMode);});});let initial='greek';try{const s=localStorage.getItem('star-almanack-bayer-mode');if(s==='greek'||s==='latin'||s==='mixed')initial=s}catch(_){}setMode(initial);
})();
</script>'''


def requested_pages() -> tuple[Path, ...]:
    if len(sys.argv) not in (3, 5):
        raise SystemExit("Usage: wire_ephemeris_notation.py START_YEAR START_WEEK [END_YEAR END_WEEK]")
    try:
        start_year, start_week = int(sys.argv[1]), int(sys.argv[2])
        end_year, end_week = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) == 5 else (start_year, start_week)
        start = __import__("datetime").date.fromisocalendar(start_year, start_week, 1)
        end = __import__("datetime").date.fromisocalendar(end_year, end_week, 1)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid ISO week range: {exc}") from exc
    if end < start:
        raise SystemExit("End ISO week must not precede Start ISO week")
    pages = []
    for root in sorted(Path("almanack").iterdir()):
        if not (root.is_dir() and re.fullmatch(r"\d{4}", root.name)):
            continue
        year = int(root.name)
        for page in sorted(root.glob("W[0-9][0-9]/index.html")):
            week = int(page.parent.name[1:])
            try:
                monday = __import__("datetime").date.fromisocalendar(year, week, 1)
            except ValueError:
                continue
            if start <= monday <= end:
                pages.append(page)
    return tuple(pages)


pages = requested_pages()
changed = 0
pattern = re.compile(r'<script id="ephemeris-notation-sync">.*?</script>', re.S)
for page in pages:
    html = page.read_text(encoding='utf-8')
    html2 = pattern.sub(lambda _m: SCRIPT, html, count=1)
    if html2 == html and 'ephemeris-notation-sync' not in html:
        html2 = html.replace('</body>', SCRIPT + '</body>', 1)
    if html2 != html:
        page.write_text(html2, encoding='utf-8')
        changed += 1
print(f'Wired calendar and ephemeris notation on {changed} weekly pages')