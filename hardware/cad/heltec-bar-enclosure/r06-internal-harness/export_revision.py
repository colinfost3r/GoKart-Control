"""Export only the three R06 print parts; references remain in the native assembly."""
import adsk.core, adsk.fusion, pathlib, json, math

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec Internal Harness R06'
 folder=pathlib.Path(__file__).resolve().parent;d.computeAll()
 parts=[o for o in r.occurrences if o.component.name.startswith('R06 ')];assert len(parts)==3
 names={'R06 Case with internal GPS socket':'case-upper-collar','R06 OLED and antenna lid':'lid-integral-antenna','R06 Lower collar':'lower-collar'}
 before=json.loads((folder/'input/owner-layout.json').read_text());comparisons=[]
 for old in before['components']:
  if old['name'].startswith(('REF Heltec','REF GPS accessory','REF 2inch','REF OLED')) or old['name'].strip()=='new ant mount':
   o=next(o for o in r.occurrences if o.component.name==old['name']);error=max(abs(x-y) for x,y in zip(o.transform2.asArray(),old['transform']));assert error<1e-8
   comparisons.append({'component':old['name'],'max_matrix_difference':error,'transform_cm':list(o.transform2.asArray())})
 out=[]
 for o in parts:
  c=o.component;b=c.bRepBodies.item(0);assert c.bRepBodies.count==1 and b.isSolid and b.lumps.count==1
  slug=names[c.name];opt=d.exportManager.createSTLExportOptions(c,str(folder/(slug+'.stl')));opt.unitType=adsk.fusion.DistanceUnits.MillimeterDistanceUnits;opt.isBinaryFormat=True;opt.sendToPrintUtility=False;opt.meshRefinement=adsk.fusion.MeshRefinementSettings.MeshRefinementHigh;assert d.exportManager.execute(opt)
  assert d.exportManager.execute(d.exportManager.createSTEPExportOptions(str(folder/(slug+'.step')),c))
  bb=o.bRepBodies.item(0).boundingBox;out.append({'component':c.name,'file':slug,'connected_solids':b.lumps.count,'volume_cm3':b.volume,'assembly_bounds_mm':[[v*10 for v in bb.minPoint.asArray()],[v*10 for v in bb.maxPoint.asArray()]]})
 antenna=next(o for o in r.occurrences if o.component.name=='REF 2inch antenna envelope diameter7mm assumed');surface=next(f.geometry for b in antenna.bRepBodies for f in b.faces if f.geometry.surfaceType==adsk.core.SurfaceTypes.CylinderSurfaceType)
 audit={'document':a.activeDocument.name,'status':'physical fit prototype','nominal_shell_mm':[79,36,30],'bar_mm':25.273,'bore_mm':25.523,'installation_screws':4,'printed_parts':3,'owner_pose_comparison':comparisons,'owner_input':'Current R05 including DeleteFace1 and DeleteFace2 preserved in input/','gps_socket':{'rear_bare_connector_y_mm':-39.752710246011276,'inner_rear_wall_y_mm':-44,'bare_connector_rear_clearance_mm':4.247289753988724,'clearance_reference':'Owner confirmed4mm behind bare board socket','pcb_support_z_mm':15.6,'pcb_top_z_mm':17.2,'upper_capture_z_mm':17.5,'retention':'Fixed rear PCB lips and one front end clip; serviced with lid removed'},'harness':{'destination':'Heltec P3 SH1.25 8-pin GNSS connector under PCB; rearward mating approach','P3_bounds_mm':[[-7.499499445799438,-17.34389755641854,3.3412281448183734],[7.500500898161686,-12.043896972273727,6.941229407575513]],'wire_envelope_mm':[8,2],'GPS_plug_envelope_assumed_mm':[12,3,2.5],'P3_plug_envelope_assumed_mm':[12,5,2.7],'under_PCB_wire_center_z_mm':5.1,'route_reference_rear_wall_gap_mm':.25,'route':'Behind GPS bare socket, downward behind boards, forward beneath Heltec PCB into P3','actual_harness':'Unmeasured plug sizes, wire thickness, length and bend radius; square-corner envelope is clearance reference only'},'antenna':{'mount_center_mm':[v*10 for v in surface.origin.asArray()],'axis':list(surface.axis.asArray()),'cant_from_vertical_deg':math.degrees(math.acos(surface.axis.z)),'SMA_panel_mm':2,'SMA_bore_mm':6.6,'rear_access_mm':13.2,'reference_antenna_length_mm':50.8,'reference_diameter_assumed_mm':7},'OLED':{'lower_opening_mm':[14.4,25],'upper_opening_mm':[18.4,29],'full_display_view_angle_deg_estimate':12},'parts':out,'known_fit_limits':['Preserved GPS receiver overlaps conservative rectangular OLED cover proxy approximately0.0845mm inY and0.3mm inZ; check actual hardware without forcing.','Actual GPS accessory revision differs between official drawing and STEP.','Physical clip flex, harness route and RF performance remain unvalidated.'],'feature_warnings':[]}
 for i in range(d.timeline.count):
  t=d.timeline.item(i)
  if t.errorOrWarningMessage:audit['feature_warnings'].append({'name':t.name,'message':t.errorOrWarningMessage})
 (folder/'model-audit.json').write_text(json.dumps(audit,indent=2)+'\n')
 for o in r.occurrences:
  if o.component.name.startswith(('R06 ','REF GPS accessory','REF Heltec')):o.isLightBulbOn=True
  if o.component.name.startswith('REF R06 '):o.isLightBulbOn=False
 cam=a.activeViewport.camera;cam.viewOrientation=adsk.core.ViewOrientations.IsoTopRightViewOrientation;cam.isFitView=True;a.activeViewport.camera=cam
 a.activeViewport.fit();a.activeViewport.saveAsImageFile(str(folder/'assembled-preview.png'),1600,1200)
 assert d.exportManager.execute(d.exportManager.createFusionArchiveExportOptions(str(folder/'GoKart-Heltec-Internal-Harness-R06.f3d')))
 print('Exported R06 native, three STEP, three millimetre STL, model audit and assembled preview.')
