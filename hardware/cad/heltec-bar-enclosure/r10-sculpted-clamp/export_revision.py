"""Export R10 only after every native edge has two coedges, including periodic seams."""
import adsk.core, adsk.fusion, pathlib, json


def run(_context: str):
    a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    assert a.activeDocument.name=='GoKart Heltec Sculpted Clamp R10'
    folder=pathlib.Path(__file__).resolve().parent;d.computeAll()
    before=json.loads((folder/'input/owner-layout.json').read_text())
    repair=json.loads((folder/'sculpt-audit.json').read_text())
    parts=[o for o in r.occurrences if o.component.name.startswith('R10 ')]
    assert len(parts)==3 and d.timeline.count==repair['timeline_count']
    names={'R10 Sculpted upper clamp and owner case':'case-sculpted-clamp','R10 Preserved recessed lid':'recessed-lid','R10 Sculpted lower clamp':'lower-sculpted-clamp'}
    poses=[]
    for old in before['components']:
        if old['name'].startswith(('REF Heltec','REF GPS accessory','REF 2inch','REF OLED')) or old['name'].strip()=='new ant mount':
            o=next(o for o in r.occurrences if o.component.name==old['name'])
            err=max(abs(x-y) for x,y in zip(o.transform2.asArray(),old['transform']));assert err<1e-8
            poses.append({'component':old['name'],'max_matrix_difference':err,'transform_cm':list(o.transform2.asArray())})
    out=[]
    for o in parts:
        c=o.component;b=c.bRepBodies.item(0);assert c.bRepBodies.count==1 and b.isSolid and b.lumps.count==1
        bad=[e for e in b.edges if e.coEdges.count!=2];assert not bad,c.name+' has non-manifold edge topology'
        slug=names[c.name]
        opt=d.exportManager.createSTLExportOptions(c,str(folder/(slug+'.stl')))
        opt.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits;opt.isBinaryFormat=True;opt.sendToPrintUtility=False;opt.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        assert d.exportManager.execute(opt)
        assert d.exportManager.execute(d.exportManager.createSTEPExportOptions(str(folder/(slug+'.step')),c))
        bb=o.bRepBodies.item(0).boundingBox
        out.append({'component':c.name,'file':slug,'stl':slug+'.stl','step':slug+'.step','solid':b.isSolid,'connected_solids':b.lumps.count,'volume_cm3':b.volume,'all_edges_two_coedges':True,'periodic_seam_edges':sum(e.faces.count==1 and e.coEdges.count==2 for e in b.edges),'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
    unchanged=[]
    for oldname,slug in [('R09 Recessed lid','recessed-lid')]:
        old=next(c for c in before['components'] if c['name']==oldname)['bodies'][0]['volume_cm3']
        new=next(p for p in out if p['file']==slug)['volume_cm3'];assert abs(old-new)<1e-9
        unchanged.append({'part':slug,'volume_delta_cm3':new-old})
    audit={'status':'CAD fastener reversal and subtle machined styling complete; physical FDM fit, grip, strength and endurance remain unvalidated','document':a.activeDocument.name,'timeline_count':d.timeline.count,'authoritative_input':'input/current-R09-before-R10.f3d','owner_pose_comparison':poses,'parts':out,'sculpting_and_fasteners':repair,'unchanged_parts':unchanged,'lid_screws':{'chosen_part':'McMaster92295A103, #4 x 1/2 inch pan-head thread-forming screw for plastic','pilot_diameter_mm':d.userParameters.itemByName('r08_pilot').value*10,'pilot_depth_mm':d.userParameters.itemByName('r08_pilot_depth').value*10,'lid_clearance_mm':d.userParameters.itemByName('r08_lid_clear').value*10,'count':2,'tip_clearance_mm':1.8},'clamp_screws':{'count':2,'specification':'M4 x30 ISO4762/DIN912 socket head recessed above; plain DIN934 M4 nuts captive below','axes_xy_mm':[[-26,0],[26,0]]},'known_fit_limits':['Inherited GPS receiver overlap with conservative OLED cover proxy:0.0845mm in Y and0.3mm in Z; actual accessory fit unverified','Actual mating plugs, harness bundle and bend are unmeasured','Pilot diameter, screw torque, clip flex and ASA/PETG fit need a physical prototype','Clamping force, vibration, FDM strength and weather sealing are not established by manifold CAD geometry'],'feature_warnings':[]}
    for i in range(d.timeline.count):
        t=d.timeline.item(i)
        if t.errorOrWarningMessage:
            e=t.entity;audit['feature_warnings'].append({'timeline_index':i,'name':t.name,'component':e.parentComponent.name if hasattr(e,'parentComponent') else '', 'suppressed':e.isSuppressed if hasattr(e,'isSuppressed') else None,'message':t.errorOrWarningMessage})
    (folder/'model-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
    for o in r.occurrences:
        if o.component.name.startswith('R10 '):o.isLightBulbOn=True
        if o.component.name.startswith(('REF R06 ','REF R07 ','REF R08 ')):o.isLightBulbOn=False
    assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(folder/'GoKart-Heltec-Sculpted-Clamp-R10.f3d')))
    print('R10 native, three STEP/STL pairs and model audit exported; every native edge has two coedges.')
