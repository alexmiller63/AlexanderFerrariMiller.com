#!/usr/bin/env python3
"""Audit Star Almanack fixed-object identity before permanent IDs are assigned."""
from __future__ import annotations
import csv,json,math,re
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'Star-Almanack-Repo';OUT=SRC/'generated'/'fixed-object-identity-audit.json';REVIEW_OUT=SRC/'generated'/'fixed-object-contradiction-review.json'
CATALOG_RE=re.compile(r'^(NGC|IC)\s*0*(\d+)$',re.I);HIP_RE=re.compile(r'^HIP\s*0*(\d+)$',re.I);SH2_RE=re.compile(r'^Sh\s*2\s*[- ]\s*0*(\d+)$',re.I);VARIABLE_STAR_RE=re.compile(r'^([A-Z]{1,2}\d+)\s+([A-Za-z]{3})$')
CROSS_SOURCE_NAMESPACES={'ngc','ic','hip','bayer','sh2','variable_star'};STABLE_SOURCE_NAMESPACES={'messier','caldwell','finest_ngc','special','component','asterism_member_label'}
TYPE_FAMILIES={'Gal':'galaxy','ScG':'galaxy','SbG':'galaxy','dE0G':'galaxy','E6G':'galaxy','IG':'galaxy','SG':'galaxy','EG':'galaxy','LG':'galaxy','BG':'galaxy','BN':'emission_nebula','EN':'emission_nebula','E/RN':'emission_nebula','DN':'dark_nebula','PN':'planetary_nebula','OC':'open_cluster','GC':'globular_cluster','SN':'supernova_remnant','SNR':'supernova_remnant','DS':'double_star','MW':'milky_way','AS':'asterism'}
def norm_catalog(v):
 if v is None:return None
 s=str(v).strip()
 if not s or s.lower()=='null':return None
 m=CATALOG_RE.match(s)
 if m:return f'{m.group(1).upper()} {int(m.group(2))}'
 if s.isdigit():return f'NGC {int(s)}'
 return s
def catalog_identifier(v):
 cat=norm_catalog(v)
 if not cat:return None
 m=CATALOG_RE.match(cat)
 if m:return(m.group(1).lower(),str(int(m.group(2))))
 m=HIP_RE.match(cat)
 if m:return('hip',str(int(m.group(1))))
 m=SH2_RE.match(cat)
 if m:return('sh2',str(int(m.group(1))))
 m=VARIABLE_STAR_RE.match(cat)
 if m:return('variable_star',f'{m.group(1)} {m.group(2)}')
 return('catalog_label',cat)
def type_family(v):return TYPE_FAMILIES.get(v,v) if v else None
def read_csv(p):
 if not p.exists():return []
 with p.open(newline='',encoding='utf-8') as f:return list(csv.DictReader(f))
def schemas():return {'messier':['id','ngc','name','type','con','ra_h','dec_deg','mag','size_arcmin','best','iso'],'bayer':['bayer','con','name','ra_h','dec_deg','mag','best','iso'],'special':['id','name','catalog','con','ra_h','dec_deg','mag','best','iso','note'],'component':['bayer','con','component','name','ra_h','dec_deg','mag']}
def parse_fixed_simple_yaml(p):
 ss=schemas();result={k:[] for k in ss};current=None;inside=True
 for raw in p.read_text(encoding='utf-8').splitlines():
  if raw and not raw.startswith(' ') and raw.rstrip().endswith(':'):
   key=raw.strip()[:-1];inside=key=='schema';current=None if inside else(key if key in ss else None);continue
  if inside or current is None:continue
  s=raw.strip()
  if s.startswith('- [') and s.endswith(']'):
   vals=next(csv.reader([s[3:-1]],skipinitialspace=True));result[current].append([None if v.strip().lower()=='null' else v.strip() for v in vals])
 return result
def row_dict(section,values):
 names=schemas()[section];return {names[i]:values[i] if i<len(values) else None for i in range(len(names))}
def add_candidate(cs,source,key,ids,name=None,con=None,ra_h=None,dec_deg=None,obj_type=None,notes=None):
 clean=[];seen=set()
 for ns,val in ids:
  if val is None:continue
  v=str(val).strip()
  if not v or v.lower()=='null' or(ns,v)in seen:continue
  seen.add((ns,v));clean.append({'namespace':ns,'value':v})
 cs.append({'candidate_id':len(cs)+1,'source':source,'source_key':key,'identifiers':clean,'name':name or None,'constellation':con or None,'ra_h':ra_h or None,'dec_deg':dec_deg or None,'object_type':obj_type or None,'object_type_family':type_family(obj_type),'notes':notes or None})
