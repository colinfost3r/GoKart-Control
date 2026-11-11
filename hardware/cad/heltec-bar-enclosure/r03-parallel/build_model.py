"""Fusion MCP construction script: R03 compact parallel prototype, mm. Run only in the named NEW design.
References are imported separately. Re-run into a fresh design, never overwrite an existing model.
"""
import adsk.core, adsk.fusion, math
V=adsk.core.ValueInput
P=adsk.core.Point3D
O=adsk.fusion.FeatureOperations
D=adsk.fusion.DimensionOrientations

def mm(v): return V.createByString(str(v)+' mm') if not isinstance(v,str) else V.createByString(v)
def pt(x,y,z=0): return P.create(x/10,y/10,z/10)
def coll(items):
    c=adsk.core.ObjectCollection.create()
    for i in items: c.add(i)
    return c

def plane(c,z,name='datum'):
    if z==0:return c.xYConstructionPlane
    i=c.constructionPlanes.createInput();i.setByOffset(c.xYConstructionPlane,mm(z))
    p=c.constructionPlanes.add(i);p.name=name;p.isLightBulbOn=False;return p

def sketch(c,z,name):
    s=c.sketches.add(plane(c,z,name+' datum'));s.name=name;return s

def rectangle(s,x,y,w,h,wx=None,hy=None):
    lines=s.sketchCurves.sketchLines.addTwoPointRectangle(pt(x-w/2,y-h/2),pt(x+w/2,y+h/2))
    lines.item(0).startSketchPoint.isFixed=True
    a=s.sketchDimensions.addDistanceDimension(lines.item(0).startSketchPoint,lines.item(0).endSketchPoint,D.HorizontalDimensionOrientation,pt(x,y-h/2-3))
    a.parameter.expression=wx or str(w)+' mm'
    a=s.sketchDimensions.addDistanceDimension(lines.item(1).startSketchPoint,lines.item(1).endSketchPoint,D.VerticalDimensionOrientation,pt(x+w/2+3,y))
    a.parameter.expression=hy or str(h)+' mm'
    return s.profiles.item(0)

def extrude(c,s,depth,op,name,profile=None):
    ps=profile or (s.profiles.item(0) if s.profiles.count==1 else coll(list(s.profiles)))
    i=c.features.extrudeFeatures.createInput(ps,op)
    i.setDistanceExtent(False,mm(depth))
    if op in (O.CutFeatureOperation,O.IntersectFeatureOperation):i.participantBodies=list(c.bRepBodies)
    f=c.features.extrudeFeatures.add(i);f.name=name;s.isLightBulbOn=False
    return f

def box(c,name,x,y,z,w,h,t,op=O.NewBodyFeatureOperation,wx=None,hy=None):
    s=sketch(c,z,name+' sketch');rectangle(s,x,y,w,h,wx,hy)
    return extrude(c,s,t,op,name)

def circles(c,name,xy,z,d,depth,op=O.CutFeatureOperation,dexpr=None):
    s=sketch(c,z,name+' sketch')
    for x,y in xy:
        q=s.sketchCurves.sketchCircles.addByCenterRadius(pt(x,y),d/20);q.centerSketchPoint.isFixed=True
        dm=s.sketchDimensions.addDiameterDimension(q,pt(x+d,y+d));dm.parameter.expression=dexpr or str(d)+' mm'
    return extrude(c,s,depth,op,name)

def hexholes(c,name,xy,z,af,depth):
    s=sketch(c,z,name+' sketch');r=af/math.sqrt(3)
    for x,y in xy:
        vs=[pt(x+r*math.cos(math.pi/6+k*math.pi/3),y+r*math.sin(math.pi/6+k*math.pi/3)) for k in range(6)]
        for k in range(6):s.sketchCurves.sketchLines.addByTwoPoints(vs[k],vs[(k+1)%6])
    return extrude(c,s,depth,O.CutFeatureOperation,name)

def vertical_fillet(c,body,r):
    es=[]
    for e in body.edges:
        a=e.startVertex.geometry;b=e.endVertex.geometry
        if abs(a.x-b.x)<1e-6 and abs(a.y-b.y)<1e-6 and abs(a.z-b.z)>0.1:es.append(e)
    i=c.features.filletFeatures.createInput();i.edgeSetInputs.addConstantRadiusEdgeSet(coll(es),mm(r),False)
    f=c.features.filletFeatures.add(i);f.name='Rounded vertical corners';return f

