"""R06: extend the archived owner-edited R05 shell and replace the exterior tray
with a side-supported internal GPS socket. All hardware positions stay unchanged.
"""
import adsk.core, adsk.fusion, importlib.util, pathlib
O=adsk.fusion.FeatureOperations

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec Internal Harness R06'
 assert not any(o.component.name.startswith('R06 ') for o in r.occurrences)
 sp=importlib.util.spec_from_file_location('h',str(pathlib.Path(__file__).resolve().parent.parent/'r03-parallel/build_model.py'));h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
 originals=list(r.occurrences);poses={o.component.name:list(o.transform2.asArray()) for o in originals}
 def copy(name,oldname):
  c=h.component(r,name);o=next(o for o in r.occurrences if o.component==c);src=next(o for o in originals if o.component.name==oldname)
  src.bRepBodies.item(0).copyToComponent(o);return c
 main=copy('R06 Case with internal GPS socket','R05 Case and upper collar')
 lid=copy('R06 OLED and antenna lid','R05 OLED lid with integral antenna mount')
 cap=copy('R06 Lower collar','R05 Lower collar')
 # Retain owner face-healing edits by deriving the actual current bodies, not R05 source.
 h.box(main,'Extend and close rectangular rear wall',0,-43.5,0,36,5,27.5,O.JoinFeatureOperation)
 h.box(main,'Clear old tray and provide open underside',0,-32.5,2.5,32,23,25.1,O.CutFeatureOperation)
 h.box(main,'Close obsolete underside latch access',0,-32.9,0,7.2,4.2,2.5,O.JoinFeatureOperation)
 # Rear wall now innerY=-44, outerY=-46:4.2473mm from actual bare GPS connector.
 h.box(lid,'Extend continuous rectangular lid',0,-43.5,27.5,36,5,2.5,O.JoinFeatureOperation)
 for c,zlen in [(main,27.5),(lid,2.5)]:
  es=[]
  for e in c.bRepBodies.item(0).edges:
   p=e.startVertex.geometry;q=e.endVertex.geometry
   if abs(p.x-q.x)<1e-6 and abs(p.y-q.y)<1e-6 and abs(p.y+4.6)<1e-6 and abs(abs(p.x)-1.8)<1e-6 and abs(abs(p.z-q.z)-zlen/10)<1e-6:es.append(e)
  if es:
   fi=c.features.filletFeatures.createInput();fi.edgeSetInputs.addConstantRadiusEdgeSet(h.coll(es),h.mm(2),False);c.features.filletFeatures.add(fi).name='R06 rear outer corners'
 # Restore low Heltec end stops removed with the old tray structure.
 for x in [-8,8]:h.box(main,'Heltec rear end stop',x,-26.6,2.5,3,.9,6.8,O.JoinFeatureOperation)
 # Sidewall-supported ledges contact clear GPS PCB edge strips, leaving its underside open.
 for x in [-11.375,11.375]:
  for y in [-32.55,-26.55]:h.box(main,'GPS PCB side support',x,y,14.1,9.25,2.5,1.5,O.JoinFeatureOperation)
 for x in [-8.65,8.65]:
  for y in [-32.55,-26.55]:h.box(main,'GPS lateral guide',x,y,15.6,.8,2.5,3,O.JoinFeatureOperation)
 # Fixed rear capture lips sit over exposed PCB corners, behind the ceramic patch.
 for x in [-11.6,11.6]:h.box(main,'GPS rear capture side arm',x,-40.7,14.4,8.8,.8,1.2,O.JoinFeatureOperation)
 for x in [-7.2,7.2]:
  h.box(main,'GPS rear end locator',x,-40.7,15.6,1.5,.5,2.7,O.JoinFeatureOperation)
  h.box(main,'GPS rear PCB capture lip',x,-40.15,17.5,1.5,1.1,.8,O.JoinFeatureOperation)
 # Front stop arms are side-supported above the protective cover.
 for x in [-11.6,11.6]:h.box(main,'GPS front side arm',x,-21.05,14.4,8.8,.9,1.2,O.JoinFeatureOperation)
 for x in [-7.2,7.2]:h.box(main,'GPS front end locator',x,-21.05,15.6,1.5,1,1.6,O.JoinFeatureOperation)
 # One front end clip, released toward+Y with lid removed; its nose clears the ceramic.
 h.box(main,'GPS single end clip beam',11.6,-20.95,17.5,8.8,.8,2,O.JoinFeatureOperation)
 # Ramp profile inYZ atX6.55, extruded1.3mm alongX.
 pi=main.constructionPlanes.createInput();pi.setByOffset(main.yZConstructionPlane,h.mm(6.55));p=main.constructionPlanes.add(pi);s=main.sketches.add(p)
 coords=[(-22.15,17.5),(-21.35,17.5),(-21.35,19.5),(-22.15,18.3)];pts=[s.modelToSketchSpace(h.pt(6.55,y,z)) for y,z in coords]
 for j in range(4):s.sketchCurves.sketchLines.addByTwoPoints(pts[j],pts[(j+1)%4])
 h.extrude(main,s,1.3,O.JoinFeatureOperation,'GPS end clip insertion ramp');p.isLightBulbOn=False
 # Retain positive Heltec cover capture while clearing the new front GPS stops/clip.
 for x in [-7.2,7.2]:h.box(lid,'Internal clearance for GPS end clip',x,-21.9,14.25,4,3.3,5.5,O.CutFeatureOperation)
 # The P3 mating approach needs a wider opening than the8mm wire corridor.
 h.box(main,'P3 mating plug approach between rear pads',0,-20.15,2.5,13.5,5.5,4.4413,O.CutFeatureOperation)
 # Internal cable keeper, open at the top centre, holds wires below the GPS.
 for x in [-5.5,5.5]:h.box(main,'Internal wire keeper upright',x,-30,2.5,1,2.5,4.8,O.JoinFeatureOperation)
 for x in [-3.5,3.5]:h.box(main,'Internal wire keeper lip',x,-30,6.5,4,2.5,.8,O.JoinFeatureOperation)
 # Nonprinted route envelopes: dimensions are allowances, not measured cable/plug sizes.
 wire=h.component(r,'REF R06 internal wire route 8x2mm assumed')
 h.box(wire,'GPS connector rear turn envelope',0,-41.251355,12.8,8,2.99729,2)
 h.box(wire,'Downward wire envelope',0,-42.75,4.1,8,2,10.7,O.JoinFeatureOperation)
 h.box(wire,'Under PCB wire approach',0,-32.545,4.1,8,20.41,2,O.JoinFeatureOperation)
 gp=h.component(r,'REF R06 GPS mating plug12x3x2p5 assumed');h.box(gp,'GPS plug allowance',0,-41.252710,12.55,12,3,2.5)
 hp=h.component(r,'REF R06 Heltec P3 mating plug12x5x2p7 assumed');h.box(hp,'P3 plug allowance',0,-19.843898,3.8,12,5,2.7)
 # Restore the rear lid pillar removed by the broad socket clearing cut.
 h.circles(main,'Restore rear M3 lid pillar',[(14,-29)],2.5,7,25,O.JoinFeatureOperation)
 h.circles(main,'Rear M3 working clearance only',[(14,-29)],21,3.4,9.5)
 h.hexholes(main,'Rear M3 captive nut seat',[(14,-29)],27.5,5.8,-2.7)
 # Preserve the previous geometry hidden in the derived document.
 for o in originals:
  if o.component.name.startswith('R05 '):o.isLightBulbOn=False
 for o in r.occurrences:
  if o.component.name.startswith('REF R06 '):o.isLightBulbOn=False
 d.computeAll();d.activateRootComponent();a.activeViewport.fit()
 for o in originals:assert max(abs(x-y) for x,y in zip(o.transform2.asArray(),poses[o.component.name]))<1e-8,'Changed owner pose '+o.component.name
 for c in [main,lid,cap]:print(c.name,c.bRepBodies.count,[b.lumps.count for b in c.bRepBodies])
 print('R06 complete;79x36rectangle, side-supported GPS, fully internal route, owner poses preserved.')
