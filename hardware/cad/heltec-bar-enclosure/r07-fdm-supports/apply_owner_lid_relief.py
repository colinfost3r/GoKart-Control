"""Apply only the reviewed lid relief after archiving authoritative owner R07 edits.
Never rebuild or alter the owner-edited case. Run once at the captured timeline667.
"""
import adsk.core, adsk.fusion, importlib.util, pathlib, json

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec FDM Supports R07' and d.timeline.count==667
 folder=pathlib.Path(__file__).resolve().parent;owner=json.loads((folder/'input/owner-edited-R07-timeline-667.json').read_text())
 case=next(o for o in r.occurrences if o.component.name=='R07 Case with floor-backed GPS supports');lid=next(o for o in r.occurrences if o.component.name=='R07 OLED and antenna lid')
 before=case.bRepBodies.item(0).volume;lid_before=lid.bRepBodies.item(0).volume
 saved=[(o,list(o.transform2.asArray())) for o in r.occurrences]
 sp=importlib.util.spec_from_file_location('h',str(folder.parent/'r03-parallel/build_model.py'));h=importlib.util.module_from_spec(sp);sp.loader.exec_module(h)
 h.box(lid.component,'Lid relief around owner front support',-7.475,-20.025,14.1,2.65,1.05,3.4,adsk.fusion.FeatureOperations.CutFeatureOperation)
 d.computeAll();after=case.bRepBodies.item(0).volume;assert abs(after-before)<1e-10
 assert lid.component.bRepBodies.count==1 and lid.bRepBodies.item(0).lumps.count==1
 for o,pose in saved:assert max(abs(x-y) for x,y in zip(o.transform2.asArray(),pose))<1e-8
 for f in owner['owner_features']:assert d.timeline.item(f['timeline_index']).name==f['name']
 footprints=[]
 for f in lid.bRepBodies.item(0).faces:
  bb=f.boundingBox
  if abs(bb.minPoint.z-1.43)<1e-7 and abs(bb.maxPoint.z-1.43)<1e-7:
   footprints.append({'area_mm2':f.area*100,'bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
 data={'authoritative_owner_archive':'input/owner-edited-R07-timeline-667.f3d','owner_timeline_count':667,'owner_features_retained':[f['name'] for f in owner['owner_features']],'final_timeline_count':d.timeline.count,'owner_case_volume_before_cm3':before,'owner_case_volume_after_cm3':after,'case_volume_delta_cm3':after-before,'lid_volume_before_cm3':lid_before,'lid_volume_after_cm3':lid.bRepBodies.item(0).volume,'approved_change':'Local lid-only relief; owner case geometry and completed features untouched','relief_bounds_mm':[[-8.8,-20.55,14.1],[-6.15,-19.5,17.5]],'lid_connected_solids':1,'remaining_capture_faces_z14p3_mm':footprints,'source_status':'build_fdm_revision.py is generated base only; final native is authoritative'}
 (folder/'owner-edit-provenance.json').write_text(json.dumps(data,indent=2)+'\n')
 print(json.dumps(data))
