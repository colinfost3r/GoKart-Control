"""R08 lid-only revision derived from the exact owner-extended R07 archive.
Preserves the owner base and all history; never regenerate earlier revisions.
The supplied #4 screw definition is for plastic thread-forming screws, not generic sheet-metal screws.
"""
import adsk.core, adsk.fusion, pathlib, importlib.util, math, json


def run(_context: str):
    folder=pathlib.Path(__file__).resolve().parent
    a=adsk.core.Application.get()
    assert a.activeDocument.name=='GoKart Heltec FDM Supports R07'
    source=folder/'input/owner-extended-R07-timeline-677.f3d'
    doc=a.importManager.importToNewDocument(a.importManager.createFusionArchiveImportOptions(str(source)))
    assert doc
    doc.name='GoKart Heltec Recessed Lid R08'
    d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    sp=importlib.util.spec_from_file_location('r03helpers',str(folder.parent/'r03-parallel/build_model.py'))
    h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
    O=adsk.fusion.FeatureOperations
    for n,v,comment in [('r08_pilot','2.65 mm','Prototype pilot for chosen #4 plastic thread-forming screw; test actual print'),('r08_pilot_depth','12 mm','Blind depth below boss top'),('r08_lid_clear','3.4 mm','Lid through clearance for #4 screw')]:
        d.userParameters.add(n,h.mm(v),'mm',comment)
    copies={}
    for oldname,newname in [('R07 Case with floor-backed GPS supports','R08 Owner base and recessed sill'),('R07 OLED and antenna lid','R08 Stepped lid for number4 screws'),('R07 Outboard lower collar','R08 Owner lower collar')]:
        old=next(o for o in r.occurrences if o.component.name==oldname)
        new=r.occurrences.addNewComponent(adsk.core.Matrix3D.create());new.component.name=newname
        assert old.component.bRepBodies.count==1
        assert old.bRepBodies.item(0).copyToComponent(new)
        old.isLightBulbOn=False
        copies[newname]=new
    case=copies['R08 Owner base and recessed sill'].component
    lid=copies['R08 Stepped lid for number4 screws'].component
    initial_case_volume=case.bRepBodies.item(0).volume

    def rounded_outline(s,w,l,cy,rad):
        x0=-w/2;x1=w/2;y0=cy-l/2;y1=cy+l/2
        ls=s.sketchCurves.sketchLines;ar=s.sketchCurves.sketchArcs
        ls.addByTwoPoints(h.pt(x0+rad,y0),h.pt(x1-rad,y0))
        ar.addByCenterStartSweep(h.pt(x1-rad,y0+rad),h.pt(x1-rad,y0),math.pi/2)
        ls.addByTwoPoints(h.pt(x1,y0+rad),h.pt(x1,y1-rad))
        ar.addByCenterStartSweep(h.pt(x1-rad,y1-rad),h.pt(x1,y1-rad),math.pi/2)
        ls.addByTwoPoints(h.pt(x1-rad,y1),h.pt(x0+rad,y1))
        ar.addByCenterStartSweep(h.pt(x0+rad,y1-rad),h.pt(x0+rad,y1),math.pi/2)
        ls.addByTwoPoints(h.pt(x0,y1-rad),h.pt(x0,y0+rad))
        ar.addByCenterStartSweep(h.pt(x0+rad,y0+rad),h.pt(x0,y0+rad),math.pi/2)

    def ring(c,name,z,innerw,innerl,depth,op,outerw=36,outerl=79,rounded=True):
        s=h.sketch(c,z,name+' sketch')
        if rounded:rounded_outline(s,outerw,outerl,-6.5,2)
        else:s.sketchCurves.sketchLines.addTwoPointRectangle(h.pt(-outerw/2,-6.5-outerl/2),h.pt(outerw/2,-6.5+outerl/2))
        s.sketchCurves.sketchLines.addTwoPointRectangle(h.pt(-innerw/2,-6.5-innerl/2),h.pt(innerw/2,-6.5+innerl/2))
        profiles=[p for p in s.profiles if p.profileLoops.count==2]
        assert len(profiles)==1
        return h.extrude(c,s,depth,op,name,profiles[0])

    # Replace the two nut-and-clearance bores without altering the owner's lower body.
    oldaxes=[(14,-29),(-14,29)];axes=[(13,-29),(-13,28)]
    h.circles(case,'Fill old M3 through bores',oldaxes,2.5,3.6,25,O.JoinFeatureOperation)
    h.circles(case,'Fill old M3 captive nut seats',oldaxes,22,6.8,5.5,O.JoinFeatureOperation)
    h.circles(case,'Number4 upper boss reinforcement',axes,15,8,12.5,O.JoinFeatureOperation)
    h.circles(lid,'Fill former M3 lid holes',oldaxes,27.5,3.6,2.5,O.JoinFeatureOperation)

    # The lower edge sits within a chamfered rim. Top cap and antenna stay in place.
    ring(case,'Continuous inward lid bearing ledge',26,29.4,72.4,1.5,O.JoinFeatureOperation)
    ring(case,'Raised locating rim',27.5,32,75,1.5,O.JoinFeatureOperation)
    ring(lid,'Recessed lower lid edge',27.5,31.4,74.4,1.5,O.CutFeatureOperation,80,140,False)
    edges=[]
    for e in case.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z-2.9)<1e-7 and abs(bb.maxPoint.z-2.9)<1e-7:
            if (abs(abs(bb.minPoint.x)-1.6)<1e-7 and abs(bb.maxPoint.x-bb.minPoint.x)<1e-7) or (abs(bb.maxPoint.y-bb.minPoint.y)<1e-7 and (abs(bb.minPoint.y+4.4)<1e-7 or abs(bb.minPoint.y-3.1)<1e-7)):
                edges.append(e)
    assert len(edges)==4,len(edges)
    ci=case.features.chamferFeatures.createInput2();ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(h.coll(edges),h.mm(.5),False)
    ch=case.features.chamferFeatures.add(ci);ch.name='Half millimetre locating rim entry chamfer'

    h.circles(case,'Number4 plastic screw blind pilots',axes,27.5,2.65,'-r08_pilot_depth',O.CutFeatureOperation,'r08_pilot')
    h.circles(lid,'Number4 lid clearance',axes,27.5,3.4,2.5,O.CutFeatureOperation,'r08_lid_clear')
    edges=[]
    for e in case.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z-2.75)<1e-7 and abs(bb.maxPoint.z-2.75)<1e-7 and e.geometry.curveType==adsk.core.Curve3DTypes.Circle3DCurveType:
            g=adsk.core.Circle3D.cast(e.geometry)
            if abs(g.radius-.1325)<1e-7 and any(abs(g.center.x-x/10)<1e-7 and abs(g.center.y-y/10)<1e-7 for x,y in axes):edges.append(e)
    assert len(edges)==2,len(edges)
    ci=case.features.chamferFeatures.createInput2();ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(h.coll(edges),h.mm(.35),False)
    ch=case.features.chamferFeatures.add(ci);ch.name='Number4 pilot lead-in'

    refs=h.component(r,'REF R08 number4 plastic screws nominal')
    h.circles(refs,'Nominal number4 thread envelope',axes,17.3,2.8448,12.7,O.NewBodyFeatureOperation)
    h.circles(refs,'Nominal pan heads',axes,30,5.5626,2.032,O.JoinFeatureOperation)
    next(o for o in r.occurrences if o.component==refs).isLightBulbOn=False
    for o in r.occurrences:
        if o.component.name.startswith(('REF R06 ','REF R07 ')):o.isLightBulbOn=False
    d.computeAll()
    for o in copies.values():
        assert o.component.bRepBodies.count==1 and o.component.bRepBodies.item(0).lumps.count==1
    data={'document':doc.name,'timeline_count':d.timeline.count,'input_archive':str(source.name),'owner_input_case_volume_cm3':initial_case_volume,'lid_screw_axes_mm':axes,'pilot_diameter_mm':2.65,'pilot_depth_mm':12,'screw_under_head_length_mm':12.7,'screw_tip_z_mm':17.3,'pilot_bottom_z_mm':15.5,'tip_clearance_mm':1.8,'rim_top_z_mm':29,'cap_top_z_mm':30,'locating_depth_mm':1.5,'side_clearance_mm':.3,'rim_entry_chamfer_mm':.5,'ledge_bearing_nominal_mm':1,'lower_lid_bounds_xy_mm':[[-15.7,-43.7],[15.7,30.7]],'base_scope':'No modifications intended below Z2.5; exact owner base and lower collar retained, including missing upper-left clamp ear pending owner clarification'}
    (folder/'build-result.json').write_text(json.dumps(data,indent=2)+'\n')
    print(json.dumps(data))
