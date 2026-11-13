"""Versioned no-Pi Core2 course package. Pure export and bounded USB publication state.
No device opens and no motor/console-command fields in the package.
"""
import math
import struct
import zlib
from kartcore import douglas_peucker

HEADER, ZONE_BYTES = 96, 96
MAX_TRACK, MAX_ZONES, MAX_LINES = 128, 16, 64
MAX_PACKAGE = HEADER + MAX_TRACK * 8 + MAX_ZONES * ZONE_BYTES + MAX_LINES * 16 + 4


def _number(v, low, high):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or not low <= v <= high:
        raise ValueError('invalid numeric course field')
    return float(v)


def _point(p):
    if not isinstance(p, (list, tuple)) or len(p) != 2:
        raise ValueError('expected latitude/longitude pair')
    return struct.pack('<ii', round(_number(p[0], -90, 90) * 1e7), round(_number(p[1], -180, 180) * 1e7))


def _distance(a, b):
    return math.hypot((a[0]-b[0])*111320, (a[1]-b[1])*111320*math.cos(math.radians((a[0]+b[0])/2)))


GAME_SPEEDS = {'eco': 0, 'normal': 1}   # the host's game speed; never the top mode, so a boost always has a step up


def export(doc, *, host, instance, revision, name='Hosted course', background=(), speed='eco'):
    if speed not in GAME_SPEEDS:
        raise ValueError('game speed must be eco or normal')
    if type(host) is not int or not 1 <= host <= 8 or type(instance) is not int or not 1 <= instance <= 0xffffffff or type(revision) is not int or not 1 <= revision <= 0xffffffff:
        raise ValueError('host, instance and revision must be explicit nonzero identities')
    if not isinstance(doc, dict) or doc.get('enabled') is not True or doc.get('source') != 'freeplay':
        raise ValueError('a running host freeplay document is required')
    title = name.encode('ascii')
    if not 1 <= len(title) <= 40 or any(c < 32 or c > 126 for c in title):
        raise ValueError('course name must be 1..40 printable ASCII bytes')
    track = doc.get('track', {})
    if not isinstance(track, dict): raise ValueError('invalid track')
    pts = track.get('points', [])
    if not isinstance(pts, list): raise ValueError('invalid track points')
    for p in pts: _point(p)
    if 128 < len(pts) <= 200: pts = douglas_peucker(pts, 1.0)
    if not 2 <= len(pts) <= MAX_TRACK or type(track.get('closed', True)) is not bool:
        raise ValueError('course exceeds 128 points after 1 m simplification; simplify on host')
    encoded = [_point(p) for p in pts]
    if len(set(encoded)) < 2 or any(_distance(pts[0], p) > 5000 for p in pts):
        raise ValueError('degenerate or oversized course')
    rows, lap = [], None
    zones = doc.get('zones', [])
    if not isinstance(zones, list): raise ValueError('invalid zones')
    for zone in zones:
        if not isinstance(zone, dict): raise ValueError('invalid zone')
        kind = zone.get('type')
        if kind == 'lapline':
            if lap is not None or zone.get('shape') != 'line':
                raise ValueError('only one segment lap line is supported')
            a, b = zone.get('a'), zone.get('b')
            lap = _point(a) + _point(b) + struct.pack('<I', round(_number(zone.get('min_lap_s', 20), 1, 300)*1000))
            if _distance(a,b) < 1:
                raise ValueError('lap line too short')
            continue
        if kind not in ('boost', 'mud', 'item'):
            raise ValueError('unsupported host zone type')
        row = bytearray(ZONE_BYTES)
        row[0] = {'boost':1, 'mud':2, 'item':3}[kind]
        row[3] = int(_number(zone.get('secs', 5 if kind == 'boost' else 4), 1, 30))
        row[4] = round(_number(zone.get('scale', 1 if kind != 'mud' else .5), .1, 1)*100)
        struct.pack_into('<H', row, 10, round(_number(zone.get('cooldown_s', 15 if kind == 'item' else 20), 1, 600)))
        shape = zone.get('shape')
        if shape == 'circle':
            center = [zone.get('lat'), zone.get('lon')]
            row[12:20] = _point(center)
            struct.pack_into('<H', row, 8, round(_number(zone.get('r_m'), 3, 200)*100))
        elif shape == 'polygon':
            points = zone.get('points', [])
            if not 3 <= len(points) <= 8:
                raise ValueError('polygon needs 3..8 vertices')
            for i,p in enumerate(points):
                row[20+i*8:28+i*8] = _point(p)
                if _distance(pts[0],p) > 5000: raise ValueError('zone outside supported extent')
            row[1], row[2] = 1, len(points)
            center = [sum(p[j] for p in points)/len(points) for j in (0,1)]
            row[12:20] = _point(center)
        else:
            raise ValueError('unsupported zone shape')
        if _distance(pts[0], center) > 5000: raise ValueError('zone outside supported extent')
        rows.append(row)
    if len(rows) > MAX_ZONES or len(background) > MAX_LINES:
        raise ValueError('too many zones or background segments')
    lines = []
    for a,b in background:
        lines.append(_point(a)+_point(b))
        if _distance(pts[0],a)>10000 or _distance(pts[0],b)>10000: raise ValueError('background outside supported extent')
    header=bytearray(HEADER)
    header[:8]=b'GKG1'+bytes([host,2,2|int(track.get('closed',True))|(4 if lap else 0),len(title)])
    struct.pack_into('<IIHHH',header,8,instance,revision,len(pts),len(rows),len(lines))
    header[22]=1  # OSM/ODbL attribution metadata; displayed at startup.
    header[23]=GAME_SPEEDS[speed]  # rules v2: the mode every joined kart plays at
    header[24:24+len(title)]=title
    if lap: header[64:84]=lap
    payload=bytes(header)+b''.join(encoded)+b''.join(rows)+b''.join(lines)
    return payload+struct.pack('<I',zlib.crc32(payload))


