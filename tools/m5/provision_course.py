#!/usr/bin/env python3
"""Validate an M5 outline offline; with --port, provision only a Core2's course NVS.
No Heltec/VESC commands, firmware flashing, radio pairing or resets. POSIX USB only.
"""
import argparse
import binascii
import json
import math
import os
from pathlib import Path
import select
import struct
import termios
import time
import tty

MAX_JSON=8192
CHUNK=128

def prepare(document):
    if not isinstance(document,dict) or type(document.get('schema')) is not int or document['schema']!=1:
        raise ValueError('Require course schema 1')
    name=document.get('name');points=document.get('points');closed=document.get('closed',False)
    if not isinstance(name,str) or not 1<=len(name.encode('utf-8'))<=40 or any(ord(c)<32 or ord(c)==127 for c in name):
        raise ValueError('Course name must be 1..40 UTF-8 bytes without control characters')
    if type(closed) is not bool:raise ValueError('closed must be boolean')
    if not isinstance(points,list) or not 2<=len(points)<=128:raise ValueError('Require 2..128 points')
    quantized=[]
    for p in points:
        if not isinstance(p,list) or len(p)!=2 or any(type(x) not in (int,float) or not math.isfinite(x) for x in p):
            raise ValueError('Each point must contain two finite numbers')
        if not -90<=p[0]<=90 or not -180<=p[1]<=180:raise ValueError('Coordinate out of range')
        quantized.append(tuple(int(math.copysign(math.floor(abs(x)*1e7+.5),x)) for x in p))
    if len(set(quantized))<2:raise ValueError('Course needs two distinct points at 1e-7 degree precision')
    clean={'schema':1,'name':name,'closed':closed,'points':[[a/1e7,b/1e7] for a,b in quantized]}
    # Preserve seven decimal places: ArduinoJson can parse short decimals as float32.
    # Coordinate literals with the full e7 precision keep the board/tool CRC equal.
    header=json.dumps({k:clean[k] for k in ('schema','name','closed')},separators=(',',':'),ensure_ascii=False)
    point_text=','.join(f'[{a/1e7:.7f},{b/1e7:.7f}]' for a,b in quantized)
    payload=(header[:-1]+',"points":['+point_text+']}').encode('utf-8')
    if len(payload)>MAX_JSON:raise ValueError('Course exceeds upload size limit')
    title=name.encode('utf-8')
    record=struct.pack('>4sHBB40s',b'GKC1',len(points),closed,len(title),title)+b''.join(struct.pack('>ii',*p) for p in quantized)
    record_crc=binascii.crc32(record)&0xffffffff
    return clean,payload,f'{record_crc:08x}'

def commands(payload):
    if not 2<=len(payload)<=MAX_JSON:raise ValueError('Invalid payload size')
    yield 'begin',f'course begin {len(payload)} {binascii.crc32(payload)&0xffffffff:08x}'
    for offset in range(0,len(payload),CHUNK):yield 'chunk',f'course chunk {offset} {payload[offset:offset+CHUNK].hex()}'
    yield 'commit','course commit'

class Usb:
    def __init__(self,port):self.port=port;self.fd=None;self.old=None;self.buffer=b''
    def __enter__(self):
        try:
            self.fd=os.open(self.port,os.O_RDWR|os.O_NOCTTY|os.O_NONBLOCK)
            self.old=termios.tcgetattr(self.fd);tty.setraw(self.fd,termios.TCSANOW)
            cfg=termios.tcgetattr(self.fd);cfg[2]=(cfg[2]|termios.CLOCAL|termios.CREAD)&~termios.HUPCL
            cfg[4]=cfg[5]=termios.B115200;termios.tcsetattr(self.fd,termios.TCSANOW,cfg);return self
        except BaseException:self.__exit__();raise
    def __exit__(self,*unused):
        if self.fd is not None:
            try:
                if self.old is not None:self.old[2]&=~termios.HUPCL;termios.tcsetattr(self.fd,termios.TCSANOW,self.old)
            finally:os.close(self.fd);self.fd=None
    def request(self,line,kind,action=None):
        if '\n' in line or '\r' in line:raise ValueError('One command per line')
        data=(line+'\n').encode()
        if os.write(self.fd,data)!=len(data):raise IOError('Partial send; no retry or automatic cleanup')
        deadline=time.monotonic()+3;count=0
        while time.monotonic()<deadline:
            while b'\n' in self.buffer:
                raw,self.buffer=self.buffer.split(b'\n',1)
                try:result=json.loads(raw)
                except (ValueError,UnicodeError):continue
                if isinstance(result,dict) and result.get('t')==kind and (action is None or result.get('action')==action):return result
            ready,_,_=select.select([self.fd],[],[],min(.1,max(0,deadline-time.monotonic())))
            if not ready:continue
            data=os.read(self.fd,4096)
            if not data:raise IOError('USB closed')
            count+=len(data);self.buffer+=data
            if count>32768 or len(self.buffer)>16384:raise IOError('Unexpected USB output size')
        raise TimeoutError('No matching reply; no retry. A timed-out commit may have stored the course; inspect course status.')

def upload(connection,document,kart_id):
    if type(kart_id) is not int or not 1<=kart_id<=8:raise ValueError('Expected kart ID must be 1..8')
    clean,payload,crc=prepare(document)
    status=connection.request('status','m5_status')
    if status.get('fw')!='m5-v1.5' or status.get('transport') not in ('uart','espnow') or status.get('kart')!=kart_id or status.get('course_proto')!=1:
        raise ValueError('Require intended Core2 ID and course protocol1; no upload started')
    for action,line in commands(payload):
        result=connection.request(line,'course',action)
        if result.get('ok') is not True:raise RuntimeError('Course '+action+' refused: '+str(result.get('error')))
    final=connection.request('course status','course','status')
    if final.get('source')!='internal' or final.get('points')!=len(clean['points']) or final.get('name')!=clean['name'] or final.get('closed') is not clean['closed'] or final.get('record_crc32')!=crc:
        raise RuntimeError('Course readback differs; do not retry blindly')
    return final

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--course',required=True,type=Path);p.add_argument('--port');p.add_argument('--kart-id',type=int,choices=range(1,9));a=p.parse_args()
    try:
        document=json.loads(a.course.read_text());clean,payload,crc=prepare(document)
        if a.port:
            if a.kart_id is None:p.error('--kart-id is required with --port')
            with Usb(a.port) as c:result=upload(c,document,a.kart_id)
            print(json.dumps(result,indent=2))
        else:print(json.dumps({'operation':'offline_validate_only','name':clean['name'],'points':len(clean['points']),'bytes':len(payload),'record_crc32':crc,'no_device_opened':True},indent=2))
    except (ValueError,OSError,RuntimeError,TimeoutError) as e:p.exit(2,str(e)+'\n')
if __name__=='__main__':main()
