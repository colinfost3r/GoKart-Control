"""Archive the exact live R09 before approved fastener reversal and exterior shaping."""
import adsk.core, adsk.fusion, pathlib, json

def run(_context: str):
    a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    assert a.activeDocument.name=='GoKart Heltec Connected Clamp R09' and d.timeline.count==733
    folder=pathlib.Path(__file__).resolve().parent/'input'
    archive=folder/'current-R09-before-R10.f3d';assert not archive.exists()
    data={'document':a.activeDocument.name,'timeline_count':d.timeline.count,'components':[],'feature_warnings':[]}
    for o in r.occurrences:
        bodies=[]
        for b in o.bRepBodies:
            bb=b.boundingBox
            bodies.append({'name':b.name,'volume_cm3':b.volume,'solid':b.isSolid,'lumps':b.lumps.count,'invalid_edge_coedge_counts':[e.coEdges.count for e in b.edges if e.coEdges.count!=2],'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
        data['components'].append({'name':o.component.name,'transform':list(o.transform2.asArray()),'visible':o.isLightBulbOn,'bodies':bodies})
    for i in range(d.timeline.count):
        t=d.timeline.item(i)
        if t.errorOrWarningMessage:data['feature_warnings'].append({'index':i,'name':t.name,'message':t.errorOrWarningMessage})
    assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(archive)))
    (folder/'owner-layout.json').write_text(json.dumps(data,indent=2)+'\n')
    assert a.activeViewport.saveAsImageFile(str(folder/'input-view.png'),1600,1200)
    print('Current R09 archived without geometry changes.')