def angular_sep_deg(a,b):
 try:r1=math.radians(float(a['ra_h'])*15);d1=math.radians(float(a['dec_deg']));r2=math.radians(float(b['ra_h'])*15);d2=math.radians(float(b['dec_deg']))
 except(TypeError,ValueError):return None
 x=max(-1,min(1,math.sin(d1)*math.sin(d2)+math.cos(d1)*math.cos(d2)*math.cos(r1-r2)));return math.degrees(math.acos(x))
def reconcile(cs):
 parent={c['candidate_id']:c['candidate_id'] for c in cs}
 def find(x):
  while parent[x]!=x:parent[x]=parent[parent[x]];x=parent[x]
  return x
 def union(a,b):
  a,b=find(a),find(b)
  if a!=b:parent[max(a,b)]=min(a,b)
 by=defaultdict(list)
 for c in cs:
  for i in c['identifiers']:
   if i['namespace']in CROSS_SOURCE_NAMESPACES:by[(i['namespace'],i['value'])].append(c['candidate_id'])
 for ids in by.values():
  for x in ids[1:]:union(ids[0],x)
 grouped=defaultdict(list)
 for c in cs:grouped[find(c['candidate_id'])].append(c['candidate_id'])
 cmap={c['candidate_id']:c for c in cs};groups=[]
 for n,ids in enumerate(sorted(grouped.values(),key=min),1):
  idset=set(ids);evidence=[]
  for(ns,v),members in sorted(by.items()):
   shared=sorted(idset.intersection(members))
   if len(shared)>1:evidence.append({'namespace':ns,'value':v,'candidate_ids':shared})
  contradictions=[];max_sep=0.0
  if len(ids)>1:
   rows=[cmap[i]for i in ids];cons=sorted({r['constellation']for r in rows if r['constellation']});rawtypes=sorted({r['object_type']for r in rows if r['object_type']});families=sorted({r['object_type_family']for r in rows if r['object_type_family']})
   if len(cons)>1:contradictions.append({'kind':'constellation','values':cons,'severity':'boundary_review'})
   if len(families)>1:contradictions.append({'kind':'object_type_family','values':families,'raw_values':rawtypes,'severity':'review'})
   for x in range(len(rows)):
    for y in range(x+1,len(rows)):
     sep=angular_sep_deg(rows[x],rows[y]);max_sep=max(max_sep,sep or 0.0)
   if max_sep>1.0:contradictions.append({'kind':'coordinates','max_separation_deg':round(max_sep,6),'severity':'review'})
  status='singleton'if len(ids)==1 else('contradiction_review'if contradictions else'validated_exact_identifier')
  groups.append({'provisional_group_id':n,'candidate_ids':sorted(ids),'candidate_count':len(ids),'merge_evidence':evidence,'max_coordinate_separation_deg':round(max_sep,6)if len(ids)>1 else None,'contradictions':contradictions,'review_status':status})
 return groups,by
