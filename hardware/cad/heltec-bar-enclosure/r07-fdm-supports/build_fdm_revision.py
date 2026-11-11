"""GENERATED BASE ONLY: R07 floor-backed ribs/outboard bolts before owner manual edits.
The owner subsequently edited R07 directly in Fusion. The archived/final native file is
authoritative; this script does not reproduce those manual edits and must not replace them.
"""
import adsk.core, adsk.fusion, importlib.util, pathlib, math
O=adsk.fusion.FeatureOperations

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec FDM Supports R07'
 assert not any(o.component.name.startswith('R07 ') for o in r.occurrences)
 sp=importlib.util.spec_from_file_location('h',str(pathlib.Path(__file__).resolve().parent.parent/'r03-parallel/build_model.py'));h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
 original=list(r.occurrences);poses={o.component.name:list(o.transform2.asArray()) for o in original}
 def copy(name,source):
  c=h.component(r,name);dst=next(o for o in r.occurrences if o.component==c);src=next(o for o in original if o.component.name==source);src.bRepBodies.item(0).copyToComponent(dst);return c
 main=copy('R07 Case with floor-backed GPS supports','R06 Case with internal GPS socket')
 lid=copy('R07 OLED and antenna lid','R06 OLED and antenna lid')
 cap=copy('R07 Outboard lower collar','R06 Lower collar')
 # The rear socket is behind the PCB; these ribs run directly to the case floor.
 for x in [-11.6,11.6]:h.box(main,'Rear GPS capture floor rib',x,-40.9,2.5,8.8,1.6,11.9,O.JoinFeatureOperation)
 for x in [-11.375,11.375]:h.box(main,'Rear GPS ledge floor rib',x,-32.55,2.5,9.25,2.5,11.6,O.JoinFeatureOperation)
 # Forward ledges sit partly over the board. Back their feet behind its rear edge.
 for x in [-11.375,11.375]:h.box(main,'Forward GPS ledge floor rib behind PCB',x,-27.1,2.5,9.25,1.4,11.6,O.JoinFeatureOperation)
 def yz_prism(c,name,x,points,width):
  pi=c.constructionPlanes.createInput();pi.setByOffset(c.yZConstructionPlane,h.mm(x));pl=c.constructionPlanes.add(pi);s=c.sketches.add(pl);s.name=name+' profile'
  ps=[s.modelToSketchSpace(h.pt(x,y,z)) for y,z in points]
  for k in range(len(ps)):s.sketchCurves.sketchLines.addByTwoPoints(ps[k],ps[(k+1)%len(ps)])
  h.extrude(c,s,width,O.JoinFeatureOperation,name);pl.isLightBulbOn=False
 for x in [-16,6.75]:yz_prism(main,'45deg forward ledge transition',x,[(-26.4,13),(-26.4,14.1),(-25.3,14.1)],9.25)
 # Front end supports descend outside the Heltec PCB/cover, with45deg inner transitions.
 for x in [-14.7,14.7]:h.box(main,'Front socket floor column outside PCB',x,-21,2.5,2.6,2.4,11.9,O.JoinFeatureOperation)
 def xz_prism(c,name,y,points,length):
  normal=c.xZConstructionPlane.geometry.normal.y;pi=c.constructionPlanes.createInput();pi.setByOffset(c.xZConstructionPlane,h.mm(y/normal));pl=c.constructionPlanes.add(pi);s=c.sketches.add(pl);s.name=name+' profile'
  ps=[s.modelToSketchSpace(h.pt(x,y,z)) for x,z in points]
  for k in range(len(ps)):s.sketchCurves.sketchLines.addByTwoPoints(ps[k],ps[(k+1)%len(ps)])
  h.extrude(c,s,length/normal,O.JoinFeatureOperation,name);pl.isLightBulbOn=False
 for sign in [-1,1]:xz_prism(main,'45deg front socket transition',-22.2,[(sign*16,7.7),(sign*16,15.45),(sign*8.25,15.45)],1.65)
 # The flexible end clip remains free. Its root already joins the full-height sidewall.
 # Solid ear additions fill obsolete holes/nut channels and extend the collar to66mm wide.
 for c,z in [(main,-16.25),(cap,-34)]:
  for x in [-23.25,23.25]:h.box(c,'Solid outboard clamp ear',x,0,z,19.5,24,16.25,O.JoinFeatureOperation)
  es=[]
  for e in c.bRepBodies.item(0).edges:
   p=e.startVertex.geometry;q=e.endVertex.geometry
   if abs(p.x-q.x)<1e-6 and abs(p.y-q.y)<1e-6 and abs(abs(p.x)-3.3)<1e-6 and abs(abs(p.y)-1.2)<1e-6 and abs(abs(p.z-q.z)-1.625)<1e-6:es.append(e)
  if es:
   fi=c.features.filletFeatures.createInput();fi.edgeSetInputs.addConstantRadiusEdgeSet(h.coll(es),h.mm(2.5),False);c.features.filletFeatures.add(fi).name='Rounded new clamp ear corners'
  h.circles(c,'Outboard M4 shafts at52mm pitch',[(-26,0),(26,0)],-36,4.5,37)
 h.circles(cap,'M4 socket head counterbores',[(-26,0),(26,0)],-34,8,2)
 # Hex flats parallel slot walls:7.3AF pocket,7.5mm wide insertion slot,3.4mm depth.
 s=h.sketch(main,-2.6,'Outboard M4 nut seats')
 for x in [-26,26]:h.polygon(s,x,0,7.3/math.sqrt(3),6,0)
 h.extrude(main,s,-3.4,O.CutFeatureOperation,'Outboard M4 captive nut pockets')
 for x in [-30,30]:h.box(main,'Outboard M4 nut insertion slot',x,0,-6,8,7.5,3.4,O.CutFeatureOperation)
 # Nonprinted nominal fastener/tool checks; no thread helices or assumed physical tolerances.
 bolts=h.component(r,'REF R07 M4x30 socket screws nominal')
 h.circles(bolts,'Nominal4mm shafts',[(-26,0),(26,0)],-32,4,30,O.NewBodyFeatureOperation)
 h.circles(bolts,'Nominal7mm socket heads',[(-26,0),(26,0)],-36,7,4,O.JoinFeatureOperation)
 nuts=h.component(r,'REF R07 M4 nuts7AFx3p2 nominal');s=h.sketch(nuts,-5.9,'Nominal M4 nut outlines')
 for x in [-26,26]:h.polygon(s,x,0,7/math.sqrt(3),6,0)
 h.extrude(nuts,s,3.2,O.NewBodyFeatureOperation,'Nominal M4 nuts');h.circles(nuts,'Nominal nut bore',[(-26,0),(26,0)],-6,4.2,3.5)
 tools=h.component(r,'REF R07 12mm driver access above case datum')
 h.circles(tools,'Straight tool clearance to case and lid',[(-26,0),(26,0)],0,12,85,O.NewBodyFeatureOperation)
 for o in original:
  if o.component.name.startswith('R06 '):o.isLightBulbOn=False
 for o in r.occurrences:
  if o.component.name.startswith('REF R07 '):o.isLightBulbOn=False
 d.computeAll();d.activateRootComponent();a.activeViewport.fit()
 for o in original:assert max(abs(x-y) for x,y in zip(o.transform2.asArray(),poses[o.component.name]))<1e-8,'Owner pose changed '+o.component.name
 for c in [main,lid,cap]:print(c.name,c.bRepBodies.count,[b.lumps.count for b in c.bRepBodies])
 print('R07 built:floor-backed ribs,52mm M4 pitch,66mm clamp width. Original tube and hardware poses retained.')
