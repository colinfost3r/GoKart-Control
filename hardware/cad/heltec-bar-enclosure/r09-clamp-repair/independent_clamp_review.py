"""Independent transient-BRep audit of R09 repairs; native geometry unchanged."""
import adsk.core, adsk.fusion, json

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert 'R09' in a.activeDocument.name
 t=adsk.fusion.TemporaryBRepManager.get();B=adsk.fusion.BooleanTypes
 def body(name):return next(o.bRepBodies.item(0) for o in r.occurrences if o.component.name==name)
 def difference(u,v):
  q=t.copy(u);assert t.booleanOperation(q,t.copy(v),B.DifferenceBooleanType)
  return q.volume*1000 if q.isValid else 0
 def intersection(u,v):
  q=t.copy(u);assert t.booleanOperation(q,t.copy(v),B.IntersectionBooleanType)
  return q.volume*1000 if q.isValid else 0
 def box(lo,hi):return t.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(*[(x+y)/20 for x,y in zip(lo,hi)]),adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),*[(y-x)/10 for x,y in zip(lo,hi)]))
 old=body('R08 Owner base and recessed sill');case=body('R09 Case with connected clamp ears')
 lid=body('R09 Recessed lid');oldlid=body('R08 Stepped lid for number4 screws')
 cap=body('R09 Owner lower collar');oldcap=body('R08 Owner lower collar')
 outside=case.pointContainment(adsk.core.Point3D.create(100,100,100))
 def inside(b,p):return b.pointContainment(adsk.core.Point3D.create(*[x/10 for x in p]))!=outside
 report={'document':a.activeDocument.name,'timeline_count':d.timeline.count,'scope':'Temporary copies and Boolean operations; no native edits','owner_material_removed_mm3':difference(old,case),'added_repair_material_mm3':difference(case,old),'lid_differences_mm3':[difference(lid,oldlid),difference(oldlid,lid)],'lower_collar_differences_mm3':[difference(cap,oldcap),difference(oldcap,cap)],'topology':{},'web_columns':[],'clamp_bores':[]}
 for n,b in [('case',case),('lid',lid),('lower_collar',cap)]:
  bad=[{'coedges':e.coEdges.count,'faces':e.faces.count} for e in b.edges if e.coEdges.count!=2]
  report['topology'][n]={'solid':b.isSolid,'lumps':b.lumps.count,'bad_edges':bad,'volume_cm3':b.volume}
 for x in [-16,16]:
  for y in [-10,0,10]:
   missing=[z for z in [-16+i*.5 for i in range(37)] if not inside(case,[x,y,z])]
   report['web_columns'].append({'xy_mm':[x,y],'range_z_mm':[-16,2],'samples':37,'all_material':not missing,'missing_z_mm':missing})
 for x in [-26,26]:
  zvals=[-33+i*.5 for i in range(66)]
  conflicts=[z for z in zvals if inside(case,[x,0,z]) or inside(cap,[x,0,z])]
  report['clamp_bores'].append({'axis_xy_mm':[x,0],'axis_clear':not conflicts,'blocked_z_mm':conflicts})
 tube=t.createCylinderOrCone(adsk.core.Point3D.create(0,-10,-1.7),1.26365,adsk.core.Point3D.create(0,10,-1.7),1.26365)
 report['full_length_nominal_tube']={n:{'overlap_mm3':intersection(tube,b),'minimum_clearance_mm':a.measureManager.measureMinimumDistance(tube,b).value*10} for n,b in [('case',case),('lower_collar',cap)]}
 report['case_to_collar']={'overlap_mm3':intersection(case,cap),'minimum_gap_mm':a.measureManager.measureMinimumDistance(case,cap).value*10}
 tools=[b for o in r.occurrences if o.component.name=='REF R07 12mm driver access above case datum' for b in o.bRepBodies]
 report['driver_contact_at_ear_plane_mm']=[min(a.measureManager.measureMinimumDistance(b,p).value*10 for p in [case,lid]) for b in tools]
 above=t.copy(case);assert t.booleanOperation(above,box([-100,-100,.01],[100,100,100]),B.IntersectionBooleanType)
 report['driver_clearance_above_ear_mm']=[min(a.measureManager.measureMinimumDistance(b,p).value*10 for p in [above,lid]) for b in tools]
 report['driver_volume_intersection_mm3']=[sum(intersection(b,p) for p in [case,lid]) for b in tools]
 added=t.copy(case);assert t.booleanOperation(added,t.copy(old),B.DifferenceBooleanType)
 bb=added.preciseBoundingBox
 report['added_material_bounds_mm']=[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]
 upper=box([-100,-100,.01],[100,100,100]);newupper=t.copy(case);oldupper=t.copy(old)
 assert t.booleanOperation(newupper,upper,B.IntersectionBooleanType);assert t.booleanOperation(oldupper,t.copy(upper),B.IntersectionBooleanType)
 report['upper_case_differences_mm3']=[difference(newupper,oldupper),difference(oldupper,newupper)]
 print(json.dumps(report))