def main():
 cs=[];fixed=parse_fixed_simple_yaml(SRC/'fixed-objects.yaml')
 for section,rows in fixed.items():
  for n,vals in enumerate(rows,1):
   r=row_dict(section,vals);ids=[];key=f'{section}:{n}'
   if section=='messier':ids=[('messier',r['id'])];ident=catalog_identifier(r['ngc']);ids+=([ident]if ident else[]);key=str(r['id'])
   elif section=='bayer':ids=[('bayer',f"{r['bayer']} {r['con']}")];key=f"{r['bayer']} {r['con']}"
   elif section=='special':ids=[('special',r['id'])];ident=catalog_identifier(r['catalog']);ids+=([ident]if ident else[]);key=str(r['id'])
   elif section=='component':ids=[('bayer',f"{r['bayer']} {r['con']}"),('component',r['component'])];key=f"{r['bayer']} {r['con']}:{r['component']}"
   add_candidate(cs,f'fixed-objects.yaml:{section}',key,ids,r.get('name'),r.get('con'),r.get('ra_h'),r.get('dec_deg'),r.get('type'),r.get('note'))
 for r in read_csv(SRC/'caldwell-catalog.csv'):
  ids=[('caldwell',r.get('caldwell'))];ident=catalog_identifier(r.get('catalog'));ids+=([ident]if ident else[]);add_candidate(cs,'caldwell-catalog.csv',r.get('caldwell',''),ids,r.get('name'),r.get('con'),r.get('ra_h'),r.get('dec_deg'),r.get('type'))
 for r in read_csv(SRC/'finest-ngc-catalog.csv'):
  ids=[('finest_ngc',r.get('finest_ngc'))];ident=catalog_identifier(r.get('catalog'));ids+=([ident]if ident else[]);add_candidate(cs,'finest-ngc-catalog.csv',r.get('finest_ngc',''),ids,r.get('name'),r.get('con'),r.get('ra_h'),r.get('dec_deg'),r.get('type'))
 for n,r in enumerate(read_csv(SRC/'asterism-member-coordinates.csv'),1):
  ids=[];hip=HIP_RE.match((r.get('coordinate_source_id')or'').strip());ids+=([('hip',str(int(hip.group(1))))]if hip else[]);ids.append(('asterism_member_label',r.get('member')));add_candidate(cs,'asterism-member-coordinates.csv',f'row:{n}',ids,r.get('resolved_object'),None,r.get('ra_h'),r.get('dec_deg'),'star',f"asterism={r.get('asterism','')}")
 groups,by=reconcile(cs);overlaps=[{'namespace':ns,'value':v,'candidate_ids':ids}for(ns,v),ids in sorted(by.items())if len(ids)>1];explicit={'finest_ngc_caldwell':read_csv(SRC/'finest-ngc-caldwell-overlap.csv'),'asterism_catalog':read_csv(SRC/'asterism-catalog-overlap.csv')};counts=Counter(c['source']for c in cs);icounts=Counter(i['namespace']for c in cs for i in c['identifiers']);no_cross=[c['candidate_id']for c in cs if not any(i['namespace']in CROSS_SOURCE_NAMESPACES for i in c['identifiers'])];no_any=[c['candidate_id']for c in cs if not c['identifiers']];merged=[g for g in groups if g['candidate_count']>1];review=[g for g in merged if g['contradictions']];validated=[g for g in merged if not g['contradictions']]
 result={'schema_version':7,'purpose':'pre-migration physical fixed-object identity audit; no permanent IDs assigned','canonical_source':'Star-Almanack-Repo/fixed-objects.yaml','candidate_count':len(cs),'provisional_reconciliation_group_count':len(groups),'provisional_merged_group_count':len(merged),'provisional_singleton_group_count':len(groups)-len(merged),'validated_exact_identifier_group_count':len(validated),'contradiction_review_group_count':len(review),'source_counts':dict(sorted(counts.items())),'identifier_counts':dict(sorted(icounts.items())),'cross_source_identifier_namespaces':sorted(CROSS_SOURCE_NAMESPACES),'stable_source_identifier_namespaces':sorted(STABLE_SOURCE_NAMESPACES),'object_type_families':TYPE_FAMILIES,'cross_source_identifier_overlap_count':len(overlaps),'cross_source_identifier_overlaps':overlaps,'candidates_without_cross_source_identifier':no_cross,'candidates_without_any_identifier':no_any,'explicit_overlap_counts':{k:len(v)for k,v in explicit.items()},'warnings':[],'provisional_reconciliation_groups':groups,'candidates':cs,'explicit_overlap_records':explicit}
 cmap={c['candidate_id']:c for c in cs};review_result={'schema_version':3,'purpose':'focused review after normalization of compatible object-type vocabularies','group_count':len(review),'groups':[dict(g,candidates=[cmap[i]for i in g['candidate_ids']])for g in review]}
 OUT.parent.mkdir(parents=True,exist_ok=True);OUT.write_text(json.dumps(result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8');REVIEW_OUT.write_text(json.dumps(review_result,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
 print(f'Wrote {OUT.relative_to(ROOT)}');print(f'Wrote {REVIEW_OUT.relative_to(ROOT)}');print(f'Candidates: {len(cs)}');print(f'Provisional groups: {len(groups)}; merged: {len(merged)}; validated: {len(validated)}; review: {len(review)}');print('No fixed_object_id values were assigned.')
if __name__=='__main__':main()
