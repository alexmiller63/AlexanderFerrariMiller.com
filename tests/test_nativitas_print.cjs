/* Run: node --test tests/test_nativitas_print.cjs */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const {PDFDocument}=require('../nativitas/vendor/pdf-lib/pdf-lib-1.17.1.min.js');
const pdfLib=require('../nativitas/vendor/pdf-lib/pdf-lib-1.17.1.min.js');
// These tests exercise export and controls with browser boundaries replaced.
// Actual SVG rasterization and iPhone sharing still require a real device test.
class Element {
 constructor(tag='div',text=''){this.tagName=tag.toUpperCase();this.ownText=text;this.children=[];this.attrs={};this.events={};this.disabled=false;this.open=false;}
 get textContent(){return this.ownText+this.children.map(c=>c.textContent).join('');}
 set textContent(t){this.ownText=t;this.children=[];}
 setAttribute(k,v){this.attrs[k]=v;}
 getAttribute(k){return this.attrs[k];}
 get className(){return this.attrs.class||'';} set className(v){this.attrs.class=v;}
 append(...els){els.forEach(el=>{el.parentElement=this;this.children.push(el);});}
 before(el){const p=this.parentElement;el.parentElement=p;p.children.splice(p.children.indexOf(this),0,el);}
 replaceChildren(...els){this.children.forEach(el=>{el.parentElement=null;});this.children=[];this.ownText='';this.append(...els);}
 get childNodes(){return this.children;}
 after(el){const p=this.parentElement;el.parentElement=p;p.children.splice(p.children.indexOf(this)+1,0,el);}
 remove(){const p=this.parentElement;if(p)p.children.splice(p.children.indexOf(this),1);this.parentElement=null;}
 replaceWith(el){this.after(el);this.remove();}
 get isConnected(){return this.parentElement?this.parentElement.isConnected:this.tagName==='BODY';}
 matches(s){if(s==='details:not([open])')return this.tagName==='DETAILS'&&!this.open;if(s[0]==='.')return this.className.split(' ').includes(s.slice(1));if(s[0]==='[')return s.slice(1,-1) in this.attrs;return this.tagName===s.toUpperCase();}
 querySelectorAll(s){return this.children.flatMap(c=>[...(s.split(',').some(t=>c.matches(t))?[c]:[]),...c.querySelectorAll(s)]);}
 querySelector(s){if(s==='.wheel svg')return this.querySelector('.wheel')?.querySelector('svg');if(s==='.wheel + .chart-note'){const w=this.querySelector('.wheel');return w?.parentElement.children[w.parentElement.children.indexOf(w)+1];}return this.querySelectorAll(s)[0]||null;}
 closest(s){return this.matches(s)?this:this.parentElement?.closest(s)||null;}
 cloneNode(){const e=new Element(this.tagName,this.ownText);e.attrs={...this.attrs};e.open=this.open;this.children.forEach(c=>e.append(c.cloneNode()));return e;}
 addEventListener(event,fn){this.events[event]=fn;}
 get rows(){return this.querySelectorAll('tr');} get cells(){return this.children.filter(c=>['TD','TH'].includes(c.tagName));}
 get tHead(){return this.querySelector('thead');} get caption(){return this.querySelector('caption');}
}
function element(tag,text,cls){const e=new Element(tag,text);if(cls)e.className=cls;return e;}
function chart(rowCount=11){
 const body=new Element('body'), main=new Element('main');body.append(main);
 const holder=element('p'),button=element('button','Print / Save as PDF');button.setAttribute('data-natal-print','');holder.append(button);main.append(holder);
 main.append(element('p','January 1, 2000 · 12:00 PM UTC','chart-intro'),element('p','Location: 0°, 0°. Time zone: UTC.','chart-print-location'));
 const wheel=element('figure','','wheel'),svg=element('svg');
 for(const tag of ['circle','rect','path','line','text']){const e=element(tag);e.setAttribute('fill','#101a2c');e.setAttribute('stroke','#75b9f4');svg.append(e);}
 wheel.append(svg);main.append(wheel,element('p','Placidus houses.','chart-note'));
 for(const title of ['Planet positions','Major aspects','House cusp positions']){
  const detail=element('details');detail.append(element('summary',title));const table=element('table');const head=element('thead'),hr=element('tr');hr.append(element('th','Body'),element('th','Position'));head.append(hr);table.append(head);
  const tbody=element('tbody');for(let i=0;i<rowCount;i++){const row=element('tr');row.append(element('th',`☉ Sun ${i}`),element('td',`${i}° ♈`));tbody.append(row);}table.append(tbody);detail.append(table);main.append(detail);
 }
 main.append(element('p','Black aspect lines.','chart-note print-aspect-key'),element('p','Calculated with DE440s.','chart-note'));
 return {body,main,button};
}
function environment(fixture,{exporter,share,standalone=false,loadError=false}={}){
 const events={},drawn=[],serialized=[],urlEvents=[];let canvases=0;
 const document={currentScript:{src:'https://example.test/nativitas/natal-pdf.js'},head:element('head'),getElementById:id=>id==='natal-interpretations'?(fixture.interpretations||null):fixture.main,querySelector:()=>fixture.main,
  addEventListener:(n,fn)=>events[n]=fn,dispatchEvent:e=>events[e.type]?.(e),createTextNode:t=>element('text',t),createElement:tag=>{
   const el=element(tag);if(tag==='canvas'){const page=++canvases;
    const ctx={scale(){},fillRect(){},drawImage(){},strokeRect(){},measureText:t=>({width:t.length*6}),fillText(t,x,y){drawn.push({t,x,y,page,color:this.fillStyle});}};
    el.getContext=()=>ctx;
    el.toDataURL=()=> 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=';
   }return el;
  }};
 document.head.append=script=>{queueMicrotask(()=>script.onerror());};
 const window={PDFLib:loadError?undefined:pdfLib,addEventListener:(n,fn)=>events[n]=fn};
 if(exporter)window.NativitasPDF=exporter;
 const navigator=share?{canShare:()=>true,share}:{};
 navigator.standalone=standalone;
 class Image {set src(url){queueMicrotask(()=>this.onload());}}
 class XMLSerializer {serializeToString(svg){serialized.push(svg);return '<svg/>';}}
 class URLs extends URL{static createObjectURL(blob){urlEvents.push(blob);return `blob:test-${urlEvents.length}`;}static revokeObjectURL(){}}
 const context={window,document,navigator,Image,XMLSerializer,URL:URLs,Blob,File,Event,MutationObserver:class{constructor(fn){this.callback=fn;}observe(){}},console,queueMicrotask,setTimeout,clearTimeout};
 const sandbox=vm.createContext(context);
 const run=file=>vm.runInContext(fs.readFileSync(file==='nativitas/natal-print.js' && process.env.NATIVITAS_PRINT_SOURCE ? process.env.NATIVITAS_PRINT_SOURCE : path.join(root,file),'utf8'),sandbox);
 if (!loadError) { run('nativitas/vendor/pdf-lib/pdf-lib-1.17.1.min.js'); window.PDFLib=sandbox.PDFLib; }
 return {events,drawn,serialized,urlEvents,window,document,run};
}
test('before/after printing restores only the originally closed sections',()=>{
 const f=chart();const details=f.main.querySelectorAll('details');details[0].open=true;
 const env=environment(f);env.run('nativitas/natal-print.js');env.events.beforeprint();assert.ok(details.every(d=>d.open));env.events.afterprint();assert.deepEqual(details.map(d=>d.open),[true,false,false]);
});
test('PDF includes collapsed tables, paginates all rows and preserves the screen colors',async()=>{
 const f=chart(55),env=environment(f);env.run('nativitas/natal-pdf.js');const blob=await env.window.NativitasPDF(f.main);
 const pdf=await PDFDocument.load(await blob.arrayBuffer());assert.ok(pdf.getPageCount()>=5);assert.ok(pdf.getPages().every(p=>p.getWidth()===595&&p.getHeight()===842));
 assert.equal(env.drawn.filter(x=>x.t==='☉ Sun 54').length,3);assert.ok(env.drawn.some(x=>x.t==='Calculated with DE440s.'));assert.ok(env.drawn.every(x=>x.color==='#000'));
 assert.ok(env.drawn.every(x=>x.y>=36&&x.y<806),'no text outside page margins');
 const svg=env.serialized[0];assert.ok(svg.querySelectorAll('path,line').every(e=>e.getAttribute('stroke')==='#000'));assert.equal(svg.querySelector('rect').getAttribute('fill'),'#fff');assert.equal(svg.querySelector('circle').getAttribute('fill'),'none');
 assert.equal(f.main.querySelector('.wheel svg').querySelector('rect').getAttribute('fill'),'#101a2c');assert.ok(f.main.querySelectorAll('details').every(d=>!d.open));
});
test('a failed local library load rejects rather than leaving the UI waiting',async()=>{
 const f=chart(),env=environment(f,{loadError:true});env.run('nativitas/natal-pdf.js');await assert.rejects(env.window.NativitasPDF(f.main),/Could not load PDF tools/);
});

