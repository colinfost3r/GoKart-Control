#!/usr/bin/env python3
"""Render the production Core2 C++ views into a self-contained offline browser rehearsal.

No device ports, Wi-Fi, ESP-NOW, VESC connection or course provisioning. The small
browser interaction layer selects pre-rendered scenes; native touch logic is tested
separately. Text uses browser monospace metrics, not the LCD bitmap font's exact glyphs.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
SCENES = ('startup', 'invite', 'invitation', 'joined', 'download', 'ready', 'used', 'download-error',
          'host-lost', 'gps-lost', 'link-lost', 'no-course', 'fault', 'stopped', 'slow', 'live')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-scenes', action='store_true', help='Also write all individual SVG scenes')
    parser.add_argument('--out', type=Path, required=True, help='Output directory for HTML and SVG scenes')
    args = parser.parse_args()
    compiler = shutil.which('c++')
    candidates = [Path(os.environ.get('ARDUINOJSON_DIR', '/missing')),
                  Path('/private/tmp/gokart-arduino/user/libraries/ArduinoJson/src'),
                  Path.home() / 'Arduino/libraries/ArduinoJson/src']
    include = next((p for p in candidates if (p/'ArduinoJson.h').exists()), None)
    if not compiler or not include:
        parser.error('C++ compiler and ArduinoJson headers required (set ARDUINOJSON_DIR)')
    args.out.mkdir(parents=True, exist_ok=True)
    frames = {}
    with tempfile.TemporaryDirectory(prefix='gokart-preview-') as tmp:
        exe = Path(tmp)/'render'
        subprocess.run([compiler, '-std=c++17', '-Wall', '-Wextra', '-Werror',
                        '-I'+str(include), '-I'+str(ROOT/'firmware/m5-core2'),
                        '-I'+str(ROOT/'firmware/libraries/M5DisplayLink'),
                        str(ROOT/'firmware/m5-core2/tests/render_driver.cpp'), '-o', str(exe)], check=True)
        for scene in SCENES:
            for page in ('map', 'dash'):
                svg = subprocess.check_output([str(exe), scene, page])
                if args.write_scenes or (scene, page) in [('ready', 'map'), ('ready', 'dash'), ('invitation', 'map')]:
                    (args.out/f'{scene}-{page}.svg').write_bytes(svg)
                frames[scene+'-'+page] = 'data:image/svg+xml;base64,'+base64.b64encode(svg).decode()
    html = '''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>GoKart / Core2 rehearsal</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#111e28;color:#edf4f8;font:16px system-ui,sans-serif}
main{max-width:1100px;margin:40px auto;padding:24px}h1{font-size:30px;font-weight:500;margin:12px 0}
.eyebrow{color:#f7ce79;letter-spacing:.15em;font-size:12px}p{color:#bbcbd5;line-height:1.5;max-width:760px}
.workbench{display:grid;grid-template-columns:minmax(320px,640px) 1fr;gap:28px;margin-top:28px}
#screen{width:100%;aspect-ratio:4/3;display:block;border-radius:8px;border:1px solid #748c9c;cursor:pointer}
label{display:block;margin-bottom:8px;color:#bbcbd5}select,button{padding:12px;background:#293744;color:#edf4f8;border:1px solid #748c9c;border-radius:7px;font:inherit}
select{width:100%}.buttons{display:flex;gap:8px;margin:14px 0}button{cursor:pointer}button.active{border-color:#a4e5ee;color:#a4e5ee}
#result{border-left:2px solid #f7ce79;padding-left:12px;min-height:100px;font-size:14px}
[hidden]{display:none!important}small{color:#bbcbd5;line-height:1.5;display:block;margin-top:20px}a{color:#a4e5ee}
@media(max-width:800px){main{margin:8px auto;padding:16px}.workbench{grid-template-columns:1fr}}
</style><main><div class="eyebrow">M5 V1.5 / OFFLINE DESIGN REHEARSAL</div>
<h1>Your course, in context.</h1><p>Hunter’s instrument style with the Pi’s existing South Norwalk map data. Roads and building outlines are real; the loop, start/finish, boost pad, pickup and kart positions are simulated.</p>
<div class="workbench"><div><img id="screen" alt="Core2 native view preview" draggable="false"><small>320 × 240 layout from the production C++ renderer. Browser text approximates the LCD bitmap font. All inputs here are simulated—even the LIVE appearance scenario. The five-second startup screen is the only attribution screen.</small></div>
<aside><label for="scene">Test scenario</label><select id="scene"></select><div class="buttons"><button id="dash">DASH</button><button id="map">MAP</button></div><p id="result" role="status" aria-live="polite">Checkered gate: start/finish. Green arrows: boost pad. Gold ?: item pickup. Gold 3: your kart; blue numbers: other karts. Top left: GPS speed in MPH and measured pack voltage from the Heltec. Hold the page button for 1.8 seconds on live hardware to open updates.</p><small>No hardware connection. No radio packets. No motor output. Real host publishing, course transfer, inventory and game commands are still separate work.</small><small id="startupCredits">Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> / ODbL.</small></aside></div></main>
<script>
const frames=FRAMES_JSON;const scenes=SCENES_JSON;let scene='startup',page='map',returnScene='invite',timer;
const screen=document.getElementById('screen'),select=document.getElementById('scene'),result=document.getElementById('result');
for(const s of scenes){const o=document.createElement('option');o.value=s;o.textContent=s.replaceAll('-',' ').toUpperCase();select.append(o)}
function render(){document.getElementById('startupCredits').hidden=scene!=='startup';screen.src=frames[scene+'-'+page];select.value=scene;for(const p of ['dash','map'])document.getElementById(p).classList.toggle('active',p===page)}
function choose(s,message){clearTimeout(timer);scene=s;if(message)result.textContent=message;render()}
select.onchange=()=>choose(select.value,'Scenario selected. This changes the preview only.');
for(const p of ['dash','map'])document.getElementById(p).onclick=()=>{page=p;render()};
screen.onclick=e=>{let r=screen.getBoundingClientRect(),x=(e.clientX-r.left)*320/r.width,y=(e.clientY-r.top)*240/r.height;
 const inside=(a,b,w,h)=>x>=a&&x<a+w&&y>=b&&y<b+h;
 if(scene==='startup')return;
 const modal=['invitation','joined','download','download-error'].includes(scene);
 if(modal){if(inside(20,145,132,36)){choose(returnScene,'Invitation closed; no command sent.');return}
  if(inside(168,145,132,36)&&scene==='joined'){choose('invite','Left the simulated game. No command sent.');return}
  if(inside(168,145,132,36)&&scene!=='download'){choose('download','Simulated transfer: a real transfer will verify the package before joining.');timer=setTimeout(()=>choose('ready','Simulated join complete. Open MAP and press FIRE to try item feedback.'),3000)}return}
 if(inside(268,4,48,40)){page=page==='map'?'dash':'map';render();return}
 if(inside(222,4,42,40)&&!['host-lost','link-lost','live'].includes(scene)){returnScene=scene;choose(['ready','used'].includes(scene)?'joined':'invitation','Game menu is simulated. No session request has been sent.');return}
 if(page==='map'&&inside(258,180,58,56)){if(scene==='ready')choose('used','Simulated shell consumed once. No attack packet or VESC command was sent.');else result.textContent='FIRE unavailable in this scenario.';return}
 if(page==='dash'&&y>=202)result.textContent='Mode controls are disabled in the rehearsal. Installed live firmware retains guarded hold-to-select behavior.';
};render();timer=setTimeout(()=>choose('ready'),5000);
</script>'''
    html = html.replace('FRAMES_JSON', json.dumps(frames)).replace('SCENES_JSON', json.dumps(SCENES))
    (args.out/'index.html').write_text(html)
    print(json.dumps({'preview': str((args.out/'index.html').resolve()), 'scenes': len(frames), 'no_device_opened': True}))


if __name__ == '__main__':
    main()
