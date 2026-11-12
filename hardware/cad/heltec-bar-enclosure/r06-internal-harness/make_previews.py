"""Show the internal route through a transparent case, then restore assembly state."""
import adsk.core, adsk.fusion, pathlib

def run(_context: str):
 a=adsk.core.Application.get();d=adsk.fusion.Design.cast(a.activeProduct);r=d.rootComponent
 assert a.activeDocument.name=='GoKart Heltec Internal Harness R06'
 folder=pathlib.Path(__file__).resolve().parent
 saved=[(o,o.isLightBulbOn,o.component.opacity) for o in r.occurrences]
 for o in r.occurrences:
  n=o.component.name
  if n.startswith('REF R06 '):
   o.isLightBulbOn=True;b=o.component.bRepBodies.item(0)
   name='R06 wire route orange' if 'internal wire' in n else 'R06 unmeasured plug blue'
   ap=d.appearances.itemByName(name) or d.appearances.addByCopy(b.appearance,name)
   color=adsk.core.Color.create(255,112,12,255) if 'wire' in name else adsk.core.Color.create(30,130,255,255)
   for prop in ap.appearanceProperties:
    if prop.objectType=='adsk::core::ColorProperty':adsk.core.ColorProperty.cast(prop).value=color
   b.appearance=ap
  elif n in ['R06 OLED and antenna lid','R06 Lower collar'] or n.startswith(('REF 2inch','REF Horizontal','REF OLED')):o.isLightBulbOn=False
  elif n=='R06 Case with internal GPS socket':o.component.opacity=.18
  elif n.startswith('REF Heltec'):o.isLightBulbOn=True;o.component.opacity=.20
  elif n.startswith('REF GPS accessory'):o.isLightBulbOn=True;o.component.opacity=.65
 cam=a.activeViewport.camera;cam.viewOrientation=adsk.core.ViewOrientations.IsoTopRightViewOrientation;cam.isFitView=True;a.activeViewport.camera=cam
 a.activeViewport.fit();a.activeViewport.saveAsImageFile(str(folder/'internal-route-preview.png'),1600,1200)
 for o,visible,opacity in saved:o.isLightBulbOn=visible;o.component.opacity=opacity
 a.activeViewport.fit();a.activeViewport.saveAsImageFile(str(folder/'assembled-preview.png'),1600,1200)
 print('Saved orange-route/blue-plug transparent-case preview; restored assembled visibility and opacity. Hardware poses untouched.')
