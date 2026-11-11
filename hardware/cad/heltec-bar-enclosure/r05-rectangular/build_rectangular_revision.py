"""Build R05 in a fresh copy of the archived owner layout, preserving hardware poses.
Dimensions are mm. Original components are retained hidden; new R05 print parts use world coordinates.
"""
import adsk.core, adsk.fusion, importlib.util, pathlib, math
P=adsk.core.Point3D;V=adsk.core.ValueInput;O=adsk.fusion.FeatureOperations

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec Rectangular Owner Layout R05'
 assert not any(o.component.name.startswith('R05 ') for o in r.occurrences)
 sp=importlib.util.spec_from_file_location('helpers',str(pathlib.Path(__file__).resolve().parent.parent/'r03-parallel/build_model.py'));h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
 original=list(r.occurrences);poses={o.component.name:list(o.transform2.asArray()) for o in original}
 oldmain=next(o for o in original if o.component.name.startswith('C01'))
 main=h.component(r,'R05 Case and upper collar');maino=next(o for o in r.occurrences if o.component==main)
 oldmain.bRepBodies.item(0).copyToComponent(maino)
 h.box(main,'Retain proven upper collar only',0,0,0,200,200,100,O.CutFeatureOperation)
 h.box(main,'Continuous rectangular shell',0,-5.5,0,36,77,27.5,O.JoinFeatureOperation)
 es=[]
 for e in main.bRepBodies.item(0).edges:
  p=e.startVertex.geometry;q=e.endVertex.geometry
  if abs(p.x-q.x)<1e-6 and abs(p.y-q.y)<1e-6 and abs(abs(p.z-q.z)-2.75)<1e-6:es.append(e)
 fi=main.features.filletFeatures.createInput();fi.edgeSetInputs.addConstantRadiusEdgeSet(h.coll(es),h.mm(2),False);main.features.filletFeatures.add(fi).name='R05 shell outer corners'
 h.box(main,'Continuous electronics cavity',0,-5.5,2.5,32,73,26,O.CutFeatureOperation)
 # The original clamp nut insertion paths lie below the new floor and remain intact.
 lidxy=[(14,-29),(-14,29)]
 h.circles(main,'Two lid screw pillars',lidxy,2.5,7,25,O.JoinFeatureOperation)
 h.circles(main,'Two lid screw clearance holes',lidxy,2.5,3.4,28)
 h.hexholes(main,'Two M3 nut seats',lidxy,27.5,5.8,-2.7)
 h.circles(main,'Four PCB support pads',[(-y,x) for x in [-20.0345,8.9655] for y in [-7,7]],2.5,4.5,4.4413,O.JoinFeatureOperation)
 for y in [-26.6,26.6]:
  for x in [-8,8]:h.box(main,'PCB end stop',x,y,2.5,3,.9,6.8,O.JoinFeatureOperation)
 for x in [-13.4,13.4]:
  for y in [-8,15]:h.box(main,'PCB side stop',x,y,2.5,.8,5,6.8,O.JoinFeatureOperation)
 h.box(main,'USB C outside plug access',0,33,7,13,6,7.5,O.CutFeatureOperation)
 # Flush rear tray access. The enlarged interior is one continuous rectangle.
 h.box(main,'Flush GPS tray opening',0,-43.2,9.2,25,4,11.1,O.CutFeatureOperation)
 for x in [-9.6,9.6]:
  h.box(main,'GPS tray lower rail',x,-33,2.5,2,19,8,O.JoinFeatureOperation)
  h.box(main,'GPS tray guide upright',x,-33,10.5,2,19,5.5,O.JoinFeatureOperation)
 for x in [-13.2,13.2]:h.box(main,'Tray guide backed to shell',x,-33,10.5,5.6,19,6.8,O.JoinFeatureOperation)
 for x in [-12.3,12.3]:h.box(main,'Tray upper capture lip',x,-33,16,7.4,19,1.3,O.JoinFeatureOperation)
 # Relieve the guide uprights to a 20.8mm track, leaving 0.25mm per side for20.3tray.
 h.box(main,'Tray guide side clearance',0,-33,10.5,20.8,19.1,5.5,O.CutFeatureOperation)
 h.box(main,'Tray floor forward stop',0,-23.2,2.5,21,.6,9,O.JoinFeatureOperation)
 h.box(main,'Final latch catch clear of connector',0,-35.7,2.5,21,1.6,8,O.JoinFeatureOperation)
 h.box(main,'Final latch release access',0,-32.9,0,7,4,10.6,O.CutFeatureOperation)
 # Lid with a recessed/flared OLED sight opening.
 lid=h.component(r,'R05 OLED lid with integral antenna mount');lido=next(o for o in r.occurrences if o.component==lid)
 lb=h.box(lid,'Single rectangular lid',0,-5.5,27.5,36,77,2.5).bodies.item(0);h.vertical_fillet(lid,lb,2)
 h.circles(lid,'Two lid holes',lidxy,27.5,3.4,3)
 # Four stops bear only on the protective-frame ends, clear of the moved GPS.
 h.circles(lid,'Protective frame capture',[(x,y) for x in [-7,7] for y in [-20.0345,8.9655]],14.3,3,13.2,O.JoinFeatureOperation)
 def rectloft(name,z1,w1,l1,z2,w2,l2,op):
  s1=h.sketch(lid,z1,name+' lower');h.rectangle(s1,0,-5.5345,w1,l1)
  s2=h.sketch(lid,z2,name+' upper');h.rectangle(s2,0,-5.5345,w2,l2)
  i=lid.features.loftFeatures.createInput(op);i.loftSections.add(s1.profiles.item(0));i.loftSections.add(s2.profiles.item(0))
  if op==O.CutFeatureOperation:i.participantBodies=list(lid.bRepBodies)
  f=lid.features.loftFeatures.add(i);f.name=name;s1.isLightBulbOn=False;s2.isLightBulbOn=False
 rectloft('Recessed OLED surround',16.5,18.4,28,30,22.4,32,O.JoinFeatureOperation)
 rectloft('OLED clear sight aperture',16,14.4,25,30.5,18.4,29,O.CutFeatureOperation)
 # Preserve the owner's final antenna axis and exterior collar shape.
 owner_mount=next(o for o in original if o.component.name.strip()=='new ant mount');owner_mount.bRepBodies.item(0).copyToComponent(lido)
 antenna=next(o for o in original if o.component.name=='REF 2inch antenna envelope diameter7mm assumed')
 surf=next(f.geometry for b in antenna.bRepBodies for f in b.faces if f.geometry.surfaceType==adsk.core.SurfaceTypes.CylinderSurfaceType)
 origin=surf.origin;n=surf.axis;n.normalize();u=n.crossProduct(adsk.core.Vector3D.create(0,0,1));u.normalize();v=n.crossProduct(u);v.normalize()
 def point(dist,bu=0,bv=0):return P.create(origin.x+n.x*dist+u.x*bu+v.x*bv,origin.y+n.y*dist+u.y*bu+v.y*bv,origin.z+n.z*dist+u.z*bu+v.z*bv)
 sk=lid.sketches.add(lid.xYConstructionPlane);sk.name='Owner antenna datum preserved'
 ps=[sk.sketchPoints.add(point(0)),sk.sketchPoints.add(point(0,1)),sk.sketchPoints.add(point(0,0,1))]
 pi=lid.constructionPlanes.createInput();pi.setByThreePoints(*ps);face=lid.constructionPlanes.add(pi)
 pi=lid.constructionPlanes.createInput();pi.setByOffset(face,h.mm(-2));seat=lid.constructionPlanes.add(pi)
 # A tapered root joins the collar smoothly into the lid, with no case notch/web.
 s1=h.sketch(lid,28.5,'Antenna blended root lower');s1.sketchCurves.sketchEllipses.add(h.pt(9,22),h.pt(9,31),h.pt(17,22))
 s2=lid.sketches.add(seat);s2.name='Antenna blended root upper';s2.sketchCurves.sketchCircles.addByCenterRadius(s2.modelToSketchSpace(point(-.2)),.75)
 li=lid.features.loftFeatures.createInput(O.JoinFeatureOperation);li.loftSections.add(s1.profiles.item(0));li.loftSections.add(s2.profiles.item(0));lf=lid.features.loftFeatures.add(li);lf.name='Integral antenna tapered root'
 s1.isLightBulbOn=False;s2.isLightBulbOn=False
 if lid.bRepBodies.count>1:
  target=lid.bRepBodies.item(0);ci=lid.features.combineFeatures.createInput(target,h.coll([b for b in lid.bRepBodies if b!=target]));ci.operation=O.JoinFeatureOperation;ci.isKeepToolBodies=False;lid.features.combineFeatures.add(ci)
 s=lid.sketches.add(seat);s.sketchCurves.sketchCircles.addByCenterRadius(s.modelToSketchSpace(point(-.2)),.46);h.extrude(lid,s,2,O.JoinFeatureOperation,'Integral2mm SMA panel seat')
 s=lid.sketches.add(face);s.sketchCurves.sketchCircles.addByCenterRadius(s.modelToSketchSpace(point(0)),.33);h.extrude(lid,s,-2.1,O.CutFeatureOperation,'SMA6p6 panel hole')
 s=lid.sketches.add(seat);s.sketchCurves.sketchCircles.addByCenterRadius(s.modelToSketchSpace(point(-.2)),.66);h.extrude(lid,s,-24,O.CutFeatureOperation,'Open underside13p2mm connector access')
 sk.isLightBulbOn=False;face.isLightBulbOn=False;seat.isLightBulbOn=False
 # Lower collar copied exactly: M4x30, two screws, side-loaded nut seats retained.
 cap=h.component(r,'R05 Lower collar');capo=next(o for o in r.occurrences if o.component==cap)
 next(o for o in original if o.component.name.startswith('C02')).bRepBodies.item(0).copyToComponent(capo)
 tray=h.component(r,'R05 GPS slide tray with end latch')
 h.box(tray,'Tray floor',0,-33,10.5,20.3,19,1)
 for x in [-9.55,9.55]:h.box(tray,'Tray guide side',x,-33,11.5,1.2,19,4.1,O.JoinFeatureOperation)
 for x in [-6.5,6.5]:
  for y in [-33.3,-27]:h.box(tray,'PCB underside support pad',x,y,11.5,2,2,4.1,O.JoinFeatureOperation)
 h.box(tray,'Flush tray pull end',0,-43.2,9.5,24.6,1.4,10.5,O.JoinFeatureOperation)
 h.box(tray,'Rear harness notch',0,-43.2,11.5,14,2,5,O.CutFeatureOperation)
 for x in [-3.3,3.3]:h.box(tray,'Final latch tongue isolation',x,-29.2,10.3,.6,10,1.5,O.CutFeatureOperation)
 h.box(tray,'Final latch free end separation',0,-34.2,10.3,6.6,.6,1.5,O.CutFeatureOperation)
 h.box(tray,'Final latch beam thin section',0,-29.2,11.3,6,10,.3,O.CutFeatureOperation)
 pi=tray.constructionPlanes.createInput();pi.setByOffset(tray.yZConstructionPlane,h.mm(-2.75));side=tray.constructionPlanes.add(pi);ts=tray.sketches.add(side)
 vs=[(-34.2,10.5),(-34.2,9.4),(-33.1,9.4),(-31.6,10.5)];pts=[ts.modelToSketchSpace(h.pt(-2.75,y,z)) for y,z in vs]
 for j in range(4):ts.sketchCurves.sketchLines.addByTwoPoints(pts[j],pts[(j+1)%4])
 h.extrude(tray,ts,5.5,O.JoinFeatureOperation,'Final single end latch tooth');side.isLightBulbOn=False
 for x in [-9.6,9.6]:h.box(main,'PCB clearance below tray rail',x,-24.825,2.5,2.02,2.65,6.5,O.CutFeatureOperation)
 h.box(main,'PCB clearance below tray stop',0,-23.2,2.5,21.02,.62,6.5,O.CutFeatureOperation)
 h.box(lid,'Internal collar clearance beside shell wall',22.85,23,20,14.3,14,7.5,O.CutFeatureOperation)
 h.box(main,'IPEX and coax clearance in tray stop',0,-23.2,8.5,4,.8,3.1,O.CutFeatureOperation)
 h.circles(main,'Fill sealed lower M3 pillar cavity',[(14,-29)],2.5,3.6,8,O.JoinFeatureOperation)
 # Original geometry remains recoverable in the same document, hidden from final assembly.
 for o in original:
  if o.component.name.startswith(('C01','C02','C03','C04','REF GPS conservative')) or o.component.name.strip()=='new ant mount':o.isLightBulbOn=False
 for o in r.occurrences:
  if o.component.name.startswith('R05 '):o.isLightBulbOn=True
 d.computeAll();d.activateRootComponent();a.userInterface.activeSelections.clear();a.activeViewport.fit()
 for o in original:assert max(abs(x-y) for x,y in zip(o.transform2.asArray(),poses[o.component.name]))<1e-8,'Owner pose changed '+o.component.name
 for c in [main,lid,cap,tray]:print(c.name,c.bRepBodies.count,[b.lumps.count for b in c.bRepBodies])
 print('R05 rectangular revision complete. Exact owner poses preserved.')
