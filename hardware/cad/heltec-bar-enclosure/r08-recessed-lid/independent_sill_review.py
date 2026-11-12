import adsk.core, adsk.fusion, json
def run(_context: str):
 a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec Recessed Lid R08'
 d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent;t=adsk.fusion.TemporaryBRepManager.get();B=adsk.fusion.BooleanTypes
 def body(name):return next(o.bRepBodies.item(0) for o in r.occurrences if o.component.name==name)
 def box(lo,hi):
  return t.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(*[(x+y)/20 for x,y in zip(lo,hi)]),adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),*[(y-x)/10 for x,y in zip(lo,hi)]))
 def clip(b,reg):
  q=t.copy(b);assert t.booleanOperation(q,reg,B.IntersectionBooleanType);return q
 def difference(u,v):
  q=t.copy(u);assert t.booleanOperation(q,v,B.DifferenceBooleanType);return q.volume*1000 if q.isValid else 0
 old=body('R07 Case with floor-backed GPS supports');case=body('R08 Owner base and recessed sill')
 oldcap=body('R07 Outboard lower collar');cap=body('R08 Owner lower collar')
 oldlid=body('R07 OLED and antenna lid');lid=body('R08 Stepped lid for number4 screws')
 base_reg=box([-100,-100,-100],[100,100,2.49]);ob=clip(old,base_reg);nb=clip(case,base_reg)
 base={'region_z_max_mm':2.49,'new_minus_owner_mm3':difference(nb,ob),'owner_minus_new_mm3':difference(ob,nb)}
 lower={'new_minus_owner_mm3':difference(cap,oldcap),'owner_minus_new_mm3':difference(oldcap,cap)}
 antreg=box([-100,-100,30.01],[100,100,100]);ol=clip(oldlid,antreg);nl=clip(lid,antreg)
 ant={'region_z_min_mm':30.01,'new_minus_owner_mm3':difference(nl,ol),'owner_minus_new_mm3':difference(ol,nl)}
 band=box([-100,-100,27.55],[100,100,28.4]);cb=clip(case,band);lb=clip(lid,band)
 gap=a.measureManager.measureMinimumDistance(cb,lb).value*10
 co=case.pointContainment(adsk.core.Point3D.create(100,100,100));lo=lid.pointContainment(adsk.core.Point3D.create(100,100,100))
 def inside(b,p,out):return b.pointContainment(adsk.core.Point3D.create(*[v/10 for v in p]))!=out
 bearings=[]
 for x,y in [(15.2,0),(-15.2,0),(0,-43.2),(0,30.2)]:
  bearings.append({'xy_mm':[x,y],'case_below':inside(case,[x,y,27.49],co),'lid_above':inside(lid,[x,y,27.51],lo)})
 pilots=[]
 for x,y in [(13,-29),(-13,28)]:
  pilots.append({'xy_mm':[x,y],'bottom_material':inside(case,[x,y,15.49],co),'bore_above_bottom_empty':not inside(case,[x,y,15.51],co),'tip_empty':not inside(case,[x,y,17.3],co),'lid_clearance_empty':not inside(lid,[x,y,28],lo),'pilot_side_wall_material':inside(case,[x+1.4,y,20],co)})
 print(json.dumps({'document':a.activeDocument.name,'timeline_count':d.timeline.count,'owner_extended_base_comparison':base,'owner_lower_collar_comparison':lower,'antenna_print_above_lid_comparison':ant,'locating_side_gap_min_mm':gap,'perimeter_bearing_samples':bearings,'pilot_samples':pilots,'tip_clearance_mm':1.8,'scope':'Temporary geometry only; no native geometry or visibility changed. Upper-left clamp ear remains missing as in owner input.'}))
