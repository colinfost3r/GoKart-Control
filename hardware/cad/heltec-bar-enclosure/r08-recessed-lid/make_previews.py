"""Show the preserved extended base, recessed sill and lower lid step."""
import adsk.core, adsk.fusion, pathlib


def run(_context: str):
    a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
    assert a.activeDocument.name=='GoKart Heltec Recessed Lid R08'
    folder=pathlib.Path(__file__).resolve().parent
    saved=[(o,o.isLightBulbOn,o.component.opacity) for o in r.occurrences]
    for o in r.occurrences:o.isLightBulbOn=False
    case=next(o for o in r.occurrences if o.component.name=='R08 Owner base and recessed sill')
    lid=next(o for o in r.occurrences if o.component.name=='R08 Stepped lid for number4 screws')
    case.isLightBulbOn=True;case.component.opacity=1
    cam=a.activeViewport.camera;cam.eye=adsk.core.Point3D.create(5,-9,32);cam.target=adsk.core.Point3D.create(0,-.65,1.2)
    direction=cam.eye.vectorTo(cam.target);direction.normalize();right=direction.crossProduct(adsk.core.Vector3D.create(0,1,0));right.normalize();up=right.crossProduct(direction);up.normalize();cam.upVector=up;cam.isFitView=True;cam.isSmoothTransition=False;a.activeViewport.camera=cam
    a.activeViewport.fit();assert a.activeViewport.saveAsImageFile(str(folder/'open-sill-preview.png'),1600,1200)
    case.isLightBulbOn=False;lid.isLightBulbOn=True;lid.component.opacity=1
    cam=a.activeViewport.camera;cam.viewOrientation=adsk.core.ViewOrientations.IsoBottomLeftViewOrientation;cam.isFitView=True;cam.isSmoothTransition=False;a.activeViewport.camera=cam
    a.activeViewport.fit();assert a.activeViewport.saveAsImageFile(str(folder/'lid-underside-preview.png'),1600,1200)
    for o,visible,opacity in saved:o.isLightBulbOn=visible;o.component.opacity=opacity
    for o in r.occurrences:
        if o.component.name.startswith('R08 '):o.isLightBulbOn=True;o.component.opacity=1
        if o.component.name.startswith(('REF Heltec','REF GPS accessory','REF 2inch','REF OLED')):o.isLightBulbOn=True
        if o.component.name.startswith(('REF R06 ','REF R07 ','REF R08 ')):o.isLightBulbOn=False
    cam=a.activeViewport.camera;cam.viewOrientation=adsk.core.ViewOrientations.IsoTopRightViewOrientation;cam.isFitView=True;cam.isSmoothTransition=False;a.activeViewport.camera=cam
    a.activeViewport.fit();assert a.activeViewport.saveAsImageFile(str(folder/'assembled-preview.png'),1600,1200)
    print('Three R08 previews saved; final assembled view restored.')
