#!/usr/bin/env python3
"""Read only status / espnow status on fixed kart3 board ports. No DTR/RTS changes."""
import contextlib,datetime,json,os,select,time,argparse
from pathlib import Path
from read_lisp import SerialConnection
PORTS={'heltec':'/dev/cu.usbmodem1101','core2':'/dev/cu.usbserial-59740081161'}
def main():
 p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--seconds',type=int,choices=range(5,181),default=30);a=p.parse_args()
 a.out.mkdir(parents=True,exist_ok=False);m={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'complete':False,'allowed_commands':['status','espnow status'],'port_control':'termios; HUPCL disabled; no DTR/RTS manipulation','latest':{}}
 try:
  with contextlib.ExitStack() as stack,(a.out/'responses.jsonl').open('w') as log:
   cs={n:stack.enter_context(SerialConnection(port)) for n,port in PORTS.items()};byfd={c.fd:n for n,c in cs.items()};buf={n:b'' for n in cs}
   start=time.monotonic();last=-100
   while time.monotonic()-start<a.seconds:
    now=time.monotonic()-start
    if now-last>=2:
     for n,c in cs.items():
      for command in (b'status\n',b'espnow status\n'):
       if os.write(c.fd,command)!=len(command):raise IOError('Partial query; stop')
     last=now
    ready,_,_=select.select(list(byfd),[],[],.1)
    for fd in ready:
     n=byfd[fd];data=os.read(fd,16384)
     if not data:raise IOError('Board serial EOF')
     buf[n]+=data
     if len(buf[n])>131072:raise IOError('Oversized board stream')
     while b'\n' in buf[n]:
      line,buf[n]=buf[n].split(b'\n',1)
      try:d=json.loads(line)
      except (ValueError,UnicodeError):continue
      if d.get('t') not in ('status','m5_status','espnow'):continue
      for key in ('ssid','wifi','gps_lat','gps_lon'):d.pop(key,None)
      row={'board':n,'seconds':time.monotonic()-start,'status':d};log.write(json.dumps(row)+'\n');log.flush();m['latest'].setdefault(n,{})[d['t']]=d
   m['complete']=True
 except BaseException as e:m['error']=repr(e);raise
 finally:
  m['finished_utc']=datetime.datetime.now(datetime.timezone.utc).isoformat();(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
 print(json.dumps(m,indent=2))
if __name__=='__main__':main()