function toggles(f){return Object.fromEntries(f.main.querySelectorAll('input').map(i=>[i.getAttribute('data-print-section'),i]));}
function ready(f,env){
 f.interpretations=element('section');f.body.append(f.interpretations);
 f.interpretations.setAttribute('data-print-ready','true');
 f.interpretations.append(element('h3','Planets in signs'),element('p','Interpretation only text'),element('h3','Sources'),element('p','Historical source note'));
 env.events['nativitas-interpretations-ready']?.();
}
test('one button prepares selected sections, then shares the named PDF on a fresh tap',async()=>{
 const f=chart();let shared,captured,calls=0;
 const env=environment(f,{standalone:true,share:data=>{shared=data;return Promise.resolve();},exporter:async(source,selection)=>{calls++;captured=selection;return new Blob(['%PDF-test']);}});
 env.run('nativitas/natal-print.js');ready(f,env);
 assert.equal(f.main.querySelectorAll('button').length,1);
 const options=toggles(f);assert.deepEqual(Object.keys(options),['wheel','positions','aspects','houses','interpretations']);
 options.aspects.checked=false;options.aspects.events.change();
 const event={target:f.button};await f.button.events.click(event);await env.events.click(event);
 assert.equal(calls,1,'bubbling must not export twice');assert.equal(shared,undefined,'sharing needs another user tap after preparation');
 assert.equal(captured.aspects,false);assert.equal(captured.interpretations,true);
 const pending=f.button.events.click({target:f.button});assert.equal(shared.files[0].name,'Nativitas-Natal-Chart.pdf');assert.equal(shared.url,undefined);await pending;
 assert.equal(await shared.files[0].text(),'%PDF-test');assert.match(f.main.textContent,/Save to Files/);
 assert.equal(f.main.querySelectorAll('a').some(a=>a.textContent==='Open PDF'),false);
});
test('changing a toggle invalidates an already prepared PDF',async()=>{
 const f=chart();let calls=0,shares=0;
 const env=environment(f,{share:async()=>{shares++;},exporter:async()=>{calls++;return new Blob(['pdf']);}});env.run('nativitas/natal-print.js');
 await f.button.events.click({target:f.button});
 const options=toggles(f);options.wheel.checked=false;options.wheel.events.change();
 assert.equal(f.main.querySelectorAll('a').length,0);
 await f.button.events.click({target:f.button});assert.equal(calls,2);assert.equal(shares,0);
});
test('a selection changed while exporting discards the old result',async()=>{
 const f=chart();let finish;
 const env=environment(f,{exporter:()=>new Promise(resolve=>{finish=resolve;})});env.run('nativitas/natal-print.js');
 const pending=f.button.events.click({target:f.button});const options=toggles(f);options.positions.checked=false;options.positions.events.change();
 finish(new Blob(['old']));await pending;assert.equal(f.main.querySelectorAll('a').length,0);assert.equal(f.button.disabled,false);
});
test('no sections selected gives a useful message instead of an empty PDF',async()=>{
 const f=chart();let calls=0;const env=environment(f,{exporter:async()=>{calls++;}});env.run('nativitas/natal-print.js');
 for(const input of Object.values(toggles(f)))input.checked=false;
 await f.button.events.click({target:f.button});assert.equal(calls,0);assert.match(f.main.textContent,/Choose at least one/);
});
test('loading interpretations and absent houses are unavailable without blocking chart export',async()=>{
 const f=chart();f.main.querySelectorAll('details').find(d=>d.querySelector('summary').textContent==='House cusp positions').remove();
 const env=environment(f);env.run('nativitas/natal-print.js');let options=toggles(f);
 assert.equal(options.interpretations.disabled,true);assert.equal(options.houses.disabled,true);assert.equal(options.houses.checked,false);
 ready(f,env);assert.equal(options.interpretations.disabled,false);
});
test('export and share errors remain retryable with a named download fallback',async()=>{
 const f=chart();let attempts=0;
 const env=environment(f,{standalone:true,exporter:async()=>{if(++attempts===1)throw Error('Offline');return new Blob(['pdf']);},share:async()=>{throw Error('Unavailable');}});
 env.run('nativitas/natal-print.js');await f.button.events.click({target:f.button});assert.match(f.main.textContent,/Offline/);assert.equal(f.button.disabled,false);
 await f.button.events.click({target:f.button});await f.button.events.click({target:f.button});assert.match(f.main.textContent,/Files/);
 assert.equal(f.main.querySelectorAll('a')[0].download,'Nativitas-Natal-Chart.pdf');
});
test('desktop PDF uses the same button and opens only the prepared document',async()=>{
 const f=chart();let opened;const env=environment(f,{exporter:async()=>new Blob(['pdf'])});env.window.open=url=>{opened=url;};env.run('nativitas/natal-print.js');
 await f.button.events.click({target:f.button});assert.equal(opened,undefined);
 await f.button.events.click({target:f.button});assert.match(opened,/^blob:/);assert.equal(f.main.querySelectorAll('button').length,1);
});
const emptySelection={wheel:false,positions:false,aspects:false,houses:false,interpretations:false};
for(const key of Object.keys(emptySelection))test(`PDF can include only ${key}`,async()=>{
 const f=chart(),env=environment(f);ready(f,env);env.run('nativitas/natal-pdf.js');
 const blob=await env.window.NativitasPDF(f.main,{...emptySelection,[key]:true});const pdf=await PDFDocument.load(await blob.arrayBuffer());
 assert.ok(pdf.getPageCount()>=1);assert.ok(env.drawn.some(x=>x.t.includes('January 1')));assert.ok(env.drawn.some(x=>x.t.includes('Location:')));
 for(const [category,heading] of [['positions','Planet positions'],['aspects','Major aspects'],['houses','House cusp positions']])assert.equal(env.drawn.some(x=>x.t===heading),key===category);
 assert.equal(env.serialized.length,key==='wheel'?1:0);assert.equal(env.drawn.some(x=>x.t==='Interpretation only text'),key==='interpretations');
 if(key==='interpretations')assert.ok(env.drawn.some(x=>x.t==='Historical source note'));
});
test('PDF rejects empty selections and interpretations that are not ready',async()=>{
 const f=chart(),env=environment(f);env.run('nativitas/natal-pdf.js');
 await assert.rejects(env.window.NativitasPDF(f.main,emptySelection),/Choose at least one/);
 await assert.rejects(env.window.NativitasPDF(f.main,{...emptySelection,interpretations:true}),/still loading or unavailable/);
});
test('interpretations cannot be replaced by a slower previous chart',async()=>{
 const f=chart(),env=environment(f);ready(f,env);const pending=[];
 env.window.NativitasDraftLibrary={natal:(data,target)=>new Promise(resolve=>{pending.push(()=>{target.append(element('p',data.label));resolve();});})};
 env.run('nativitas/interpretations.js');
 const first=env.window.NativitasInterpretations.render({label:'Previous chart'}),second=env.window.NativitasInterpretations.render({label:'Current chart'});
 assert.equal(f.interpretations.getAttribute('data-print-ready'),'false');
 pending[1]();await second;pending[0]();await first;
 assert.equal(f.interpretations.textContent,'Current chart');assert.equal(f.interpretations.getAttribute('data-print-ready'),'true');
});

