(() => {
  'use strict';
  const core=window.NativitasSynastry, scriptURL=document.currentScript.src;
  const base=new URL('../star-almanack/',scriptURL), form=document.getElementById('synastry-form');
  if(!form)return;
  const status=document.getElementById('synastry-status'), results=document.getElementById('synastry-results');
  const progress=document.getElementById('synastry-progress'), bar=progress.querySelector('progress');
  const submit=document.getElementById('synastry-calculate'),cancel=document.getElementById('synastry-cancel');
  let worker, pending, busy=false, generation=0, downloadURL, citiesPromise;
  const escape=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const title=s=>s[0].toUpperCase()+s.slice(1);
  const symbols={sun:'☉',moon:'☽',mercury:'☿',venus:'♀',mars:'♂',ceres:'Ce',jupiter:'♃',saturn:'♄',uranus:'♅',neptune:'♆',pluto:'♇'};
  const signs=['♈','♉','♊','♋','♌','♍','♎','♏','♐','♑','♒','♓'].map(glyph=>glyph+'\uFE0E');
  const position=x=>{const n=Math.round(core.angle(x)*60)%21600;return `${signs[Math.floor(n/1800)]} ${Math.floor(n%1800/60)}°${String(n%60).padStart(2,'0')}′`;};
  const people=document.getElementById('synastry-people');
  for(let i=0;i<2;i++){
    const field=document.createElement('fieldset');field.dataset.person=i;
    field.innerHTML=`<legend>Person ${i+1}</legend><div class="syn-grid">
      <label class="wide">Name or label (optional)<input name="label" maxlength="80" autocomplete="off"></label>
      <label class="wide">Find birth city<input type="search" name="city" placeholder="City and country" autocomplete="off" aria-controls="syn-cities-${i}"></label>
      <div class="city-matches wide" id="syn-cities-${i}" aria-label="City matches"></div>
      <label>Birth date<input name="date" type="date" min="1900-01-01" max="2099-12-31" required></label>
      <label>Local birth time<input name="time" type="time" step="60" required></label>
      <label class="wide check"><input name="unknown" type="checkbox">Birth time unknown</label>
      <label class="wide">Time zone<input name="zone" list="synastry-zones" placeholder="e.g. America/Los_Angeles" required autocomplete="off"></label>
      <label>Latitude (north positive)<input name="latitude" type="number" step="any" min="-90" max="90" required></label>
      <label>Longitude (east positive)<input name="longitude" type="number" step="any" min="-180" max="180" required></label>
      <label class="wide occurrence" hidden>Repeated clock time<select name="occurrence"></select></label>
      <p class="hint wide">Choose a city to fill coordinates and time zone, or enter them manually.</p></div>`;
    people.append(field);
  }
  const fields=[...people.querySelectorAll('fieldset')];
  const control=(field,name)=>field.querySelector(`[name="${name}"]`);
  const value=(field,name)=>control(field,name).value.trim();
  const fold=s=>s.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();
  for(const zone of ['UTC',...(typeof Intl.supportedValuesOf==='function'?Intl.supportedValuesOf('timeZone'):[])]){
    const option=document.createElement('option');option.value=zone;document.getElementById('synastry-zones').append(option);
  }
  function occurrences(field){
    const select=control(field,'occurrence'), previous=select.value;
    select.replaceChildren();field.querySelector('.occurrence').hidden=true;
    let times;
    try{times=core.localInstants(value(field,'date'),control(field,'unknown').checked?'12:00':value(field,'time'),value(field,'zone'));}catch{return [];}
    if(times.length>1){
      field.querySelector('.occurrence').hidden=false;
      const empty=document.createElement('option');empty.value='';empty.textContent='Choose first or second occurrence';select.append(empty);
      times.forEach((t,i)=>{const option=document.createElement('option');option.value=String(t);option.textContent=`${i===0?'First':'Second'} · ${new Date(t).toISOString().slice(11,16)} UTC`;select.append(option);});
      if(times.some(t=>String(t)===previous))select.value=previous;
    }
    return times;
  }
  async function cityData(){
    if(!citiesPromise)citiesPromise=fetch(new URL('assets/ephemera/cities.json',base)).then(r=>{if(!r.ok)throw Error('City search unavailable; enter coordinates and time zone manually.');return r.json();}).then(rows=>rows.map(row=>({row,text:fold(row[1]+' '+row[2])}))).catch(e=>{citiesPromise=null;throw e;});
    return citiesPromise;
  }
  fields.forEach(field=>{
    for(const name of ['date','time','zone'])control(field,name).addEventListener('change',()=>occurrences(field));
    control(field,'unknown').addEventListener('change',()=>{const unknown=control(field,'unknown').checked;control(field,'time').disabled=unknown;control(field,'time').required=!unknown;occurrences(field);});
    control(field,'city').addEventListener('input',async()=>{
      const query=value(field,'city'), target=field.querySelector('.city-matches');target.replaceChildren();
      if(query.length<2)return;
      try{
        const rows=await cityData();if(busy||value(field,'city')!==query)return;
        const tokens=fold(query).split(/\s+/), matches=rows.filter(x=>tokens.every(t=>x.text.includes(t))).slice(0,10);
        for(const {row} of matches){const button=document.createElement('button');button.type='button';button.textContent=`${row[1]} · ${row[6]}`;
          button.addEventListener('click',()=>{if(busy)return;control(field,'city').value=row[1];control(field,'latitude').value=row[3];control(field,'longitude').value=row[4];control(field,'zone').value=row[6];target.replaceChildren();occurrences(field);});target.append(button);}
        field.querySelector('.hint').textContent=matches.length?'Choose a match to fill coordinates and time zone.':'No match. Add a country, or enter coordinates and time zone manually.';
      }catch(e){field.querySelector('.hint').textContent=e.message;}
    });
  });
  function request(field){
    const unknown=control(field,'unknown').checked;
    const times=core.localInstants(value(field,'date'),unknown?'12:00':value(field,'time'),value(field,'zone'));
    occurrences(field);
    if(!times.length)throw Error('That local time does not exist because the clocks change. Choose another time.');
    const chosen=times.length===1?times[0]:Number(control(field,'occurrence').value);
    if(!times.includes(chosen))throw Error('This local time occurs twice. Choose its first or second occurrence.');
    const year=new Date(chosen).getUTCFullYear();if(year<1900||year>2099)throw Error('The UTC instant is outside the 1900–2099 source coverage.');
    const latitude=Number(value(field,'latitude')),longitude=Number(value(field,'longitude'));
    if(!value(field,'latitude')||!value(field,'longitude')||!Number.isFinite(latitude)||!Number.isFinite(longitude)||latitude < -90||latitude >90||longitude < -180||longitude >180)throw Error('Enter valid birth-place coordinates.');
    return {calculator:'natal',instant_utc:new Date(chosen).toISOString(),timezone:value(field,'zone'),unknown_time:unknown,latitude,longitude,elevation_m:0};
  }
  function calculate(request,index){
    return new Promise((resolve,reject)=>{
      if(!worker){
        worker=new Worker(new URL('js/ephemera-worker.js',base));
        const activeWorker=worker;
        worker.onmessage=event=>{
          if(worker!==activeWorker||!pending)return;
          const message=event.data;
          if(message.type==='progress'){
            status.textContent=`Calculating ${pending.label}: ${message.message}`;
            if(Number.isFinite(message.completed))bar.value=pending.index*11+message.completed;
          }else if(message.type==='result'){const p=pending;pending=null;p.resolve(message.data);}
          else if(message.type==='error'){const p=pending;pending=null;p.reject(Error(message.message));}
        };
        worker.onerror=()=>{if(worker!==activeWorker)return;if(pending){const p=pending;pending=null;p.reject(Error('The calculation engine stopped. Please retry.'));}worker?.terminate();worker=null;};
      }
      pending={resolve,reject,index,label:value(fields[index],'label')||`person ${index+1}`};worker.postMessage(request);
    });
  }
  function setBusy(on){busy=on;submit.disabled=on;cancel.hidden=!on;progress.hidden=!on;
    fields.forEach(field=>{field.disabled=on;});
  }
  function svg(report,enabled){
    const people=report.people, rotation=people[0].houses?.[0]??0;
    const xy=(degree,radius)=>{const a=(180+degree-rotation)*Math.PI/180;return [radius*Math.cos(a),radius*Math.sin(a)];};
    const layouts=[];let baseRadius=250;
    for(const person of people){
      const slots=[];
      for(const row of person.bodies){let radius=baseRadius,x,y;
        for(let lane=0;lane<12;lane++){radius=baseRadius+lane*42;[x,y]=xy(row.longitude,radius);if(slots.every(s=>Math.abs(s.x-x)>=37||Math.abs(s.y-y)>=37))break;}
        slots.push({...row,x,y,radius});
      }
      layouts.push(slots);baseRadius=Math.max(...slots.map(s=>s.radius))+95;
    }
    const rim=baseRadius-45,edge=rim+90,colors=['#a9dcff','#ffd09b'];
    let out=`<svg xmlns="http://www.w3.org/2000/svg" viewBox="${-edge} ${-edge} ${edge*2} ${edge*2}" role="img" aria-labelledby="syn-wheel-title syn-wheel-desc"><title id="syn-wheel-title">Synastry bi-wheel</title><desc id="syn-wheel-desc">${escape(people[0].label)} inside in blue; ${escape(people[1].label)} outside in amber. Symbols retain exact longitudes. Cross-chart lines are projected to the inner circle.</desc><circle r="${rim+35}" fill="#22344d" stroke="#b6c6d9"/>`;
    for(let d=0;d<360;d++){
      const [x,y]=xy(d,rim),[u,v]=xy(d,rim-(d%30===0?16:d%5===0?8:3));out+=`<path d="M${x},${y}L${u},${v}" stroke="#b0bfd0" stroke-width="${d%30===0?1.3:.6}"/>`;
      if(d%30===0){const [a,b]=xy(d+15,rim+20);out+=`<text x="${a}" y="${b}" fill="#ffe0a1" font-size="22" text-anchor="middle" dominant-baseline="central">${signs[d/30]}</text>`;}
    }
    if(people[0].houses)people[0].houses.forEach((cusp,i)=>{const [x,y]=xy(cusp,213),[u,v]=xy(cusp,236),[a,b]=xy(cusp+3,225);out+=`<path d="M${x},${y}L${u},${v}" stroke="#b8c8dc"/><text x="${a}" y="${b}" fill="#ffffff" font-size="12">${i+1}</text>`;});
    for(const match of report.aspects){if(!enabled.has(match.aspect)||match.aspect==='conjunction')continue;
      const a=people[0].bodies.find(p=>p.body===match.first_body),b=people[1].bodies.find(p=>p.body===match.second_body);
      const [x,y]=xy(a.longitude,212),[u,v]=xy(b.longitude,212),color=['trine','sextile'].includes(match.aspect)?'#75b9f4':'#ef7e83';
      out+=`<path d="M${x},${y}L${u},${v}" fill="none" stroke="${color}" opacity=".85" stroke-width="1.7" ${match.aspect==='sextile'?'stroke-dasharray="4 3"':''}/>`;
    }
    layouts.forEach((rows,i)=>{out+=`<circle r="${Math.min(...rows.map(s=>s.radius))-23}" fill="none" stroke="${colors[i]}" opacity=".85"/>`;
      rows.forEach(row=>{out+=`<text x="${row.x}" y="${row.y}" fill="${colors[i]}" text-anchor="middle" dominant-baseline="central" font-size="${row.body==='ceres'?13:22}" font-family="DejaVu Sans,Segoe UI Symbol,Apple Symbols,sans-serif">${symbols[row.body]}</text>`;const [a,b]=xy(row.longitude,row.radius-18);out+=`<text x="${a}" y="${b}" fill="${colors[i]}" text-anchor="middle" dominant-baseline="central" font-size="12">${Math.floor(row.longitude%30)}°</text>`;});
    });
    return out+'</svg>';
  }
  function render(report){
    const enabled=new Set(core.aspects.map(a=>a[0])), labels=report.people.map(p=>p.label);
    results.innerHTML=`<h2>Your comparison</h2><p><strong class="person-one">${escape(labels[0])} · inner blue</strong><br><strong class="person-two">${escape(labels[1])} · outer amber</strong></p><p>${report.people.map(p=>`${escape(p.label)}: ${escape(p.instant_utc)} · ${escape(p.timezone)}${p.unknown_time?' · noon snapshot, time unknown':''}`).join('<br>')}</p><p>${report.people[0].houses?'Inner wheel aligned to Person 1’s Ascendant; house numbers refer to Person 1.':'No known-time inner chart: no houses or angles; Aries begins at the left.'}</p><div class="filters" aria-label="Show aspects">${core.aspects.map(([name,symbol])=>`<label><input type="checkbox" data-aspect="${name}" checked>${symbol} ${title(name)}</label>`).join('')}</div><figure class="wheel"></figure><p class="hint">Blue: trine and dashed sextile. Red: square and opposition. Conjunctions are listed without a line. Ce = Ceres. Symbols preserve exact longitude; crowded symbols use additional radial lanes.</p><h3 class="aspect-count"></h3><div class="table-scroll"><table><thead><tr><th>${escape(labels[0])}</th><th>Aspect</th><th>${escape(labels[1])}</th><th>Orb</th><th>Time uncertainty</th></tr></thead><tbody class="aspect-rows"></tbody></table></div><details><summary>Planet positions</summary><div class="table-scroll"><table><thead><tr><th>Person</th><th>Body</th><th>Position</th></tr></thead><tbody>${report.people.flatMap(p=>p.bodies.map(row=>`<tr><td>${escape(p.label)}</td><td>${title(row.body)}</td><td>${position(row.longitude)}</td></tr>`)).join('')}</tbody></table></div></details><details><summary>House overlays (${report.house_overlays.length})</summary><p class="hint">Overlays are calculated only into a chart with known time. Positions from an unknown-time chart are approximate.</p><div class="table-scroll"><table><thead><tr><th>Planet owner</th><th>Body</th><th>House owner</th><th>House</th><th>Position uncertain</th></tr></thead><tbody>${report.house_overlays.map(o=>`<tr><td>${escape(labels[o.planet_person-1])}</td><td>${title(o.body)}</td><td>${escape(labels[o.house_person-1])}</td><td>${o.house}</td><td>${o.birth_time_uncertain?'Yes':'No'}</td></tr>`).join('')}</tbody></table></div></details><p class="hint">${report.people.some(p=>p.unknown_time)?'Unknown birth time can change positions and aspects, especially those involving the Moon. Moon-related rows are flagged; a whole-day uncertainty interval has not been calculated.':''}</p><a class="download" download="nativitas-synastry.json">Download comparison JSON</a>`;
    function redraw(){
      results.querySelector('.wheel').innerHTML=svg(report,enabled);
      const rows=report.aspects.filter(a=>enabled.has(a.aspect)).sort((a,b)=>a.orb-b.orb);
      results.querySelector('.aspect-count').textContent=`Cross-chart aspects (${rows.length} shown of ${report.aspects.length})`;
      results.querySelector('.aspect-rows').innerHTML=rows.map(a=>`<tr><td>${title(a.first_body)}</td><td>${a.symbol} ${title(a.aspect)}</td><td>${title(a.second_body)}</td><td>${a.orb.toFixed(2)}°</td><td>${a.moon_time_uncertain?'Moon uncertain':a.birth_time_uncertain?'Approximate snapshot':'Known times'}</td></tr>`).join('');
    }
    results.querySelectorAll('[data-aspect]').forEach(box=>box.addEventListener('change',()=>{if(box.checked)enabled.add(box.dataset.aspect);else enabled.delete(box.dataset.aspect);redraw();}));redraw();
    if(downloadURL)URL.revokeObjectURL(downloadURL);downloadURL=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));results.querySelector('.download').href=downloadURL;
  }
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(busy)return;
    let requests;
    try{requests=fields.map(request);}catch(e){status.textContent=e.message;return;}
    const current=++generation,labels=fields.map((field,i)=>value(field,'label')||`Person ${i+1}`);
    setBusy(true);bar.value=0;results.replaceChildren();status.textContent='Loading the astronomy engine…';
    try{
      const a=await calculate(requests[0],0);if(current!==generation)return;bar.value=11;
      const b=await calculate(requests[1],1);if(current!==generation)return;bar.value=22;
      const comparison=core.compare(a,b,labels);render(comparison);status.textContent=`Complete: ${comparison.compared_pairs} cross-chart planet pairs compared.`;
    }catch(e){if(current===generation)status.textContent=e.message;}
    finally{if(current===generation)setBusy(false);}
  });
  cancel.addEventListener('click',()=>{
    generation++;worker?.terminate();worker=null;if(pending){const p=pending;pending=null;p.reject(Error('Calculation cancelled.'));}
    setBusy(false);status.textContent='Calculation cancelled. You can change the details and try again.';
  });
  window.NativitasSynastryView={svg};
})();
