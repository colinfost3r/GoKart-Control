import adsk.core, adsk.fusion, json
def run(_context: str):
 a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec FDM Supports R07'
 d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 es=adsk.core.ObjectCollection.create();seen=set();counts={}
 for o in r.allOccurrences:
  path=o.fullPathName
  for b in o.bRepBodies:
   include=path.startswith(('R07 ','REF R06 ','REF R07 ','REF GPS accessory','REF OLED protective'))
   if path.startswith('REF Heltec') and not any(p.startswith(('JP4:','JP5:')) for p in path.split('+')):
    bb=b.preciseBoundingBox;lo=bb.minPoint;hi=bb.maxPoint
    include=('+Board:1+' in path or '+P3:' in path or (hi.y>=-4.4 and lo.y<=-1.7 and hi.z>=.25 and lo.z<=1.95))
   if include and b.entityToken not in seen:
    seen.add(b.entityToken);es.add(b)
    group='printed' if path.startswith('R07 ') else 'routing_or_fastener_reference' if path.startswith(('REF R06 ','REF R07 ')) else 'hardware_or_cover'
    counts[group]=counts.get(group,0)+1
 ip=d.createInterferenceInput(es);ip.areCoincidentFacesIncluded=False;rs=d.analyzeInterference(ip);hits=[];cover_hits=[]
 for i in range(rs.count):
  q=rs.item(i);an=q.entityOne.parentComponent.name;bn=q.entityTwo.parentComponent.name;v=q.interferenceBody.volume*1000
  if v<1e-7:continue
  relevant=an.startswith('R07 ') or bn.startswith('R07 ') or (an.startswith(('REF R06 ','REF R07 ')) != bn.startswith(('REF R06 ','REF R07 ')))
  cover_gps=(an.startswith('GPS-Module1') and bn.startswith('REF OLED')) or (bn.startswith('GPS-Module1') and an.startswith('REF OLED'))
  if not(relevant or cover_gps):continue
  bb=q.interferenceBody.preciseBoundingBox
  row={'a':an+'/'+q.entityOne.name,'b':bn+'/'+q.entityTwo.name,'volume_mm3':v,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]}
  if relevant:hits.append(row)
  else:cover_hits.append(row)
 prints={o.component.name:o.bRepBodies.item(0) for o in r.occurrences if o.component.name.startswith('R07 ')}
 case=prints['R07 Case with floor-backed GPS supports'];outside=case.pointContainment(adsk.core.Point3D.create(100,100,100))
 floor=[]
 for x,y,zt in [(sg*x,y,z) for sg in [-1,1] for x,y,z in [(11.6,-40.9,14.35),(11.375,-32.55,14.05),(11.375,-27.1,14.05),(14.7,-21,14.35)]]:
  bad=[]
  for i in range(51):
   z=2.55+(zt-2.55)*i/50
   if case.pointContainment(adsk.core.Point3D.create(x/10,y/10,z/10))==outside:bad.append(z)
  floor.append({'x_mm':x,'y_mm':y,'range_z_mm':[2.55,zt],'samples':51,'all_material':not bad,'missing_z_mm':bad})
 low=-4.375;high=-4.5
 for i in range(35):
  mid=(low+high)/2
  if case.pointContainment(adsk.core.Point3D.create(0,mid,1.38))==outside:low=mid
  else:high=mid
 gap=(-3.9752710246011276-(low+high)/2)*10
 refs=[(o.component.name,b) for o in r.occurrences if o.component.name.startswith('REF R06 ') for b in o.bRepBodies]
 clearance={name:min(a.measureManager.measureMinimumDistance(body,p).value*10 for p in prints.values()) for name,body in refs}
 print(json.dumps({'document':a.activeDocument.name,'timeline_count':d.timeline.count,'selected':counts,'remaining_intersections':hits,'inherited_cover_fit':cover_hits,'floor_support_samples':floor,'bare_gps_socket_to_rear_inner_wall_mm':gap,'route_reference_to_print_minimum_mm':clearance,'print_solids':{k:{'solid':b.isSolid,'lumps':b.lumps.count} for k,b in prints.items()}}))