test('long interpretations and source URLs paginate inside the margins with every section selected',async()=>{
 const f=chart(),env=environment(f);ready(f,env);
 for(let i=0;i<150;i++)f.interpretations.append(element('p',`Interpretation paragraph ${i}: `+'A traditional theme. '.repeat(8)));
 const paragraph=element('p','Source: '),link=element('a','Read the source');link.setAttribute('href','https://example.org/'+'a'.repeat(200));paragraph.append(link);f.interpretations.append(paragraph);
 env.run('nativitas/natal-pdf.js');const blob=await env.window.NativitasPDF(f.main,{interpretations:true});
 const pdf=await PDFDocument.load(await blob.arrayBuffer());assert.ok(pdf.getPageCount()>5);
 assert.ok(env.drawn.some(x=>x.t.includes('paragraph 149:')));assert.ok(env.drawn.some(x=>x.t==='Sources'));
 assert.ok(env.drawn.every(x=>x.y>=36&&x.y<806));assert.ok(env.drawn.every(x=>x.x+x.t.length*6<=559));
});

test('Home Screen without file sharing downloads rather than opening a blob viewer',async()=>{
 const f=chart(),env=environment(f,{standalone:true,exporter:async()=>new Blob(['pdf'])});let opened=0,saved=0;
 env.window.open=()=>{opened++;};env.run('nativitas/natal-print.js');await f.button.events.click({target:f.button});
 const save=f.main.querySelectorAll('a')[0];save.click=()=>{saved++;};
 await f.button.events.click({target:f.button});assert.equal(opened,0);assert.equal(saved,1);assert.match(f.main.textContent,/Files/);
});

test('interpretation headings stay on the same page as their first paragraph lines',async()=>{
 const f=chart(),env=environment(f);ready(f,env);
 for(let i=0;i<80;i++)f.interpretations.append(element('h4',`Heading ${i}`),element('p',`Paragraph ${i}: `+'Long interpretation prose. '.repeat(12)));
 env.run('nativitas/natal-pdf.js');await env.window.NativitasPDF(f.main,{...emptySelection,interpretations:true});
 for(let i=0;i<80;i++){
  const heading=env.drawn.find(x=>x.t===`Heading ${i}`),paragraph=env.drawn.find(x=>x.t.startsWith(`Paragraph ${i}:`));
  assert.equal(heading.page,paragraph.page,`Heading ${i} was orphaned`);
 }
});
