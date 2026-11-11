"""Export R05 print parts only; authoritative owner references remain in the native file."""
import adsk.core, adsk.fusion, json, pathlib, math

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec Rectangular Owner Layout R05'
 folder=pathlib.Path(__file__).resolve().parent
 parts=[o for o in r.occurrences if o.component.name.startswith('R05 ')]
 assert len(parts)==4
 d.computeAll()
 before=json.loads((folder/'input/owner-layout.json').read_text())
 comparisons=[]
 for c in before['components']:
  if c['name'].startswith(('REF Heltec','REF GPS accessory','REF 2inch')) or c['name'].strip()=='new ant mount':
   o=next(o for o in r.occurrences if o.component.name==c['name'])
   error=max(abs(x-y) for x,y in zip(c['transform'],o.transform2.asArray()))
   assert error<1e-8
   comparisons.append({'component':c['name'],'max_matrix_difference':error,'transform_cm':list(o.transform2.asArray())})
 slugs={'R05 Case and upper collar':'case-upper-collar','R05 OLED lid with integral antenna mount':'lid-integral-antenna','R05 Lower collar':'lower-collar','R05 GPS slide tray with end latch':'gps-slide-tray'}
 out=[]
 for o in parts:
  c=o.component;b=c.bRepBodies.item(0)
  assert c.bRepBodies.count==1 and b.isSolid and b.lumps.count==1
  o.isLightBulbOn=True;slug=slugs[c.name]
  stl=d.exportManager.createSTLExportOptions(c,str(folder/(slug+'.stl')))
  stl.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits;stl.isBinaryFormat=True;stl.sendToPrintUtility=False;stl.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh
  assert d.exportManager.execute(stl)
  assert d.exportManager.execute(d.exportManager.createSTEPExportOptions(str(folder/(slug+'.step')),c))
  bb=o.bRepBodies.item(0).boundingBox
  out.append({'component':c.name,'file':slug,'connected_solids':b.lumps.count,'volume_cm3':b.volume,'assembly_bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]],'assembly_transform':list(o.transform2.asArray())})
 antenna=next(o for o in r.occurrences if o.component.name=='REF 2inch antenna envelope diameter7mm assumed')
 surf=next(f.geometry for b in antenna.bRepBodies for f in b.faces if f.geometry.surfaceType==adsk.core.SurfaceTypes.CylinderSurfaceType)
 native=folder/'GoKart-Heltec-Rectangular-Owner-Layout-R05.f3d'
 assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(native)))
 qa={'document':a.activeDocument.name,'status':'fit-check prototype, not print-fit or road acceptance','nominal_shell_mm':{'width_x':36,'length_y':77,'body_plus_lid_height_z':30},'bar_mm':25.273,'bore_mm':25.523,'installation_screws':4,'owner_pose_comparison':comparisons,'antenna_mount':{'center_mm':[v*10 for v in surf.origin.asArray()],'axis':list(surf.axis.asArray()),'cant_from_vertical_deg':math.degrees(math.acos(surf.axis.z)),'panel_hole_mm':6.6,'panel_thickness_mm':2,'rear_access_bore_mm':13.2,'reference_length_mm':50.8,'reference_diameter_assumed_mm':7,'actual_bulkhead_dimensions':'unmeasured'},'oled_window':{'lower_opening_mm':[14.4,25],'upper_opening_mm':[18.4,29],'nominal_visible_display_mm':[11.4,22],'full_display_view_angle_from_vertical_deg_estimate':12,'purpose':'straight-down service view; physical viewability untested'},'tray':{'inserted_center_y_mm':-33,'extraction_direction':[0,-1,0],'fully_extracted_translation_mm':[0,-25,0],'track_width_mm':20.8,'tray_width_mm':20.3,'latch_beam_mm':[6,10,.8],'latch_release_rise_mm':1.1,'release_method':'push tongue upward from underside, then pull rearward','gps_retention':'small hot-glue pads at PCB edges/back; do not press ceramic'},'known_fit_limits':['Owner GPS receiver overlaps conservative rectangular OLED-cover proxy by approximately0.094mm inY and0.3mm inZ; real cover and module must be checked without force.','Physical GPS accessory differs between official photo and STEP; actual fit and harness route remain unverified.','USB plug overmould, SMA bulkhead nut/thread, print shrinkage, latch durability and clamp strength require physical checks.'],'parts':out,'feature_warnings':[]}
 for i in range(d.timeline.count):
  item=d.timeline.item(i)
  if item.errorOrWarningMessage:qa['feature_warnings'].append({'name':item.name,'message':item.errorOrWarningMessage})
 (folder/'model-audit.json').write_text(json.dumps(qa,indent=2)+'\n')
 a.userInterface.activeSelections.clear();d.activateRootComponent();a.activeViewport.fit();a.activeViewport.saveAsImageFile(str(folder/'assembled-preview.png'),1600,1200)
 print('Exported R05 nativeF3D, fourSTEP, fourSTL, audit and assembled preview.')