class Publisher:
    """ACK-paced USB data upload. No retry after uncertain commit; explicit new publish required.
    A timeout cancels the local operation. Link recovery never publishes or joins by itself.
    """
    def __init__(self):
        self.payload = None
        self.offset = 0
        self.phase = 'idle'
        self.waiting = None
        self.deadline = 0
        self.error = None
        self.digest = 0

    def start(self, payload, now):
        if not isinstance(payload, bytes) or not 116 <= len(payload) <= MAX_PACKAGE or payload[:4] != b'GKG1' or zlib.crc32(payload[:-4]) != int.from_bytes(payload[-4:],'little'):
            raise ValueError('invalid course package')
        if self.phase not in ('idle','ready','error'): raise ValueError('publication already in progress')
        self.payload,self.offset,self.phase,self.waiting,self.error = payload,0,'begin',None,None
        self.digest=int.from_bytes(payload[-4:],'little')
        self.deadline=now+60

    def withdraw(self, now):
        # Data-only withdrawal may be repeated until its ACK; no vehicle command.
        self.payload=None;self.waiting=None;self.phase='clear';self.deadline=now+10;self.error=None

    def cancel(self, why):
        self.payload=None;self.waiting=None;self.phase='error';self.error=why

    def next_line(self, now):
        if self.phase in ('idle','ready','error'): return None
        if now >= self.deadline or (self.waiting and now >= self.waiting[1]):
            self.cancel('publish timeout; inspect host before retrying');return None
        if self.waiting:return None
        if self.phase=='clear':line='share clear'
        elif self.phase=='begin':line=f'share begin {len(self.payload)} {self.digest:08x}'
        elif self.phase=='chunk':line=f'share chunk {self.offset} {self.payload[self.offset:self.offset+64].hex()}'
        else:line='share commit'
        self.waiting=(self.phase,now+3)
        return line

    def reply(self, msg, now):
        if msg.get('t')!='share' or not self.waiting:return False
        action=self.waiting[0]
        if msg.get('action')!=action:return False
        if now >= self.waiting[1] or msg.get('ok') is not True:
            self.cancel('publication rejected or late');return True
        if action=='clear':
            self.waiting=None;self.phase='idle';return True
        expected = 0 if action=='begin' else (min(len(self.payload),self.offset+64) if action=='chunk' else len(self.payload))
        if type(msg.get('received')) is not int or msg['received']!=expected or msg.get('digest')!=f'{self.digest:08x}':
            self.cancel('publication readback mismatch');return True
        self.waiting=None
        if action=='commit':self.phase='ready';self.payload=None
        else:self.offset=expected;self.phase='commit' if expected==len(self.payload) else 'chunk'
        return True


def background_lines(geojson, track, limit=MAX_LINES):
    """Quiet nearby OSM context, bounded by distance; never a driving route or a tile request."""
    if not track:return []
    center=[sum(p[j] for p in track)/len(track) for j in (0,1)]
    radius=max(_distance(center,p) for p in track)+120
    candidates=[]
    for f in geojson.get('features',[]):
        geom=f.get('geometry',{});kind=f.get('properties',{}).get('kind')
        if kind not in ('road','building','water','coastline','rail'):continue
        if geom.get('type')=='Polygon':rings=geom.get('coordinates',[])
        elif geom.get('type')=='LineString':rings=[geom.get('coordinates',[])]
        else:continue
        for ring in rings:
            for a,b in zip(ring,ring[1:]):
                a,b=[a[1],a[0]],[b[1],b[0]]
                try:_point(a);_point(b)
                except (ValueError,TypeError,IndexError):continue
                d=min(_distance(center,a),_distance(center,b))
                if d<=radius and max(_distance(track[0],a),_distance(track[0],b))<10000:
                    candidates.append((d,a,b))
    candidates.sort(key=lambda row:row[0])
    return [(a,b) for _,a,b in candidates[:limit]]
