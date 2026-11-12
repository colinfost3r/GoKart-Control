"""Export the preserved-base R08 and record current model evidence."""
import adsk.core, adsk.fusion, pathlib, json


def run(_context: str):
    a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    assert a.activeDocument.name=='GoKart Heltec Recessed Lid R08'
    folder=pathlib.Path(__file__).resolve().parent;d.computeAll()
    before=json.loads((folder/'input/owner-layout.json').read_text())
    build=json.loads((folder/'build-result.json').read_text())
    parts=[o for o in r.occurrences if o.component.name.startswith('R08 ')]
    assert len(parts)==3
    names={'R08 Owner base and recessed sill':'case-recessed-sill','R08 Stepped lid for number4 screws':'stepped-lid','R08 Owner lower collar':'lower-collar'}
    poses=[]
    for old in before['components']:
        if old['name'].startswith(('REF Heltec','REF GPS accessory','REF 2inch','REF OLED')) or old['name'].strip()=='new ant mount':
            o=next(o for o in r.occurrences if o.component.name==old['name'])
            err=max(abs(x-y) for x,y in zip(o.transform2.asArray(),old['transform']));assert err<1e-8
            poses.append({'component':old['name'],'max_matrix_difference':err,'transform_cm':list(o.transform2.asArray())})
    features=[]
    for row in before['owner_new_features']:
        t=d.timeline.item(row['timeline_index']);assert t.name==row['name']
        features.append({'index':row['timeline_index'],'name':t.name,'warning':t.errorOrWarningMessage})
    out=[]
    for o in parts:
        c=o.component;b=c.bRepBodies.item(0);assert c.bRepBodies.count==1 and b.isSolid and b.lumps.count==1
        slug=names[c.name]
        nonmanifold=[{'incident_faces':e.faces.count,'bounds_mm':[[v*10 for v in e.boundingBox.minPoint.asArray()],[v*10 for v in e.boundingBox.maxPoint.asArray()]]} for e in b.edges if e.faces.count!=2]
        assert not nonmanifold or slug=='case-recessed-sill', 'Unexpected defect in '+slug+'; stop and inspect'
        stl_file='diagnostics/case-as-edited-NOT-PRINT-READY.stl' if nonmanifold else slug+'.stl'
        (folder/stl_file).parent.mkdir(exist_ok=True)
        opt=d.exportManager.createSTLExportOptions(c,str(folder/stl_file))
        opt.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits;opt.isBinaryFormat=True;opt.sendToPrintUtility=False;opt.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        assert d.exportManager.execute(opt)
        assert d.exportManager.execute(d.exportManager.createSTEPExportOptions(str(folder/(slug+'.step')),c))
        bb=o.bRepBodies.item(0).boundingBox
        out.append({'component':c.name,'file':slug,'stl':stl_file,'step':slug+'.step','solid':b.isSolid,'connected_solids':b.lumps.count,'volume_cm3':b.volume,'nonmanifold_native_edges':nonmanifold,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
    oldlower=next(c for c in before['components'] if c['name']=='R07 Outboard lower collar')['bodies'][0]['volume_cm3']
    newlower=next(p for p in out if p['file']=='lower-collar')['volume_cm3']
    assert abs(oldlower-newlower)<1e-9
    audit={'status':'Lid revision complete; case print release blocked until inherited edge-only clamp-ear attachment is resolved. Check native-edge and STL validation, not isSolid alone.','document':a.activeDocument.name,'timeline_count':d.timeline.count,'authoritative_input':'input/owner-extended-R07-timeline-677.f3d','owner_features_retained':features,'owner_pose_comparison':poses,'parts':out,'lid_revision':build,'parameters_mm':{n:d.userParameters.itemByName(n).value*10 for n in ['r08_pilot','r08_pilot_depth','r08_lid_clear']},'lower_collar_volume_delta_cm3':newlower-oldlower,'owner_base_scope':'Owner exterior/skirt geometry unchanged; independent review compares geometry at or below Z2.49 mm. Obsolete M3 bores within pillars are intentionally filled for screw conversion.','screw_type':'#4 x 1/2 inch pan-head plastic thread-forming, modeled around McMaster92295A103; not generic sheet-metal screw','screw_reference':'Smooth crest and head envelopes; crest-to-pilot overlap is intentional thread-forming engagement, not an unexpected clash','mount_status':'Owner input upper-left clamp ear absent; preserved pending owner decision','known_fit_limits':['Inherited GPS receiver overlap with conservative OLED cover proxy:0.0845mm in Y and0.3mm in Z; actual accessory fit unverified','Actual mated GPS/P3 plugs, harness bundle and bend are unmeasured','Pilot diameter, screw torque, clip flex and ASA/PETG fit need a physical prototype','A recessed ledge is not a validated water seal'],'feature_warnings':[]}
    for i in range(d.timeline.count):
        t=d.timeline.item(i)
        if t.errorOrWarningMessage:
            e=t.entity
            audit['feature_warnings'].append({'timeline_index':i,'name':t.name,'component':e.parentComponent.name if hasattr(e,'parentComponent') else '', 'suppressed':e.isSuppressed if hasattr(e,'isSuppressed') else None,'message':t.errorOrWarningMessage})
    (folder/'model-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    for o in r.occurrences:
        if o.component.name.startswith('R08 '):o.isLightBulbOn=True
        if o.component.name.startswith(('REF R06 ','REF R07 ','REF R08 ')):o.isLightBulbOn=False
    assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(folder/'GoKart-Heltec-Recessed-Lid-R08.f3d')))
    print('R08 native and STEP files exported; non-manifold case STL routed to diagnostics, valid candidates kept separately.')
