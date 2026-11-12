"""Archive the exact owner-extended R07 before R08 modifications."""
import adsk.core, adsk.fusion, pathlib, json

def run(_context: str):
    a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    assert a.activeDocument.name=='GoKart Heltec FDM Supports R07'
    folder=pathlib.Path(__file__).resolve().parent/'input'
    archive=folder/'owner-extended-R07-timeline-677.f3d'
    assert not archive.exists()
    assert d.timeline.count==677
    data={'document':a.activeDocument.name,'timeline_count':d.timeline.count,'components':[],'owner_new_features':[]}
    for o in r.occurrences:
        bodies=[]
        for b in o.bRepBodies:
            bb=b.boundingBox
            bodies.append({'name':b.name,'volume_cm3':b.volume,'solid':b.isSolid,'lumps':b.lumps.count,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
        data['components'].append({'name':o.component.name,'transform':list(o.transform2.asArray()),'visible':o.isLightBulbOn,'bodies':bodies})
    for i in range(670,d.timeline.count):
        t=d.timeline.item(i);e=t.entity
        row={'timeline_index':i,'name':t.name,'type':e.objectType,'warning':t.errorOrWarningMessage}
        if hasattr(e,'extentOne') and hasattr(e.extentOne,'distance'):row['distance']=e.extentOne.distance.expression
        if hasattr(e,'distance'):row['distance']=e.distance.expression
        if hasattr(e,'parentComponent'):row['component']=e.parentComponent.name
        if hasattr(e,'faces'):
            row['current_face_bounds_mm']=[[[v*10 for v in f.boundingBox.minPoint.asArray()],[v*10 for v in f.boundingBox.maxPoint.asArray()]] for f in e.faces]
        data['owner_new_features'].append(row)
    assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(archive)))
    (folder/'owner-layout.json').write_text(json.dumps(data,indent=2)+'\n')
    assert a.activeViewport.saveAsImageFile(str(folder/'owner-input-view.png'),1600,1200)
    print('Archived exact owner timeline 677 without changing geometry or visibility.')