def bore_y(c,name,cy,cz,d,length):
    ny=c.xZConstructionPlane.geometry.normal.y
    i=c.constructionPlanes.createInput();i.setByOffset(c.xZConstructionPlane,mm(cy/ny));p=c.constructionPlanes.add(i)
    s=c.sketches.add(p);s.name=name+' sketch'
    q=s.sketchCurves.sketchCircles.addByCenterRadius(s.modelToSketchSpace(pt(0,cy,cz)),d/20);q.centerSketchPoint.isFixed=True
    dm=s.sketchDimensions.addDiameterDimension(q,pt(0,0));dm.parameter.expression='bar_diameter + clamp_fit'
    f=extrude(c,s,-length/ny,O.CutFeatureOperation,name);p.isLightBulbOn=False;return f

def bore_x(c,name,cx,cz,d,length):
    nx=c.yZConstructionPlane.geometry.normal.x
    i=c.constructionPlanes.createInput();i.setByOffset(c.yZConstructionPlane,mm(cx/nx));p=c.constructionPlanes.add(i)
    k=c.sketches.add(p);k.name=name+' sketch'
    q=k.sketchCurves.sketchCircles.addByCenterRadius(k.modelToSketchSpace(pt(cx,0,cz)),d/20);q.centerSketchPoint.isFixed=True
    k.sketchDimensions.addDiameterDimension(q,pt(0,0)).parameter.expression='bar_diameter + clamp_fit'
    f=extrude(c,k,-length/nx,O.CutFeatureOperation,name);p.isLightBulbOn=False;return f

def component(root,name):
    o=root.occurrences.addNewComponent(adsk.core.Matrix3D.create());o.component.name=name;return o.component

def polygon(s,cx,cy,r,n=8,angle=math.pi/8):
    vs=[pt(cx+r*math.cos(angle+2*math.pi*k/n),cy+r*math.sin(angle+2*math.pi*k/n)) for k in range(n)]
    for k in range(n):s.sketchCurves.sketchLines.addByTwoPoints(vs[k],vs[(k+1)%n])
    return s.profiles.item(0)

