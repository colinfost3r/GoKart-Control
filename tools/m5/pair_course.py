#!/usr/bin/env python3
"""Provision separate course-only ESP-NOW trust. Never changes the kart-control pairing or VESC.
Default: create a private plan only. --apply uses two explicitly selected USB ports, verifies MACs,
saves course peer NVS, and leaves reboot to the operator while stationary. Stop the host Pi serial
service before temporarily connecting its Heltec to this computer. Do not share the private plan.
"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets
import time

ROOT=Path(__file__).resolve().parents[2]

def mac(value):
    value=value.lower()
    if not re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',value) or int(value[:2],16)&1 or value=='00:00:00:00:00:00':
        raise argparse.ArgumentTypeError('expected unicast Wi-Fi station MAC')
    return value

def exchange(port,command,kinds):
    port.reset_input_buffer();port.write((command+'\n').encode());port.flush();out={};deadline=time.monotonic()+5
    while time.monotonic()<deadline:
        try:obj=json.loads(port.readline())
        except (ValueError,UnicodeError):continue
        if obj.get('t') in kinds:out[obj['t']]=obj
        if all(k in out for k in kinds):return out
    raise RuntimeError('Expected course firmware reply not received; no automatic retry')

def connect(name):
    import serial
    p=serial.Serial();p.port=name;p.baudrate=115200;p.timeout=.2;p.dtr=False;p.rts=False;p.open();return p

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host-id',required=True,type=int,choices=range(1,9));p.add_argument('--kart-id',required=True,type=int,choices=range(1,9))
    p.add_argument('--host-mac',required=True,type=mac);p.add_argument('--core2-mac',required=True,type=mac)
    p.add_argument('--plan',type=Path,required=True,help='private JSON file, outside tracked files (e.g. firmware/build/bench-private/course-2-3.json)')
    p.add_argument('--apply',action='store_true');p.add_argument('--host-port');p.add_argument('--core2-port')
    a=p.parse_args()
    if a.host_id==a.kart_id or a.host_mac==a.core2_mac:p.error('host and player must be distinct')
    if a.apply and (not a.host_port or not a.core2_port or a.host_port==a.core2_port):p.error('--apply requires distinct explicit host/core2 USB ports')
    expected={'host_id':a.host_id,'kart_id':a.kart_id,'host_mac':a.host_mac,'core2_mac':a.core2_mac}
    existing_plan=a.plan.exists()
    if existing_plan:
        if a.plan.stat().st_mode&0o077:raise RuntimeError('Private plan must have permissions 0600')
        plan=json.loads(a.plan.read_text())
        if any(plan.get(k)!=v for k,v in expected.items()) or not re.fullmatch('[0-9a-f]{64}',plan.get('key','')):raise RuntimeError('Existing plan identity mismatch')
    else:
        plan=dict(expected,key=secrets.token_hex(32));a.plan.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        fd=os.open(a.plan,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as f:json.dump(plan,f,indent=2);f.write('\n')
    if not a.apply:
        print(json.dumps({'plan':str(a.plan.resolve()),'no_device_opened':True,'next':'rerun with --apply and explicit ports while stationary'}));return
    with connect(a.core2_port) as core,connect(a.host_port) as host:
        states=[]
        for port,expected_mac,publisher in ((core,a.core2_mac,False),(host,a.host_mac,True)):
            status=exchange(port,'share status',('share_radio','share'))
            if status['share_radio'].get('mac')!=expected_mac or status['share'].get('publisher') is not publisher:raise RuntimeError('Wrong board/firmware; no pairing written')
            states.append(status)
        if not existing_plan and (a.host_id in states[0]['share'].get('configured',[]) or a.kart_id in states[1]['share'].get('configured',[])):
            raise RuntimeError('Course pairing exists; use its original private plan to preserve the key')
        hs=exchange(host,'status',('status',))['status']
        if hs.get('kart')!=a.host_id:raise RuntimeError('Host kart ID mismatch; no pairing written')
        cs=exchange(core,'status',('m5_status',))['m5_status']
        if cs.get('kart')!=a.kart_id:raise RuntimeError('Power the paired player Heltec so Core2 can confirm its kart ID; no pairing written')
        if states[0]['share_radio']['channel']!=states[1]['share_radio']['channel']:raise RuntimeError('Wi-Fi channels differ; align the maintenance networks first; no pairing written')
        for port,peer_id,peer_mac in ((core,a.host_id,a.host_mac),(host,a.kart_id,a.core2_mac)):
            reply=exchange(port,f'share pair {peer_id} {peer_mac} {plan["key"]}',('share',))['share']
            if reply.get('action')!='pair' or reply.get('ok') is not True:raise RuntimeError('Pairing incomplete; private plan retained; inspect both boards before retrying')
    print(json.dumps({'paired_host':a.host_id,'player':a.kart_id,'restart_required':True,'vehicle_pairing_unchanged':True,'plan':str(a.plan.resolve())}))

if __name__=='__main__':main()
