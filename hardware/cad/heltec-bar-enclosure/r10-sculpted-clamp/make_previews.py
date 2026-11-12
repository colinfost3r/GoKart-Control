"""Show top socket heads, underside nut traps and a view-only separated bottom clamp."""
import adsk.core, adsk.fusion, pathlib, json


def run(_context: str):
    a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    assert a.activeDocument.name=='GoKart Heltec Sculpted Clamp R10'
    folder=pathlib.Path(__file__).resolve().parent;timeline=d.timeline.count
    saved=[(o,o.isLightBulbOn,o.component.opacity,list(o.transform2.asArray())) for o in r.occurrences]
    case=next(o for o in r.occurrences if o.component.name=='R10 Sculpted upper clamp and owner case')
    lower=next(o for o in r.occurrences if o.component.name=='R10 Sculpted lower clamp')
    nuts=next(o for o in r.occurrences if o.component.name=='REF R10 bottom plain M4 nuts nominal')
    screws=next(o for o in r.occurrences if o.component.name=='REF R10 M4x30 top socket screws nominal')
    def capture(name):
        a.activeViewport.fit();assert a.activeViewport.saveAsImageFile(str(folder/name),1600,1200)
    def front_camera():
        cam=a.activeViewport.camera;cam.eye=adsk.core.Point3D.create(3,-24,14);cam.target=adsk.core.Point3D.create(0,-.65,.7)
        direction=cam.eye.vectorTo(cam.target);direction.normalize();right=direction.crossProduct(adsk.core.Vector3D.create(0,0,1));right.normalize();up=right.crossProduct(direction);up.normalize();cam.upVector=up;cam.isFitView=True;cam.isSmoothTransition=False;a.activeViewport.camera=cam
    for o in r.occurrences:o.isLightBulbOn=False
    lower.isLightBulbOn=True;lower.component.opacity=1
    cam=a.activeViewport.camera;cam.viewOrientation=adsk.core.ViewOrientations.IsoBottomLeftViewOrientation;cam.isFitView=True;cam.isSmoothTransition=False;a.activeViewport.camera=cam
    capture('bottom-nut-pockets-preview.png')
    nuts.isLightBulbOn=True;capture('bottom-nuts-installed-preview.png')
    lower.isLightBulbOn=False;nuts.isLightBulbOn=False;case.isLightBulbOn=True;case.component.opacity=1
    capture('web-root-transitions-preview.png')
    for o,visible,opacity,pose in saved:o.isLightBulbOn=visible;o.component.opacity=opacity
    for o in r.occurrences:
        if o.component.name.startswith('R10 '):o.isLightBulbOn=True;o.component.opacity=1
        if o.component.name.startswith(('REF Heltec','REF GPS accessory','REF 2inch','REF OLED')):o.isLightBulbOn=True
        if o.component.name.startswith(('REF R06 ','REF R07 ','REF R08 ')):o.isLightBulbOn=False
    screws.isLightBulbOn=True;nuts.isLightBulbOn=True
    front_camera();capture('assembled-preview.png')
    # This is a visual separation only; restore exact transforms before native export.
    for o in [lower,nuts]:
        m=adsk.core.Matrix3D.create();m.setWithArray(o.transform2.asArray());m.setCell(2,3,m.getCell(2,3)-2);o.transform2=m
    front_camera();capture('separated-bottom-clamp-preview.png')
    for o,visible,opacity,pose in saved:
        if o.component.name in [lower.component.name,nuts.component.name]:
            m=adsk.core.Matrix3D.create();m.setWithArray(pose);o.transform2=m
    deltas=[]
    for o,visible,opacity,pose in saved:
        delta=max(abs(x-y) for x,y in zip(pose,o.transform2.asArray()));assert delta<1e-9
        if o.component.name in [lower.component.name,nuts.component.name]:deltas.append({'component':o.component.name,'max_matrix_delta_after_view':delta})
    assert d.timeline.count==timeline
    front_camera();a.activeViewport.fit()
    (folder/'preview-state-audit.json').write_text(json.dumps({'timeline_unchanged':timeline,'view_only_separation_mm':20,'transforms_restored':deltas},indent=2)+'\n')
    print('R10 top-head, bottom-nut, web and separated-clamp previews saved; assembled transforms restored exactly.')
