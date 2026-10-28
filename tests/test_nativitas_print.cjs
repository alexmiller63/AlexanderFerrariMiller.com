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
function environment(fixture,{exporter,share,loadError=false}={}){
 const events={},drawn=[],serialized=[],urlEvents=[];
 const document={currentScript:{src:'https://example.test/nativitas/natal-pdf.js'},head:element('head'),getElementById:()=>fixture.main,querySelector:()=>fixture.main,
  addEventListener:(n,fn)=>events[n]=fn,createTextNode:t=>element('text',t),createElement:tag=>{
   const el=element(tag);if(tag==='canvas'){
    const ctx={scale(){},fillRect(){},drawImage(){},strokeRect(){},measureText:t=>({width:t.length*6}),fillText(t,x,y){drawn.push({t,x,y,color:this.fillStyle});}};
    el.getContext=()=>ctx;
    el.toDataURL=()=> 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Zl1sAAAAASUVORK5CYII=';
   }return el;
  }};
 document.head.append=script=>{queueMicrotask(()=>script.onerror());};
 const window={PDFLib:loadError?undefined:pdfLib,addEventListener:(n,fn)=>events[n]=fn};
 if(exporter)window.NativitasPDF=exporter;
 const navigator=share?{canShare:()=>true,share}:{};
 class Image {set src(url){queueMicrotask(()=>this.onload());}}
 class XMLSerializer {serializeToString(svg){serialized.push(svg);return '<svg/>';}}
 class URLs extends URL{static createObjectURL(blob){urlEvents.push(blob);return `blob:test-${urlEvents.length}`;}static revokeObjectURL(){}}
 const context={window,document,navigator,Image,XMLSerializer,URL:URLs,Blob,File,console,queueMicrotask};
 const sandbox=vm.createContext(context);
 const run=file=>vm.runInContext(fs.readFileSync(file==='nativitas/natal-print.js' && process.env.NATIVITAS_PRINT_SOURCE ? process.env.NATIVITAS_PRINT_SOURCE : path.join(root,file),'utf8'),sandbox);
 if (!loadError) { run('nativitas/vendor/pdf-lib/pdf-lib-1.17.1.min.js'); window.PDFLib=sandbox.PDFLib; }
 return {events,drawn,serialized,urlEvents,window,run};
}
test('blocked native printing still produces visible PDF controls and a shareable file',async()=>{
 const f=chart();let shared;const env=environment(f,{exporter:async()=>new Blob(['%PDF-test'],{type:'application/pdf'}),share:async data=>{shared=data;}});
 env.window.print=()=>{};env.run('nativitas/natal-print.js');await env.events.click({target:f.button});
 const panel=f.main.querySelector('.natal-print-actions');assert.ok(panel);assert.match(panel.textContent,/PDF is ready/);
 const links=panel.querySelectorAll('a');assert.equal(links.length,2);assert.equal(links[1].download,'Nativitas-Natal-Chart.pdf');
 const buttons=panel.querySelectorAll('button');await buttons.find(b=>b.textContent==='Share PDF').events.click();assert.equal(shared.files[0].type,'application/pdf');
 buttons.find(b=>b.textContent==='Print this page').events.click();assert.match(panel.textContent,/If no print dialog opens/);assert.equal(f.button.disabled,false);
});
test('export errors are visible and the original button can retry',async()=>{
 const f=chart();const env=environment(f,{exporter:async()=>{throw Error('Network unavailable');}});env.run('nativitas/natal-print.js');await env.events.click({target:f.button});
 assert.match(f.main.textContent,/Could not prepare the PDF.*Network unavailable/);assert.equal(f.button.disabled,false);
});
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
