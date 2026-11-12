import adsk.core, adsk.fusion, json
def run(_context: str):
 a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec FDM Supports R07'
 d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent;t=adsk.fusion.TemporaryBRepManager.get()
 parts={o.component.name:o.bRepBodies.item(0) for o in r.occurrences if o.component.name.startswith('R07 ')}
 case=parts['R07 Case with floor-backed GPS supports'];lid=parts['R07 OLED and antenna lid'];cap=parts['R07 Outboard lower collar']
 region=t.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(0,0,5.005),adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),20,20,9.99))
 shell=t.copy(case);assert t.booleanOperation(shell,region,adsk.fusion.BooleanTypes.IntersectionBooleanType)
 rows=[]
 for o in r.occurrences:
  if o.component.name.startswith('REF R07 12mm'):
   for b in o.bRepBodies:
    bb=b.preciseBoundingBox
    rows.append({'axis_x_mm':(bb.minPoint.x+bb.maxPoint.x)*5,'diameter_mm':12,'shell_above_z0p1_clearance_mm':a.measureManager.measureMinimumDistance(b,shell).value*10,'lid_clearance_mm':a.measureManager.measureMinimumDistance(b,lid).value*10})
 outside={name:b.pointContainment(adsk.core.Point3D.create(100,100,100)) for name,b in parts.items()}
 axis=[]
 for x in [-26,26]:
  zs=[-33,-31,-28,-24,-20,-16,-12,-8,-4,-1]
  bad=[z for z in zs if any(b.pointContainment(adsk.core.Point3D.create(x/10,0,z/10))!=outside[name] for name,b in parts.items())]
  axis.append({'x_mm':x,'z_samples_mm':zs,'clear':not bad,'blocked_z_mm':bad})
 old=[]
 for x in [-18.5,18.5]:
  old.append({'x_mm':x,'upper_old_hole_filled':case.pointContainment(adsk.core.Point3D.create(x/10,0,-1))!=outside['R07 Case with floor-backed GPS supports'],'lower_old_hole_filled':cap.pointContainment(adsk.core.Point3D.create(x/10,0,-2.5))!=outside['R07 Outboard lower collar']})
 print(json.dumps({'tool_access':rows,'new_clamp_axis_passages':axis,'old_axes':old,'note':'Transient clipped copy isolates case above Z0.1 mm from its intended collar datum; native model is not modified.'}))
