"""Save an assembled view and a steep open-case view of the floor-connected ribs."""
import adsk.core, adsk.fusion, pathlib

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec FDM Supports R07';folder=pathlib.Path(__file__).resolve().parent
 saved=[(o,o.isLightBulbOn,o.component.opacity) for o in r.occurrences]
 for o in r.occurrences:
  if o.component.name.startswith('REF '):o.isLightBulbOn=False
  if o.component.name in ['R07 OLED and antenna lid','R07 Outboard lower collar']:o.isLightBulbOn=False
 case=next(o for o in r.occurrences if o.component.name=='R07 Case with floor-backed GPS supports');case.isLightBulbOn=True;case.component.opacity=1
 cam=a.activeViewport.camera;cam.eye=adsk.core.Point3D.create(4,-7,40);cam.target=adsk.core.Point3D.create(0,-1.5,1.3)
 direction=cam.eye.vectorTo(cam.target);direction.normalize();right=direction.crossProduct(adsk.core.Vector3D.create(0,1,0));right.normalize();up=right.crossProduct(direction);up.normalize();cam.upVector=up;cam.isFitView=True;cam.isSmoothTransition=False;a.activeViewport.camera=cam
 a.activeViewport.fit();a.activeViewport.saveAsImageFile(str(folder/'open-case-supports-preview.png'),1600,1200)
 for o,visible,opacity in saved:o.isLightBulbOn=visible;o.component.opacity=opacity
 for o in r.occurrences:
  if o.component.name.startswith('R07 '):o.isLightBulbOn=True;o.component.opacity=1
  if o.component.name.startswith(('REF Heltec','REF GPS accessory','REF 2inch','REF OLED')):o.isLightBulbOn=True
  if o.component.name.startswith(('REF R06 ','REF R07 ')):o.isLightBulbOn=False
 cam=a.activeViewport.camera;cam.viewOrientation=adsk.core.ViewOrientations.IsoTopRightViewOrientation;cam.isFitView=True;a.activeViewport.camera=cam
 a.activeViewport.fit();a.activeViewport.saveAsImageFile(str(folder/'assembled-preview.png'),1600,1200)
 print('Open-case ribs and assembled previews saved; final assembled view restored. No hardware positions changed.')
