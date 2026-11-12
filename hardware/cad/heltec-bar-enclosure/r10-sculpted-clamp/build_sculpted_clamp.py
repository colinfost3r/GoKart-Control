"""R10: top socket heads, bottom nut traps and restrained exterior shaping.
Preserves the owner case/lid interfaces and the R09 structural webs and tube surfaces.
"""
import adsk.core, adsk.fusion, pathlib, importlib.util, json, math


def run(_context: str):
    folder=pathlib.Path(__file__).resolve().parent
    a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec Connected Clamp R09'
    doc=a.importManager.importToNewDocument(a.importManager.createFusionArchiveImportOptions(str(folder/'input/current-R09-before-R10.f3d')));assert doc
    doc.name='GoKart Heltec Sculpted Clamp R10'
    d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    sp=importlib.util.spec_from_file_location('helpers',str(folder.parent/'r03-parallel/build_model.py'))
    h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
    O=adsk.fusion.FeatureOperations;axes=[(-26,0),(26,0)];parts={}
    for oldname,newname in [('R09 Case with connected clamp ears','R10 Sculpted upper clamp and owner case'),('R09 Recessed lid','R10 Preserved recessed lid'),('R09 Owner lower collar','R10 Sculpted lower clamp')]:
        old=next(o for o in r.occurrences if o.component.name==oldname)
        new=r.occurrences.addNewComponent(adsk.core.Matrix3D.create());new.component.name=newname
        assert old.bRepBodies.item(0).copyToComponent(new);old.isLightBulbOn=False;parts[newname]=new
    case=parts['R10 Sculpted upper clamp and owner case'].component
    lower=parts['R10 Sculpted lower clamp'].component
    changes=[]
    def chamfer(c,name,edges,size):
        assert edges,name+' has no selected edges'
        records=[[[v*10 for v in e.boundingBox.minPoint.asArray()],[v*10 for v in e.boundingBox.maxPoint.asArray()]] for e in edges]
        ci=c.features.chamferFeatures.createInput2();ci.chamferEdgeSets.addEqualDistanceChamferEdgeSet(h.coll(edges),h.mm(size),False)
        f=c.features.chamferFeatures.add(ci);f.name=name
        changes.append({'feature':name,'size_mm':size,'selected_edge_bounds_mm':records})
    # Fill only the obsolete voids within each existing ear envelope.
    h.circles(case,'Fill obsolete upper hex nut traps',axes,-6,8.6,3.4,O.JoinFeatureOperation)
    for x in [-29.5,29.5]:h.box(case,'Fill obsolete upper nut insertion slot',x,0,-6,7,7.5,3.4,O.JoinFeatureOperation)
    h.circles(lower,'Fill obsolete lower head counterbores',axes,-34,8.2,2,O.JoinFeatureOperation)
    for c in [case,lower]:h.circles(c,'Retain aligned M4 shaft clearances',axes,-36,4.5,37,O.CutFeatureOperation)
    h.circles(case,'Fully recessed top M4 socket heads',axes,0,8.2,-4.5,O.CutFeatureOperation)
    h.hexholes(lower,'Bottom facing plain M4 nut traps',axes,-34,7.3,3.4)
    edges=[]
    for e in case.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z)<1e-7 and abs(bb.maxPoint.z)<1e-7 and e.geometry.curveType==adsk.core.Curve3DTypes.Circle3DCurveType:
            g=adsk.core.Circle3D.cast(e.geometry)
            if abs(g.radius-.41)<1e-7:edges.append(e)
    assert len(edges)==2
    chamfer(case,'Top head counterbore entry chamfers',edges,.5)
    edges=[]
    for e in lower.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z+3.4)<1e-7 and abs(bb.maxPoint.z+3.4)<1e-7 and e.geometry.curveType==adsk.core.Curve3DTypes.Line3DCurveType:
            if any(bb.minPoint.x>x/10-.43 and bb.maxPoint.x<x/10+.43 and bb.minPoint.y>-.43 and bb.maxPoint.y<.43 for x,y in axes):edges.append(e)
    assert len(edges)==12,len(edges)
    chamfer(lower,'Bottom nut insertion lead-ins',edges,.3)

    # Broad but shallow shoulders preserve flat fastener pads and all mating surfaces.
    edges=[]
    for e in case.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z)<1e-7 and abs(bb.maxPoint.z)<1e-7:
            outside=bb.minPoint.x>=1.7999 or bb.maxPoint.x<=-1.7999
            perimeter=max(abs(bb.minPoint.x),abs(bb.maxPoint.x))>3.2999 or max(abs(bb.minPoint.y),abs(bb.maxPoint.y))>1.1999
            inner=(abs(abs(bb.minPoint.x)-1.8)<1e-7 and abs(bb.maxPoint.x-bb.minPoint.x)<1e-7)
            if outside and perimeter and not inner:edges.append(e)
    chamfer(case,'Machined style upper ear shoulders',edges,1)
    edges=[]
    for e in lower.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z+3.4)<1e-7 and abs(bb.maxPoint.z+3.4)<1e-7:
            if max(abs(bb.minPoint.x),abs(bb.maxPoint.x))>3.2999 or max(abs(bb.minPoint.y),abs(bb.maxPoint.y))>1.1999:edges.append(e)
    chamfer(lower,'Machined style lower outer perimeter',edges,1)
    edges=[]
    for e in case.bRepBodies.item(0).edges:
        bb=e.boundingBox
        if abs(bb.minPoint.z)<1e-7 and abs(bb.maxPoint.z)<1e-7 and abs(abs(bb.minPoint.x)-1.4)<1e-7 and abs(bb.maxPoint.x-bb.minPoint.x)<1e-7 and bb.minPoint.y>=-1.20001 and bb.maxPoint.y<=1.20001:edges.append(e)
    assert len(edges)==2,len(edges)
    bounds=[[[v*10 for v in e.boundingBox.minPoint.asArray()],[v*10 for v in e.boundingBox.maxPoint.asArray()]] for e in edges]
    fi=case.features.filletFeatures.createInput();fi.edgeSetInputs.addConstantRadiusEdgeSet(h.coll(edges),h.mm(1.5),False)
    f=case.features.filletFeatures.add(fi);f.name='Flowing additive web root transitions'
    changes.append({'feature':f.name,'radius_mm':1.5,'selected_edge_bounds_mm':bounds,'intent':'Concave additive fillet; retain full4mm web sections'})

    refs=h.component(r,'REF R10 M4x30 top socket screws nominal')
    h.circles(refs,'Nominal M4 shaft envelopes',axes,-34.5,4,30,O.NewBodyFeatureOperation)
    h.circles(refs,'ISO4762 head envelopes',axes,-4.5,7,4,O.JoinFeatureOperation)
    h.hexholes(refs,'Three millimetre Allen sockets',axes,-.5,3,-2)
    nuts=h.component(r,'REF R10 bottom plain M4 nuts nominal');s=h.sketch(nuts,-33.8,'Plain M4 nut envelopes')
    for x,y in axes:h.polygon(s,x,y,7/math.sqrt(3),6,math.pi/6)
    h.extrude(nuts,s,3.2,O.NewBodyFeatureOperation,'Nominal DIN934 M4 nuts')
    h.circles(nuts,'Nominal nut thread clearance envelope',axes,-34,4.2,3.5,O.CutFeatureOperation)
    for o in r.occurrences:
        if o.component.name.startswith(('REF R06 ','REF R07 ','REF R08 ','REF R10 ')):o.isLightBulbOn=False
    d.computeAll()
    for o in parts.values():
        b=o.component.bRepBodies.item(0);assert o.component.bRepBodies.count==1 and b.isSolid and b.lumps.count==1 and all(e.coEdges.count==2 for e in b.edges)
    report={'document':doc.name,'timeline_count':d.timeline.count,'input_archive':'input/current-R09-before-R10.f3d','M4_axes_xy_mm':axes,'head_counterbore_mm':{'diameter':8.2,'depth':4.5,'entry_chamfer':.5},'socket_screw_mm':{'under_head_length':30,'head_diameter':7,'head_height':4,'Allen_size':3,'head_bearing_z':-4.5,'head_top_z':-.5,'tip_z':-34.5},'bottom_nut_traps_mm':{'across_flats':7.3,'depth':3.4,'entry_chamfer':.3,'opening_z':-34,'bearing_z':-30.6},'plain_nut_mm':{'across_flats':7,'height':3.2,'top_z':-30.6,'bottom_z':-33.8,'screw_beyond_nut':.7},'exterior_shaping':changes,'protected_features':'Lid/sill, uppercaseZ>0, tube bore, split faces,4mmwebminimum, hardware/GPS/harness poses unchanged; M4fastenerinterfaces explicitly reversed','appearance':'Geometry inspired by sculpted bicycle controls; no logos or simulated anodized metal'}
    (folder/'sculpt-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'document':doc.name,'timeline_count':d.timeline.count,'parts_connected':True,'shaping_features':[x['feature'] for x in changes]}))
