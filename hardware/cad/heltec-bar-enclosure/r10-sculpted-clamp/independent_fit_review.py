"""Independent R10 fit and protected-interface audit; transient BReps only."""
import adsk.core, adsk.fusion, json

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert 'R10' in a.activeDocument.name
 t=adsk.fusion.TemporaryBRepManager.get();B=adsk.fusion.BooleanTypes
 def body(name):return next(o.bRepBodies.item(0) for o in r.occurrences if o.component.name==name)
 def diff(u,v):
  q=t.copy(u);assert t.booleanOperation(q,t.copy(v),B.DifferenceBooleanType)
  return q.volume*1000 if q.isValid else 0
 def overlap(u,v):
  q=t.copy(u);assert t.booleanOperation(q,t.copy(v),B.IntersectionBooleanType)
  return q.volume*1000 if q.isValid else 0
 def clip(u,v):
  q=t.copy(u);assert t.booleanOperation(q,t.copy(v),B.IntersectionBooleanType);return q
 def box(lo,hi):return t.createBox(adsk.core.OrientedBoundingBox3D.create(adsk.core.Point3D.create(*[(x+y)/20 for x,y in zip(lo,hi)]),adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),*[(y-x)/10 for x,y in zip(lo,hi)]))
 def cylinder(rad):return t.createCylinderOrCone(adsk.core.Point3D.create(0,-10,-1.7),rad/10,adsk.core.Point3D.create(0,10,-1.7),rad/10)
 def compare(u,v,region):
  un=clip(u,region);vn=clip(v,t.copy(region));return {'added_mm3':diff(un,vn),'removed_mm3':diff(vn,un)}
 case=body('R10 Sculpted upper clamp and owner case');old=body('R09 Case with connected clamp ears')
 cap=body('R10 Sculpted lower clamp');oldcap=body('R09 Owner lower collar')
 lid=body('R10 Preserved recessed lid');oldlid=body('R09 Recessed lid')
 outside=case.pointContainment(adsk.core.Point3D.create(100,100,100))
 def inside(b,p):return b.pointContainment(adsk.core.Point3D.create(*[x/10 for x in p]))!=outside
 report={'document':a.activeDocument.name,'timeline_count':d.timeline.count,'scope':'Transient copies only; protected interfaces are compared separately from authorized fastener/outer styling changes','lid_difference_mm3':[diff(lid,oldlid),diff(oldlid,lid)],'protected_regions':{},'parts':{},'web_columns':[],'head_pockets':[],'M4_axis_clearance':[]}
 report['protected_regions']['upper_enclosure_above_z0p01']=compare(case,old,box([-100,-100,.01],[100,100,100]))
 for name,b,before in [('case',case,old),('lower',cap,oldcap)]:
  report['protected_regions'][name+'_tube_contact_band']=compare(b,before,cylinder(13.0))
 for name,b,before,z in [('upper_split',case,old,-16.25),('lower_split',cap,oldcap,-17.75)]:
  report['protected_regions'][name]=compare(b,before,box([-100,-100,z-.01],[100,100,z+.01]))
 for n,b in [('case',case),('lid',lid),('lower_clamp',cap)]:
  bb=b.preciseBoundingBox
  report['parts'][n]={'solid':b.isSolid,'lumps':b.lumps.count,'bad_coedges':[e.coEdges.count for e in b.edges if e.coEdges.count!=2],'volume_cm3':b.volume,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]}
 for x in [-16,16]:
  for y in [-10,0,10]:
   missing=[z for z in [-16+i*.5 for i in range(37)] if not inside(case,[x,y,z])]
   report['web_columns'].append({'xy_mm':[x,y],'all_material':not missing,'missing_z_mm':missing})
 for x in [-26,26]:
  report['M4_axis_clearance'].append({'x_mm':x,'blocked_z_mm':[z for z in [-33.5+i*.5 for i in range(68)] if inside(case,[x,0,z]) or inside(cap,[x,0,z])]})
  report['head_pockets'].append({'axis_xy_mm':[x,0],'head_envelope_radial_clear':not inside(case,[x+3.5,0,-2.5]),'counterbore_r4p05_clear':not inside(case,[x+4.05,0,-2.5]),'counterbore_r4p15_wall':inside(case,[x+4.15,0,-2.5]),'seat_above_empty':not inside(case,[x+3.0,0,-4.49]),'seat_below_solid':inside(case,[x+3.0,0,-4.51]),'shaft_r2p24_clear':not inside(case,[x+2.24,0,-8]),'shaft_r2p26_wall':inside(case,[x+2.26,0,-8])})
 tube=cylinder(12.6365)
 report['nominal_tube_fit']={n:{'overlap_mm3':overlap(tube,b),'clearance_mm':a.measureManager.measureMinimumDistance(tube,b).value*10} for n,b in [('case',case),('lower_clamp',cap)]}
 report['split']={'overlap_mm3':overlap(case,cap),'gap_mm':a.measureManager.measureMinimumDistance(case,cap).value*10}
 above=clip(case,box([-100,-100,.01],[100,100,100]));tools=[b for o in r.occurrences if o.component.name=='REF R07 12mm driver access above case datum' for b in o.bRepBodies]
 report['above_ear_tool_clearance_mm']=[min(a.measureManager.measureMinimumDistance(b,p).value*10 for p in [above,lid]) for b in tools]
 report['hardware_reference_bounds']=[]
 for o in r.occurrences:
  if o.component.name.startswith('REF R10 '):
   for b in o.bRepBodies:
    bb=b.preciseBoundingBox
    report['hardware_reference_bounds'].append({'component':o.component.name,'body':b.name,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]],'print_overlap_mm3':sum(overlap(b,p) for p in [case,lid,cap])})
 print(json.dumps(report))
