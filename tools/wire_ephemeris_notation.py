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
  function item(el,g,l,m,klass){el.classList.add(klass);el.dataset.greek=g;el.dataset.latin=l;el.dataset.mixed=m;}
  function prepareCalendar(){
    document.querySelectorAll('table.calendar tbody td:nth-child(2) .zodiac-glyph').forEach(function(el){
      if(el.dataset.greek)return;
      const glyph=el.textContent.replace(/\ufe0e/g,'').trim().charAt(0);
      if(signs[glyph]) item(el,glyph+VS,signs[glyph],glyph+VS+' '+signs[glyph],'calendar-notation-item');
    });
    document.querySelectorAll('table.calendar tbody td:nth-child(3) .zodiac-glyph').forEach(function(el){
      const glyph=el.textContent.replace(/\ufe0e/g,'').trim().charAt(0); if(signs[glyph])el.textContent=glyph+VS;
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
    document.querySelectorAll('table.calendar .visibility-magnitude').forEach(function(container){
      if(container.querySelector('.observing-notation-item'))return;
      const glyphs=Array.from(container.querySelectorAll(':scope > img.visibility-glyph'));
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
  function setFinder(mode){document.querySelectorAll('[data-finder-image]').forEach(function(f){f.style.display=f.dataset.finderImage===mode?'block':'none'});document.querySelectorAll('.w15-finder-strip [data-finder-mode]').forEach(function(f){f.classList.toggle('is-active',f.dataset.finderMode===mode)});}
  function setMode(mode){prepareCalendar();prepareObservingAids();prepareEphemeris();document.querySelectorAll('.calendar-notation-item,.ephemeris-notation-item').forEach(function(el){el.textContent=el.dataset[mode]||el.dataset.greek;});setObservingMode(mode);document.querySelectorAll('[data-bayer-mode]').forEach(function(b){b.setAttribute('aria-pressed',b.dataset.bayerMode===mode?'true':'false');});setFinder(mode);try{localStorage.setItem('star-almanack-bayer-mode',mode)}catch(_){}}
  document.querySelectorAll('[data-bayer-mode]').forEach(function(button){button.addEventListener('click',function(){setMode(button.dataset.bayerMode);});});let initial='greek';try{const s=localStorage.getItem('star-almanack-bayer-mode');if(s==='greek'||s==='latin'||s==='mixed')initial=s}catch(_){}setMode(initial);
})();
</script>'''


def requested_years() -> tuple[str, ...]:
    if len(sys.argv) > 1:
        years = tuple(dict.fromkeys(sys.argv[1:]))
        if any(not re.fullmatch(r"\d{4}", year) for year in years):
            raise SystemExit("Years must be four digits, e.g. 2025 2027")
        return years
    return tuple(
        path.name
        for path in sorted(Path("almanack").iterdir())
        if path.is_dir() and re.fullmatch(r"\d{4}", path.name)
    )


changed = 0
pattern = re.compile(r'<script id="ephemeris-notation-sync">.*?</script>', re.S)
for year in requested_years():
    root = Path('almanack') / year
    if not root.exists():
        continue
    for page in sorted(root.glob('W[0-9][0-9]/index.html')):
        html = page.read_text(encoding='utf-8')
        html2 = pattern.sub(lambda _m: SCRIPT, html, count=1)
        if html2 == html and 'ephemeris-notation-sync' not in html:
            html2 = html.replace('</body>', SCRIPT + '</body>', 1)
        if html2 != html:
            page.write_text(html2, encoding='utf-8')
            changed += 1
print(f'Wired calendar and ephemeris notation on {changed} weekly pages for {" ".join(requested_years())}')