#!/usr/bin/env python3
"""Pair a read-only Heltec and Core2 via explicit USB ports; never sends VESC commands.
Requires pyserial. Pairing keys stay in an ignored private directory and board NVS.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import time
import serial
from serial.tools import list_ports

ROOT=Path(__file__).resolve().parents[2]

def connect(port):
    s=serial.Serial(); s.port=port; s.baudrate=115200; s.timeout=.2
    s.dtr=False; s.rts=False; s.open()
    return s

def request(s, command, kind, seconds=5):
    s.reset_input_buffer(); s.write((command+'\n').encode()); s.flush()
    deadline=time.monotonic()+seconds; resend=time.monotonic()+1
    while time.monotonic()<deadline:
        if command in ('status','espnow status') and time.monotonic()>=resend:
            s.write((command+'\n').encode());s.flush();resend=time.monotonic()+1
        line=s.readline()
        try: obj=json.loads(line)
        except (ValueError,UnicodeError): continue
        if obj.get('t')==kind: return obj
    raise TimeoutError('No expected USB response; check firmware and selected port')

def usb_identity(port):
    match=[p for p in list_ports.comports() if p.device==port]
    return match[0].serial_number if len(match)==1 else None

def after_reboot(port, usb_serial, expected_mac):
    deadline=time.monotonic()+35
    while time.monotonic()<deadline:
        candidates=[p.device for p in list_ports.comports() if usb_serial and p.serial_number==usb_serial]
        actual=candidates[0] if len(candidates)==1 else port
        try:
            with connect(actual) as s:
                obj=request(s,'espnow status','espnow',7)
                if obj.get('mac')!=expected_mac: raise RuntimeError('Unexpected USB board after reboot')
                return obj
        except (serial.SerialException,OSError):
            time.sleep(.5)
    raise RuntimeError('USB board did not return after reboot; private pairing record retained')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core2-port',required=True)
    parser.add_argument('--heltec-port',required=True)
    parser.add_argument('--kart-id',type=int,required=True,choices=range(1,9))
    args=parser.parse_args()
    if args.core2_port==args.heltec_port: parser.error('Select two distinct ports')
    folder=ROOT/'firmware/build/bench-private'/datetime.now(timezone.utc).strftime('espnow-pair-%Y%m%dT%H%M%SZ')
    core_identity=usb_identity(args.core2_port);heltec_identity=usb_identity(args.heltec_port)
    with connect(args.core2_port) as core,connect(args.heltec_port) as heltec:
        cs=request(core,'status','m5_status'); hs=request(heltec,'status','status')
        if cs.get('transport')!='espnow' or hs.get('writes') is not False or hs.get('kart')!=args.kart_id:
            raise RuntimeError('Require Core2 ESP-NOW firmware and intended read-only Heltec kart ID')
        cm=request(core,'espnow status','espnow'); hm=request(heltec,'espnow status','espnow')
        if cm['mac']==hm['mac']: raise RuntimeError('Duplicate board identity')
        if cm.get('configured') or hm.get('configured'):
            raise RuntimeError('Existing pairing found; preserve it and explicitly clear both over USB before replacing')
        folder.mkdir(parents=True,exist_ok=False,mode=0o700);os.chmod(folder,0o700)
        lmk=secrets.token_hex(16);pmk=secrets.token_hex(16)
        record={'created_utc':datetime.now(timezone.utc).isoformat(),'kart_id':args.kart_id,
                'core2_mac':cm['mac'],'heltec_mac':hm['mac'],'lmk':lmk,'pmk':pmk}
        keyfile=folder/'pairing-private.json'
        fd=os.open(keyfile,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'w') as out: json.dump(record,out,indent=2);out.write('\n')
        # Preserve generated keys BEFORE either NVS mutation so a partial setup is recoverable.
        for s,peer in [(core,hm['mac']),(heltec,cm['mac'])]:
            result=request(s,f'espnow pair {peer} {lmk} {pmk}','espnow_config')
            if result.get('stored') is not True: raise RuntimeError('Pairing save failed; retain private record for recovery')
        for s in (core,heltec): s.write(b'reboot\n');s.flush()
    # Native USB may re-enumerate after ESP.restart; never reuse the pre-reset handles.
    time.sleep(1)
    cm=after_reboot(args.core2_port,core_identity,record['core2_mac'])
    hm=after_reboot(args.heltec_port,heltec_identity,record['heltec_mac'])
    if not (cm.get('configured') and hm.get('configured') and cm.get('peer')==record['heltec_mac'] and hm.get('peer')==record['core2_mac']):
        raise RuntimeError('Pairing readback failed; retain private record for recovery')
    print('Pair stored and read back on both boards; keys were not printed.')
    print('Private recovery record:',keyfile)
    print(json.dumps({'kart_id':args.kart_id,'core2':cm,'heltec':hm},indent=2))

if __name__=='__main__': main()
