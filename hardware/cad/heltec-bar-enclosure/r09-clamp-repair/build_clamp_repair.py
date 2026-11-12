"""R09 additive repair: preserve the extended owner base and restore connected clamp ears.
Mirror the surviving ear exactly, then add finite-thickness webs inside the existing case envelope.
Run only from the archived R08 source; never regenerate older owner-edited revisions.
"""
import adsk.core, adsk.fusion, pathlib, importlib.util, json

def run(_context: str):
    folder=pathlib.Path(__file__).resolve().parent
    a=adsk.core.Application.get();assert a.activeDocument.name=='GoKart Heltec Recessed Lid R08'
    doc=a.importManager.importToNewDocument(a.importManager.createFusionArchiveImportOptions(str(folder/'input/current-R08-before-R09.f3d')));assert doc
    doc.name='GoKart Heltec Connected Clamp R09'
    d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    sp=importlib.util.spec_from_file_location('helpers',str(folder.parent/'r03-parallel/build_model.py'))
    h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
    O=adsk.fusion.FeatureOperations;T=adsk.fusion.TemporaryBRepManager.get();BT=adsk.fusion.BooleanTypes
    pieces={}
    for oldname,newname in [('R08 Owner base and recessed sill','R09 Case with connected clamp ears'),('R08 Stepped lid for number4 screws','R09 Recessed lid'),('R08 Owner lower collar','R09 Owner lower collar')]:
        old=next(o for o in r.occurrences if o.component.name==oldname)
        new=r.occurrences.addNewComponent(adsk.core.Matrix3D.create());new.component.name=newname
        assert old.bRepBodies.item(0).copyToComponent(new)
        old.isLightBulbOn=False;pieces[newname]=new
    c=pieces['R09 Case with connected clamp ears'].component
    before_volume=c.bRepBodies.item(0).volume
    source_body=T.copy(c.bRepBodies.item(0))
    right_ear=T.copy(source_body)
    box=adsk.core.OrientedBoundingBox3D.create(h.pt(26,0,-8.125),adsk.core.Vector3D.create(1,0,0),adsk.core.Vector3D.create(0,1,0),1.6,2.4,1.625)
    assert T.booleanOperation(right_ear,T.createBox(box),BT.IntersectionBooleanType)
    assert right_ear.isSolid and right_ear.lumps.count==1
    ear_volume=right_ear.volume
    mirror=adsk.core.Matrix3D.create();mirror.setCell(0,0,-1)
    assert T.transform(right_ear,mirror)
    assert all(e.coEdges.count==2 for e in right_ear.edges)

    # Finite side walls fill only the former internal gap, clear of the tube bore.
    for x in [-16,16]:
        h.box(c,'Four millimetre clamp connection web',x,0,-16.25,4,24,16.25,O.JoinFeatureOperation)
    # Import the reflected exact ear as a base body, then unite it with the new left web.
    base=c.features.baseFeatures.add();base.name='Exact mirrored surviving ear';assert base.startEdit()
    body=c.bRepBodies.add(right_ear,base);assert body
    assert base.finishEdit()
    assert c.bRepBodies.count==2
    target=max(list(c.bRepBodies),key=lambda b:b.volume);tool=min(list(c.bRepBodies),key=lambda b:b.volume)
    inp=c.features.combineFeatures.createInput(target,h.coll([tool]));inp.operation=O.JoinFeatureOperation;inp.isKeepToolBodies=False
    f=c.features.combineFeatures.add(inp);f.name='Join restored left ear to structural web'
    d.computeAll()
    body=c.bRepBodies.item(0)
    assert c.bRepBodies.count==1 and body.isSolid and body.lumps.count==1
    assert all(e.coEdges.count==2 for e in body.edges),[(e.faces.count,e.coEdges.count) for e in body.edges if e.coEdges.count!=2]
    for o in pieces.values():
        b=o.component.bRepBodies.item(0);assert b.isSolid and b.lumps.count==1 and all(e.coEdges.count==2 for e in b.edges)
    # Boolean subtraction proves the additive repair did not remove original material.
    missing=T.copy(source_body);assert T.booleanOperation(missing,T.copy(body),BT.DifferenceBooleanType)
    removed_volume=missing.volume
    assert abs(removed_volume)<1e-9
    report={'document':doc.name,'timeline_count':d.timeline.count,'input_archive':'input/current-R08-before-R09.f3d','owner_base_preservation':'Additive repairs only; original body minus repaired body has zero volume','original_case_volume_cm3':before_volume,'repaired_case_volume_cm3':body.volume,'removed_original_volume_cm3':removed_volume,'mirrored_surviving_ear_volume_cm3':ear_volume,'webs_mm':[{'x':[-18,-14],'y':[-12,12],'z':[-16.25,0]},{'x':[14,18],'y':[-12,12],'z':[-16.25,0]}],'web_thickness_mm':4,'tube_diameter_mm':25.273,'bore_diameter_mm':25.523,'minimum_web_to_bore_radial_allowance_mm':1.2385,'split_gap_mm':1.5,'M4_axes_xy_mm':[[-26,0],[26,0]],'clamp_width_mm':66,'native_case_edges_have_two_coedges':True,'note':'Periodic seam edges can have one unique face and two coedges; two-coedge topology is the intended check.'}
    (folder/'repair-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))
