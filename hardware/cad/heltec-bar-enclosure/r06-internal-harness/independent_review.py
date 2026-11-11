import adsk.core, adsk.fusion, json
def run(_context: str):
 a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec Internal Harness R06'
 d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 es=adsk.core.ObjectCollection.create();seen=set();counts={}
 for o in r.allOccurrences:
  path=o.fullPathName
  for b in o.bRepBodies:
   include=path.startswith(('R06 ','REF R06 ','REF GPS accessory','REF OLED protective'))
   if path.startswith('REF Heltec') and b.isVisible:
    bb=b.preciseBoundingBox;lo=bb.minPoint;hi=bb.maxPoint
    include=('+Board:1+' in path or '+P3:' in path or (hi.x>=-.675 and lo.x<=.675 and hi.y>=-4.4 and lo.y<=-1.7 and hi.z>=.35 and lo.z<=1.48))
   if include and b.entityToken not in seen:
    seen.add(b.entityToken);es.add(b)
    group='printed' if path.startswith('R06 ') else 'routing_reference' if path.startswith('REF R06 ') else 'hardware_or_cover'
    counts[group]=counts.get(group,0)+1
 ip=d.createInterferenceInput(es);ip.areCoincidentFacesIncluded=False;rs=d.analyzeInterference(ip);hits=[]
 def name(b):return b.parentComponent.name+'/'+b.name
 for i in range(rs.count):
  q=rs.item(i);an=q.entityOne.parentComponent.name;bn=q.entityTwo.parentComponent.name
  if not(an.startswith(('R06 ','REF R06 ','REF OLED')) or bn.startswith(('R06 ','REF R06 ','REF OLED'))):continue
  if an.startswith('REF R06 ') and bn.startswith('REF R06 '):continue
  v=q.interferenceBody.volume*1000
  if v>1e-7:
   bb=q.interferenceBody.preciseBoundingBox
   hits.append({'a':name(q.entityOne),'b':name(q.entityTwo),'volume_mm3':v,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
 prints={o.component.name:o.bRepBodies.item(0) for o in r.occurrences if o.component.name.startswith('R06 ')}
 case=prints['R06 Case with internal GPS socket'];outside=case.pointContainment(adsk.core.Point3D.create(100,100,100))
 low=-4.375;high=-4.5
 assert case.pointContainment(adsk.core.Point3D.create(0,low,1.38))==outside
 assert case.pointContainment(adsk.core.Point3D.create(0,high,1.38))!=outside
 for i in range(35):
  mid=(low+high)/2
  if case.pointContainment(adsk.core.Point3D.create(0,mid,1.38))==outside:low=mid
  else:high=mid
 gap=(-3.9752710246011276-(low+high)/2)*10
 refs=[(o.component.name,o.bRepBodies.item(0)) for o in r.occurrences if o.component.name.startswith('REF R06 ')]
 clearance={name:min(a.measureManager.measureMinimumDistance(body,p).value*10 for p in prints.values()) for name,body in refs}
 print(json.dumps({'document':a.activeDocument.name,'timeline_count':d.timeline.count,'selected':counts,'remaining_intersections':hits,'bare_gps_socket_to_rear_inner_wall_mm':gap,'route_reference_to_print_minimum_mm':clearance,'print_solids':{k:{'solid':b.isSolid,'lumps':b.lumps.count} for k,b in prints.items()}}))
