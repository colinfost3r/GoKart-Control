import adsk.core, adsk.fusion, json, pathlib
def run(_context: str):
 a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec Rectangular Owner Layout R05'
 d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 prints={o.component.name:o.bRepBodies.item(0) for o in r.occurrences if o.component.name.startswith('R05 ')}
 case=prints['R05 Case and upper collar'];lid=prints['R05 OLED lid with integral antenna mount'];tray=prints['R05 GPS slide tray with end latch']
 gps=[b for o in r.allOccurrences if o.fullPathName.startswith('REF GPS accessory') for b in o.bRepBodies]
 ant=next(o for o in r.occurrences if o.component.name.startswith('REF 2inch'))
 surf=next(f.geometry for b in ant.bRepBodies for f in b.faces if f.geometry.surfaceType==adsk.core.SurfaceTypes.CylinderSurfaceType)
 n=surf.axis;n.normalize();u=n.crossProduct(adsk.core.Vector3D.create(0,0,1));u.normalize();p=surf.origin
 def axispoint(t,rad=0):return adsk.core.Point3D.create(p.x+n.x*t/10+u.x*rad/10,p.y+n.y*t/10+u.y*rad/10,p.z+n.z*t/10+u.z*rad/10)
 outside=lid.pointContainment(adsk.core.Point3D.create(100,100,100))
 sma={'hole_center_clear':lid.pointContainment(axispoint(-1))==outside,'seat_ring_present':lid.pointContainment(axispoint(-1,4))!=outside,'rear_access_clear':lid.pointContainment(axispoint(-3,6))==outside}
 oled=all(lid.pointContainment(adsk.core.Point3D.create(0,-.55345,z/10))==outside for z in [14,16,18,20,24,27.5,30,31])
 bm=adsk.fusion.TemporaryBRepManager.get();released=bm.copy(tray)
 # Analytical release model removes only the tooth below the tray floor. The flexible beam is checked separately.
 ob=adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(0,-3.25,.995),adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),.56,.5,.111)
 tooth=bm.createBox(ob);assert bm.booleanOperation(released,tooth,adsk.fusion.BooleanTypes.DifferenceBooleanType)
 def intersection_volume(b1,b2):
  t=bm.copy(b1);ok=bm.booleanOperation(t,b2,adsk.fusion.BooleanTypes.IntersectionBooleanType)
  assert ok
  return t.volume*1000 if t.isValid else 0
 steps=[]
 for travel in [0,1,2,3,5,8,12,16,20,24,30]:
  tr=adsk.core.Matrix3D.create();tr.translation=adsk.core.Vector3D.create(0,-travel/10,0)
  objs=[released]+gps;hit=0
  for body in objs:
   moved=bm.copy(body);assert bm.transform(moved,tr)
   hit+=intersection_volume(moved,case)+intersection_volume(moved,lid)
  steps.append({'rearward_travel_mm':travel,'intersection_mm3':hit})
 owner=json.load(open(pathlib.Path(__file__).resolve().parent/'input/owner-layout.json'))
 originals={c['name']:c['transform'] for c in owner['components']}
 checks={}
 for o in r.occurrences:
  if o.component.name in ['REF Heltec V4.3.1 official STEP','REF GPS accessory alternate revision','REF 2inch antenna envelope diameter7mm assumed']:
   checks[o.component.name]=max(abs(x-y) for x,y in zip(o.transform2.asArray(),originals[o.component.name]))
 print(json.dumps({'document':a.activeDocument.name,'timeline_count':d.timeline.count,'print_solids':{k:{'solid':b.isSolid,'lumps':b.lumps.count} for k,b in prints.items()},'owner_transform_max_deltas':checks,'sma_point_checks':sma,'oled_center_sightline_clear':oled,'released_tray_and_gps_sweep':steps,'sweep_limit':'Discrete sampled travel; rigid geometry with below-floor latch tooth analytically removed; does not validate printed latch flex or cable movement.'}))