def run(_context: str):
    app=adsk.core.Application.get();des=adsk.fusion.Design.cast(app.activeProduct)
    assert app.activeDocument.name=='GoKart Heltec L76K Compact Parallel R03'
    root=des.rootComponent
    assert not any(o.component.name.startswith('C01') for o in root.occurrences)
    params=[
      ('bar_diameter','25.273 mm','mm','Owner: 0.995 inch horizontal bar'),
      ('clamp_fit','0.25 mm','mm','Prototype diametral clearance; fit test before full print'),
      ('split_gap','1.5 mm','mm','Clamp take-up; two M4 bolts'),
      ('case_length','66 mm','mm','Board-close footprint; USB plug outside'),
      ('case_width','36 mm','mm','PCB plus shell/diagonal screw bosses'),
      ('case_height','27.5 mm','mm','To lid underside; stacked GPS'),
      ('base_thickness','2.5 mm','mm','Plain ASA or PETG prototype'),
      ('wall','2 mm','mm','Prototype wall'),
      ('lid_thickness','2.5 mm','mm','Roof includes3.3mm GPS patch clearance'),
      ('sma_angle','15 deg','deg','Cant from up toward outboard+X'),
      ('sma_hole','6.6 mm','mm','Unverified actual bulkhead clearance'),
      ('sma_panel','2 mm','mm','Unverified available SMA thread/panel thickness'),
      ('m3_clear','3.4 mm','mm','Two case closure screws'),
      ('m4_clear','4.5 mm','mm','Two clamp screws'),
      ('board_top','8.5 mm','mm','PCB top; official components clear floor'),
      ('cover_top','14 mm','mm','PDF: PCBtop+5.5mm cover'),
      ('capture_clearance','0.3 mm','mm','Positive capture; no glass loading'),
      ('gps_bottom','17 mm','mm','3mm clear above Heltec cover'),
      ('gps_stack','7.2 mm','mm','Larger of differing official GPS sources'),
      ('gps_roof_gap','3.3 mm','mm','Patch to plain polymer roof'),
      ('gps_finger','0.8 mm','mm','Prototype snapbeam; fit check ASA/PETG'),
    ]
    for n,v,u,comment in params:des.userParameters.add(n,V.createByString(v),u,comment)
    # Exactly2M4 clamp screws and2M3 enclosure screws; stock SMA nut remains connector hardware.
    clamp_xy=[(0,-18.5),(0,18.5)]
    lid_xy=[(-29,-14),(29,14)]
    main=component(root,'C01 Compact case with upper collar')
    b=box(main,'Compact outer shell',0,0,0,66,36,'case_height',wx='case_length',hy='case_width').bodies.item(0)
    vertical_fillet(main,b,3)
    box(main,'Board cavity',0,0,'base_thickness',62,32,'case_height',O.CutFeatureOperation,'case_length - 2*wall','case_width - 2*wall')
    # Collar entirely under case footprint: bore axisY, split at Z=-17.
    box(main,'Integral upper collar',0,0,'-17 mm + split_gap/2',24,50,'17 mm - split_gap/2',O.JoinFeatureOperation)
    bore_x(main,'Bar seat parallel case length',12,-17,25.523,24)
    circles(main,'Two M4 clamp passages',clamp_xy,-34,4.5,34,dexpr='m4_clear')
    hexholes(main,'Side loaded M4 nut seats',clamp_xy,-2.6,7.3,-3.4)
    for sy in [-1,1]:box(main,'M4 nut insertion channel',0,sy*22,-6,7.5,8,3.4,O.CutFeatureOperation)
    circles(main,'Two diagonal lid bosses',lid_xy,2.5,7,25,O.JoinFeatureOperation)
    circles(main,'Two M3 lid clearances',lid_xy,2.5,3.4,28,dexpr='m3_clear')
    hexholes(main,'M3 captive nuts',lid_xy,27.5,5.8,-2.7)
    # PCB supports at existing OLED hole grid; retainers do not enlarge any board hole.
    holes_x=[-20.0345,8.9655]
    circles(main,'Four PCB pads',[(x,y) for x in holes_x for y in [-7,7]],2.5,4.5,4.4413,O.JoinFeatureOperation)
    for x in [-26.6,26.6]:
      for y in [-8,8]:box(main,'Low PCB end stop',x,y,2.5,0.9,3,6.8,O.JoinFeatureOperation)
    for y in [-13.4,13.4]:
      for x in [-8,15]:box(main,'Low PCB side stop',x,y,2.5,5,0.8,6.8,O.JoinFeatureOperation)
    # USB enters from outside:13x7.5mm opening; no internal plug reserve.
    box(main,'USB C outside plug access',33,0,7,6,13,7.5,O.CutFeatureOperation)
    # Antenna flange supports leave open centre for coax; integral with side walls.
    for y in [-12,12]:box(main,'Captured SMA flange ledge',21,y,25.5,14,9,2,O.JoinFeatureOperation)
    cap=component(root,'C02 Lower collar two bolts')
    cb=box(cap,'Lower clamp',0,0,-34,24,50,'17 mm - split_gap/2').bodies.item(0)
    vertical_fillet(cap,cb,2.5)
    bore_x(cap,'Matching parallel bar seat',12,-17,25.523,24)
    circles(cap,'Two M4 bolt holes',clamp_xy,-34,4.5,20,dexpr='m4_clear')
    circles(cap,'Recessed socket heads',clamp_xy,-34,8,2)
    lid=component(root,'C03 Lid with molded board and GPS retention')
    lb=box(lid,'Two screw lid',0,0,'case_height',66,36,'lid_thickness',wx='case_length',hy='case_width').bodies.item(0)
    vertical_fillet(lid,lb,3)
    circles(lid,'Two M3 lid holes',lid_xy,27.5,3.4,3,dexpr='m3_clear')
    # Two stops touch plastic OLED end-frame region, two touch clear rear PCB edge.
    circles(lid,'Front protective-frame capture',[(8.9655,y) for y in [-7,7]],14.3,3,13.2,O.JoinFeatureOperation)
    circles(lid,'Rear PCB edge capture',[(-24,y) for y in [-7,7]],8.8,2.6,18.7,O.JoinFeatureOperation)
    # GPS is held under the lid by two flexible snap fingers and corner guides.
    # Only plain polymer over patch;3.3mm nominal sky-side gap. Dimension mismatch remains a fit check.
    for x in [-23.5,-2.5]:
      for y in [-9.75,9.75]:box(lid,'GPS corner locator',x,y,17,2,2,10.5,O.JoinFeatureOperation)
    # Actual alternate-STEP PCB underside20.6; hooks at clearY edge strips, not under IC/connector.
    for y in [-9,9]:
      box(lid,'GPS edge snap beam',-13,y,19.9,4,0.8,7.8,O.JoinFeatureOperation)
    for y in [-8.4,8.4]:
      box(lid,'GPS PCB underside hook',-13,y,19.9,4,2.0,0.7,O.JoinFeatureOperation)
    # Stops over PCB rim of the alternate STEP, clear of15x15ceramic; actual accessoryfit still unverified.
    for x in [-21.5,-4.5]:
      for y in [-7,7]:circles(lid,'GPS rim capture clear ceramic',[(x,y)],22.5,1.0,5.2,O.JoinFeatureOperation)
    # Octagonal recess captures flange:45degree indexed yaw, no extra screws.
    s=sketch(lid,27.5,'Octagonal SMA capture recess');polygon(s,21,0,11.0)
    extrude(lid,s,1.4,O.CutFeatureOperation,'Recess for index flange')
    circles(lid,'SMA insert neck opening',[(21,0)],27.5,16.4,4)
    alpha=des.userParameters.itemByName('sma_angle').value
    panel=des.userParameters.itemByName('sma_panel').value*10
    wedge=component(root,'C04 Captured 15deg antenna insert')
    s=sketch(wedge,27.5,'Octagonal eight way flange');polygon(s,21,0,10.8)
    extrude(wedge,s,1.2,O.NewBodyFeatureOperation,'Captured flange')
    circles(wedge,'Protected antenna boss',[(21,0)],28.7,16,15,O.JoinFeatureOperation)
    axis=sketch(wedge,0,'Outward cant axis');ln=axis.sketchCurves.sketchLines.addByTwoPoints(pt(21,-12),pt(21,12));ln.isConstruction=True
    pi=wedge.constructionPlanes.createInput();pi.setByAngle(ln,V.createByString('sma_angle'),wedge.xYConstructionPlane)
    tilt=wedge.constructionPlanes.add(pi);tilt.name='Parameterized antenna cant'
    pi=wedge.constructionPlanes.createInput();pi.setByOffset(tilt,V.createByString('37 mm*cos(sma_angle)'))
    face=wedge.constructionPlanes.add(pi);face.name='Antenna bulkhead face'
    s=wedge.sketches.add(face);cp=s.modelToSketchSpace(pt(21,0,37));rectangle(s,cp.x*10,cp.y*10,60,60)
    extrude(wedge,s,45,O.CutFeatureOperation,'Canted boss top')
    s=wedge.sketches.add(face);cp=s.modelToSketchSpace(pt(22.5,0,37-1.5*math.tan(alpha)))
    q=s.sketchCurves.sketchCircles.addByCenterRadius(cp,0.33);q.centerSketchPoint.isFixed=True
    s.sketchDimensions.addDiameterDimension(q,pt(0,0)).parameter.expression='sma_hole'
    extrude(wedge,s,-25,O.CutFeatureOperation,'SMA clearance hole')
    pi=wedge.constructionPlanes.createInput();pi.setByOffset(face,V.createByString('-sma_panel'))
    rear=wedge.constructionPlanes.add(pi)
    s=wedge.sketches.add(rear);cp=s.modelToSketchSpace(pt(22.5-panel*math.sin(alpha),0,37-1.5*math.tan(alpha)-panel*math.cos(alpha)))
    q=s.sketchCurves.sketchCircles.addByCenterRadius(cp,0.55);q.centerSketchPoint.isFixed=True
    extrude(wedge,s,-25,O.CutFeatureOperation,'SMA rear nut access')
    for p in [tilt,face,rear]:p.isLightBulbOn=False
    axis.isLightBulbOn=False
    # Position manufacturer references in actual mounting pose; photo has no soldered headers.
    board=next(o for o in root.occurrences if o.component.name=='REF Heltec V4.3.1 official STEP')
    m=adsk.core.Matrix3D.create();m.setToRotation(3*math.pi/2,adsk.core.Vector3D.create(0,0,1),pt(0,0))
    m.translation=adsk.core.Vector3D.create(0,2.45745,0.85);board.isGroundToParent=False;board.transform2=m;board.isLightBulbOn=True
    if des.snapshots.hasPendingSnapshot:des.snapshots.add()
    pcb=board.component.occurrences.item(0).component
    for oc in pcb.occurrences:
      if oc.name.startswith(('JP4:','JP5:')):oc.isLightBulbOn=False
    gpsref=next(o for o in root.occurrences if o.component.name=='REF GPS accessory alternate revision');gm=adsk.core.Matrix3D.create()
    gm.setWithArray([-1,0,0,0,0,0,1,-1.3,0,1,0,2.22,0,0,0,1])
    gpsref.isGroundToParent=False;gpsref.transform2=gm;gpsref.isLightBulbOn=True
    if des.snapshots.hasPendingSnapshot:des.snapshots.add()
    oled=component(root,'REF OLED protective cover missing from STEP');box(oled,'Cover envelope',-5.5345,0,8.5,33,18.6,5.5)
    gps=component(root,'REF GPS conservative stack envelope');box(gps,'GPS envelope patch upward',-13,0,17,18.3,16.5,7.2)
    next(o for o in root.occurrences if o.component==gps).isLightBulbOn=False
    bar=component(root,'REF Horizontal 25.273mm kart bar')
    s=bar.sketches.add(bar.xZConstructionPlane);q=s.sketchCurves.sketchCircles.addByCenterRadius(s.modelToSketchSpace(pt(0,0,-17)),25.273/20)
    extrude(bar,s,60,O.NewBodyFeatureOperation,'Reference bar')
    # Case long axis now parallel globalY tube. Collar was rebuilt along localX.
    for oc in root.occurrences:
      if oc.component.name.startswith(('C01','C02','C03','REF OLED','REF GPS conservative')):
        rot=adsk.core.Matrix3D.create();rot.setToRotation(math.pi/2,adsk.core.Vector3D.create(0,0,1),pt(0,0))
        oc.isGroundToParent=False;oc.transform2=rot
      if oc.component.name.startswith('C04'):
        # A90degree index adjustment cancels case rotation: cant remains global+X.
        rot=adsk.core.Matrix3D.create();rot.translation=adsk.core.Vector3D.create(-2.1,2.1,0)
        oc.isGroundToParent=False;oc.transform2=rot
      if oc.component.name.startswith('REF Horizontal'):
        rot=adsk.core.Matrix3D.create();rot.translation=adsk.core.Vector3D.create(0,-3,0)
        oc.isGroundToParent=False;oc.transform2=rot
    if des.snapshots.hasPendingSnapshot:des.snapshots.add()
    antenna=component(root,'REF 2inch antenna envelope diameter7mm assumed')
    ax=sketch(antenna,0,'Antenna axis reference')
    ln=ax.sketchCurves.sketchLines.addByTwoPoints(pt(21,-12),pt(21,12));ln.isConstruction=True
    pi=antenna.constructionPlanes.createInput();pi.setByAngle(ln,V.createByString('sma_angle'),antenna.xYConstructionPlane)
    ap=antenna.constructionPlanes.add(pi)
    pi=antenna.constructionPlanes.createInput();pi.setByOffset(ap,V.createByString('37 mm*cos(sma_angle)'))
    af=antenna.constructionPlanes.add(pi)
    sk=antenna.sketches.add(af);q=sk.sketchCurves.sketchCircles.addByCenterRadius(sk.modelToSketchSpace(pt(22.5,0,37-1.5*math.tan(alpha))),0.35)
    extrude(antenna,sk,50.8,O.NewBodyFeatureOperation,'Nonprinted2inchantenna')
    for pl in [ap,af]:pl.isLightBulbOn=False
    ax.isLightBulbOn=False
    ao=next(o for o in root.occurrences if o.component==antenna)
    am=adsk.core.Matrix3D.create();am.translation=adsk.core.Vector3D.create(-2.1,2.1,0)
    ao.isGroundToParent=False;ao.transform2=am
    if des.snapshots.hasPendingSnapshot:des.snapshots.add()
    des.computeAll();des.activateRootComponent();app.activeViewport.fit()
    assert abs(board.transform2.translation.z-0.85)<1e-7,'Heltec pose changed'
    assert abs(gpsref.transform2.translation.z-2.22)<1e-7,'GPS pose changed'
    print('Compact66x36x30mm main case parallel tube;50mm collarwidth; four printed parts;4installation screws total.')
    print('Overall height includes collar and raised antenna insert; reference bar not printed.')
    for o in root.occurrences:
      if o.component.name.startswith('C0'):print(o.component.name,'bodies',o.component.bRepBodies.count,[b.isSolid for b in o.component.bRepBodies])
