"""Export only the four printable components; references stay in the native assembly."""
import adsk.core, adsk.fusion, json, pathlib

def run(_context: str):
    app=adsk.core.Application.get();d=adsk.fusion.Design.cast(app.activeProduct)
    assert app.activeDocument.name=='GoKart Heltec L76K Compact Parallel R03'
    folder=pathlib.Path(__file__).resolve().parent
    parts=[o for o in d.rootComponent.occurrences if o.component.name.startswith(('C01 ','C02 ','C03 ','C04 '))]
    assert len(parts)==4
    d.computeAll()
    out=[]
    for o in parts:
        c=o.component
        assert c.bRepBodies.count==1 and c.bRepBodies.item(0).isSolid and c.bRepBodies.item(0).lumps.count==1,c.name
        o.isLightBulbOn=True
        slug={'C01':'case-upper-collar','C02':'lower-collar','C03':'lid-gps-retainers','C04':'antenna-insert-15deg'}[c.name[:3]]
        stl=d.exportManager.createSTLExportOptions(c,str(folder/(slug+'.stl')))
        stl.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits
        stl.isBinaryFormat=True;stl.sendToPrintUtility=False
        stl.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
        assert d.exportManager.execute(stl)
        step=d.exportManager.createSTEPExportOptions(str(folder/(slug+'.step')),c)
        assert d.exportManager.execute(step)
        b=c.bRepBodies.item(0);bb=b.boundingBox
        out.append({'component':c.name,'file':slug,'connected_solids':b.lumps.count,'volume_cm3':b.volume,
                    'local_bounds_mm':[[x*10 for x in bb.minPoint.asArray()],[x*10 for x in bb.maxPoint.asArray()]],
                    'assembly_transform':list(o.transform2.asArray())})
    native=d.exportManager.createFusionArchiveExportOptions(str(folder/'GoKart-Heltec-Compact-Parallel-R03.f3d'))
    assert d.exportManager.execute(native)
    qa={'document':app.activeDocument.name,'release_status':'fit-check prototype; not fleet/road acceptance',
        'case_nominal_mm':[66,36,30],'overall_printed_plan_mm':[66,50],
        'bar_nominal_mm':25.273,'bar_bore_mm':25.523,'installation_screws':4,
        'sma_cant_degrees':15,'antenna_reference_length_mm':50.8,'antenna_reference_diameter_mm_assumed':7,
        'parts':out,'parameters':[{ 'name':p.name,'expression':p.expression,'comment':p.comment} for p in d.userParameters],
        'feature_warnings':[],'import_group_status':[]}
    for i in range(d.timeline.count):
        item=d.timeline.item(i)
        if item.healthState!=adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
            if item.errorOrWarningMessage:qa['feature_warnings'].append({'name':item.name,'message':item.errorOrWarningMessage})
            else:qa['import_group_status'].append(item.name)
    (folder/'model-audit.json').write_text(json.dumps(qa,indent=2)+'\n')
    app.userInterface.activeSelections.clear();d.activateRootComponent();app.activeViewport.fit()
    app.activeViewport.saveAsImageFile(str(folder/'assembled-preview.png'),1600,1200)
    print('Exported nativeF3D,4STEP,4STL(mm),auditandassembledpreview to',folder)
