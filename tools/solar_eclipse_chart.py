"""Original numerical solar study charts from stored Star Almanack results."""
from datetime import datetime
import html
import json
import math
from eclipse_path_display import central_path_events


def instant(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00'))


def chart(event, shapes):
    """Render stored geometry and times without introducing new predictions."""
    has_path=bool(event.get('central_path',{}).get('points'))
    height=1800 if has_path else 1480
    out=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1400 {height}" role="img" aria-labelledby="solar-title solar-desc">',
         '<title id="solar-title">'+html.escape(event['date_utc']+' '+event['type']+' solar eclipse study chart')+'</title>',
         '<desc id="solar-desc">Numbered shadow-plane cross-section, global UTC contacts and timeline, geometry ledger, and available calculated central-path coordinates.</desc>',
         f'<rect width="1400" height="{height}" fill="#fbf8ef"/>',
         '<style>text{font-family:DejaVu Sans,sans-serif;fill:#203747}.mono{font-family:DejaVu Sans Mono,monospace;font-variant-numeric:tabular-nums}</style>']
    def text(x,y,value,size=18,extra=''):
        out.append(f'<text x="{x}" y="{y}" font-size="{size}" {extra}>{html.escape(str(value))}</text>')
    def line(x1,y1,x2,y2,extra='stroke="#b8b3a4"'):
        out.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" {extra}/>')
    text(50,45,'STAR ALMANACK  /  ECLIPSE STUDIES',17,'letter-spacing="3"')
    text(50,96,event['type'].upper()+' SOLAR ECLIPSE',40,'font-weight="bold"')
    text(50,135,instant(event['greatest_utc']).strftime('%d %B %Y')+'  ·  all clocks UTC',24)
    text(1350,45,event['id'],16,'text-anchor="end" class="mono"')
    line(50,158,1350,158)
    text(50,195,'01  /  SHADOW-PLANE GEOMETRY AT GREATEST ECLIPSE',19,'font-weight="bold"')
    # The catalog displacement is unsigned: orient x toward Earth, with no
    # celestial compass or implied motion. All circles retain a common scale.
    low=min(x-r for _,x,r,_ in shapes)
    high=max(x+r for _,x,r,_ in shapes)
    radius=max(r for _,_,r,_ in shapes)
    scale=min(650/(high-low),500/(2*radius))
    middle=(low+high)/2
    def xy(x,y=0): return 470+(x-middle)*scale,500-y*scale
    xmin,xmax=middle-350/scale,middle+350/scale
    ymax=270/scale
    for label,x,r,fill in shapes:
        sx,sy=xy(x)
        out.append(f'<circle data-label="{label}" cx="{sx:.4f}" cy="{sy}" r="{r*scale:.4f}" fill="{fill}" fill-opacity=".8" stroke="#536579"/>')
    step=5000 if max(xmax-xmin,2*ymax)<50000 else 10000
    out.append('<g id="shadow-coordinate-grid">')
    for v in range(math.ceil(xmin/step)*step,math.floor(xmax/step)*step+1,step):
        x,_=xy(v)
        line(x,230,x,770,'stroke="#526c7b" stroke-opacity=".3" stroke-dasharray="3 5"')
        text(x,794,f'{v:+,}' if v else '0',15,'text-anchor="middle" class="mono"')
    for v in range(math.ceil(-ymax/step)*step,math.floor(ymax/step)*step+1,step):
        _,y=xy(0,v)
        line(120,y,820,y,'stroke="#526c7b" stroke-opacity=".3" stroke-dasharray="3 5"')
        text(112,y+5,f'{v:+,}' if v else '0',15,'text-anchor="end" class="mono"')
    out.append('</g>')
    for i,(label,x,r,fill) in enumerate(shapes):
        px,py=xy(x)
        line(px-5,py,px+5,py,'stroke="#203747" stroke-width="2"')
        line(px,py-5,px,py+5,'stroke="#203747" stroke-width="2"')
        text(135,835+i*25,f'{label}: center x = {x:,.1f} km; radius = {r:,.1f} km',17)
    text(470,817,'Offset (km) · origin: shadow axis · +x toward Earth’s center',16,'text-anchor="middle"')
    text(50,936,'Both axes use kilometres at the same scale. Transverse orientation is arbitrary; no celestial compass is implied.',17)
    text(50,961,'A cross-section through Earth’s center at closest axis approach, not the shadow footprint on Earth’s surface.',17)
    text(930,230,'02  /  GLOBAL CONTACTS',19,'font-weight="bold"')
    contacts=event.get('contacts_utc',{})
    if isinstance(contacts,str): contacts=json.loads(contacts)
    times=sorted([(k,v) for k,v in {**contacts,'MAX':event['greatest_utc']}.items() if v],key=lambda kv:kv[1])
    labels={'global_begin':'Global beginning','global_end':'Global ending','axis_entry':'Axis enters Earth','axis_exit':'Axis leaves Earth','MAX':'Greatest eclipse'}
    for i,(key,value) in enumerate(times):
        y=268+i*59
        text(930,y,labels.get(key,key),17)
        text(930,y+24,instant(value).strftime('%Y-%m-%d  %H:%M:%S'),17,'class="mono"')
    text(930,590,'03  /  GEOMETRY',19,'font-weight="bold"')
    fields=[('axis_distance_km','Axis distance'),('central_margin_km','Axis minus Earth radius'),
            ('penumbra_margin_km','Penumbral margin'),('core_radius_km','Signed core radius'),
            ('surface_core_radius_min_km','Surface core minimum'),('surface_core_radius_max_km','Surface core maximum')]
    for i,(key,label) in enumerate((k,l) for k,l in fields if k in event):
        y=624+i*44
        text(930,y,label,17)
        text(930,y+21,f'{event[key]:+,.3f} km',18,'class="mono"')
    text(930,912,'Core: + umbra / − antumbra',16)
    line(50,980,1350,980)
    text(50,1014,'04  /  GLOBAL UTC TIMELINE',19,'font-weight="bold"')
    start,end=instant(times[0][1]),instant(times[-1][1])
    duration=(end-start).total_seconds()
    line(130,1095,1260,1095,'stroke="#526c7b" stroke-width="2"')
    for i,(key,value) in enumerate(times):
        x=130+1130*(instant(value)-start).total_seconds()/max(duration,1)
        y=1052 if i%2==0 else 1133
        line(x,1090,x,1100,'stroke="#203747" stroke-width="2"')
        line(x,1095,x,y+6 if y<1095 else y-19,'stroke="#526c7b"')
        text(x,y,labels.get(key,key),15,'text-anchor="middle"')
        text(x,y+19,instant(value).strftime('%H:%M:%S'),17,'text-anchor="middle" class="mono"')
    sec=round(duration)
    text(50,1194,f'Global event window: {sec//3600:02d}h {sec%3600//60:02d}m {sec%60:02d}s. These are global limits, not local contacts or duration.',17)
    line(50,1215,1350,1215)
    text(50,1250,'05  /  CALCULATED CENTRAL PATH',19,'font-weight="bold"')
    points=event.get('central_path',{}).get('points',[])
    if points:
        # Coordinate plot uses no borrowed basemap. Break at the dateline.
        def geo(p): return 120+(p['longitude_deg']+180)*3.2,1300+(90-p['latitude_deg'])*1.6
        out.append('<g id="timed-central-path">')
        out.append('<rect x="120" y="1300" width="1152" height="288" fill="#edf3f5" stroke="#708090"/>')
        for lon in range(-180,181,60):
            x=120+(lon+180)*3.2
            line(x,1300,x,1588,'stroke="#b8c7cd"')
            text(x,1609,f'{lon}°',14,'text-anchor="middle"')
        for lat in range(-90,91,30):
            y=1300+(90-lat)*1.6
            line(120,y,1272,y,'stroke="#b8c7cd"')
            text(112,y+5,f'{lat}°',14,'text-anchor="end"')
        for a,b in zip(points,points[1:]):
            if abs(a['longitude_deg']-b['longitude_deg'])>180: continue
            x1,y1=geo(a);x2,y2=geo(b)
            color='#195ea8' if b['phase']=='total' else '#b35400'
            line(x1,y1,x2,y2,f'stroke="{color}" stroke-width="3"')
        for n,milestone in enumerate(central_path_events(event)):
            p=milestone['point'];x,y=geo(p);tx=230+n*465;ty=1660
            line(x,y,tx,ty+4 if ty<1300 else ty-34,'stroke="#526c7b" stroke-width=".8"')
            out.append(f'<circle data-utc="{html.escape(milestone["utc"])}" cx="{x}" cy="{y}" r="3" fill="#203747"><title>Nearest stored position: {html.escape(p["utc"])}</title></circle>')
            text(tx,ty-19,milestone['label'],16,'text-anchor="middle"')
            text(tx,ty,instant(milestone['utc']).strftime('%H:%M:%S UTC'),16,'text-anchor="middle" class="mono"')
        out.append('</g>')
        text(50,1725,'Event times are calculated; markers use nearest stored positions. Path limits are central-axis contacts.',16)
        text(50,1702,f'{len(points)} stored coordinates. Longitude east +; latitude geocentric. Blue: total. Orange: annular. Center line only; no path width.',16)
    else:
        text(50,1310,'No calculated central-axis surface path for this event.',23)
        text(50,1350,'The diagram above quantifies the offset and shadow overlap; global times appear in the ledger and timeline.',18)
        text(50,1390,'For a partial eclipse, the central shadow axis misses Earth. A wider partial-visibility map is not yet calculated.',18)
    text(50,height-40,'Original chart and calculations: Star Almanack. Positions: JPL DE440s. Spherical Earth; instantaneous geometry; provisional model.',16)
    text(50,height-15,'Surface core extrema describe the sampled surface path; the cross-section core radius describes a different plane.',16)
    return ''.join(out)+'</svg>'
