/* Nativitas synastry geometry. No interpretive scoring or natal-text reuse. */
(function (root) {
  'use strict';
  const bodies = ['sun','moon','mercury','venus','mars','ceres','jupiter','saturn','uranus','neptune','pluto'];
  // Half the existing natal orbs, following the Astrodienst chart convention.
  // https://www.astro.com/faq/fq_fh_partner_e.htm
  const aspects = [['conjunction','☌',0,5],['sextile','⚹',60,3],['square','□',90,5],['trine','△',120,5],['opposition','☍',180,5]];
  function angle(x) {
    if (typeof x !== 'number' || !Number.isFinite(x)) throw Error('A finite longitude is required.');
    return ((x % 360) + 360) % 360;
  }
  function normalize(report, input, label) {
    const unknown = report.unknown_time ?? true;
    if (typeof unknown !== 'boolean') throw Error('Birth-time uncertainty must be specified as true or false.');
    const seen = new Set();
    const rows = (report.bodies || []).map(row => {
      if (!bodies.includes(row.body) || seen.has(row.body)) throw Error('Unknown or repeated body.');
      seen.add(row.body);
      return {body:row.body, longitude:angle(row.longitude)};
    });
    if (!rows.length) throw Error('A chart has no calculated positions.');
    let houses = null;
    if (!unknown && report.houses != null) {
      if (!Array.isArray(report.houses) || report.houses.length !== 12) throw Error('Twelve house cusps are required.');
      houses = report.houses.map(angle);
      const widths = houses.map((x,i) => angle(houses[(i+1)%12]-x));
      if (Math.min(...widths) <= 0 || Math.abs(widths.reduce((a,b)=>a+b,0)-360)>1e-7) throw Error('Invalid house-cusp order.');
    }
    return {input_id:input,label,unknown_time:unknown,bodies:rows,houses,
      instant_utc:report.instant_utc,timezone:report.timezone,observer:report.observer};
  }
  function houseFor(longitude, cusps) {
    const x = angle(longitude);
    for (let i=0;i<12;i++) if (angle(x-cusps[i]) < angle(cusps[(i+1)%12]-cusps[i])) return i+1;
    throw Error('Could not assign house.');
  }
  function compare(a,b,labels=['First person','Second person']) {
    const people = [normalize(a,'first',labels[0]),normalize(b,'second',labels[1])];
    if (people[0].unknown_time && !people[1].unknown_time) people.reverse();
    const matches = [], overlays = [];
    for (const first of people[0].bodies) for (const second of people[1].bodies) {
      const delta = angle(first.longitude-second.longitude), separation = Math.min(delta,360-delta);
      for (const [name,symbol,target,limit] of aspects) {
        const orb = Math.abs(separation-target);
        if (orb <= limit+1e-10) {
          matches.push({first_body:first.body,second_body:second.body,aspect:name,symbol,separation,orb,
            moon_time_uncertain:(first.body==='moon' && people[0].unknown_time)||(second.body==='moon' && people[1].unknown_time),
            birth_time_uncertain:people.some(p=>p.unknown_time)});
          break;
        }
      }
    }
    for (const [owner,host] of [[0,1],[1,0]]) if (people[host].houses) for (const row of people[owner].bodies) {
      overlays.push({planet_person:owner+1,house_person:host+1,body:row.body,
        house:houseFor(row.longitude,people[host].houses),birth_time_uncertain:people[owner].unknown_time});
    }
    return {schema_version:1,calculator:'synastry',people,compared_pairs:people[0].bodies.length*people[1].bodies.length,
      orbs:Object.fromEntries(aspects.map(([name,, ,orb])=>[name,orb])),aspects:matches,house_overlays:overlays};
  }
  function clockParts(instant,zone) {
    return Object.fromEntries(new Intl.DateTimeFormat('en-GB',{timeZone:zone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).formatToParts(instant).map(p=>[p.type,p.value]));
  }
  function localInstants(date,time,zone) {
    try {new Intl.DateTimeFormat('en',{timeZone:zone});} catch {throw Error('Choose a valid time zone.');}
    if (!/^\d{4}-\d{2}-\d{2}$/.test(date)||!/^\d{2}:\d{2}$/.test(time)) throw Error('Choose a valid date and local time.');
    const wall = Date.parse(`${date}T${time}:00Z`);
    if (!Number.isFinite(wall)||new Date(wall).toISOString().slice(0,16)!==`${date}T${time}`) throw Error('Choose a valid date and local time.');
    if (date<'1900-01-01'||date>'2099-12-31') throw Error('Choose a date from 1900 through 2099.');
    const offsets = new Set();
    for(let h=-36;h<=36;h+=6){
      const t=wall+h*3600000,p=clockParts(t,zone);
      offsets.add(Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`)-t);
    }
    return [...offsets].map(offset=>wall-offset).filter(t=>{
      const p=clockParts(t,zone);
      return `${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}`===`${date}T${time}`;
    }).sort((a,b)=>a-b);
  }
  const api = {bodies,aspects,angle,compare,houseFor,clockParts,localInstants};
  if(typeof module==='object' && module.exports) module.exports=api;
  else root.NativitasSynastry=api;
})(typeof globalThis!=='undefined'?globalThis:this);
