#!/usr/bin/env python3
"""Reproduce the reviewed kart-3 compact Lisp and RAM load plan offline.

No device/network API is imported. Default mode checks committed artifacts only.
--out creates a new review directory; it never replaces repository artifacts or
changes hash pins. A changed candidate requires a fresh source/behavior review.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / 'firmware/vesc-lisp/reverse-input'
HUMAN_SOURCE = SOURCE_DIR / 'rx-filter-candidate.lisp'
COMPACT_SOURCE = SOURCE_DIR / 'rx-filter-candidate.compact.lisp'
LOAD_PLAN = SOURCE_DIR / 'rx-filter-load-plan.json'
HUMAN_SHA256 = '1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f'
COMPACT_SHA256 = 'd530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc'
PLAN_SHA256 = 'c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805'


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def compact_source(data):
    """Only the reviewed comment/whitespace transformation, never Lisp rewriting."""
    text = data.decode('ascii')
    if '\0' in text:
        raise ValueError('NUL in source')
    code = '\n'.join(line.split(';', 1)[0] for line in text.splitlines())
    if '"' in code:
        raise ValueError('Quoted strings require a different reviewed compaction')
    return (' '.join(code.split()) + '\n').encode('ascii')


def build_plan(data):
    data.decode('ascii')
    if b'\0' in data: raise ValueError('source contains NUL')
    n=len(data); crc=lambda b:binascii.crc_hqx(b,0)
    steps=[]
    def step(kind,expr,marker):
        size=len(expr.encode('ascii'))+2
        if size>512: raise ValueError(f'{kind}: {size}')
        steps.append(dict(kind=kind,expression=expr,payload_length=size,expected_line=marker))
    step('allocate',f"(progn (define gk-rx-load-buffer (array-create {n+1})) (bufclear gk-rx-load-buffer) (define gk-rx-load-pos 0) (print (list 'gk-rx-load-allocated (buflen gk-rx-load-buffer))))",f'(gk-rx-load-allocated {n+1})')
    offset=0
    while offset<n:
        count=min(192,n-offset)
        while True:
            end=offset+count
            literal=json.dumps(data[offset:end].decode('ascii'),ensure_ascii=True)
            expr=f"(if (= gk-rx-load-pos {offset}) (progn (bufcpy gk-rx-load-buffer {offset} {literal} 0 {count}) (setvar 'gk-rx-load-pos {end}) (print (list 'gk-rx-load-chunk {end} (crc16 gk-rx-load-buffer {end})))) (print 'gk-rx-load-reject))"
            if len(expr.encode())+2<=512: break
            count-=1
            if count<1: raise ValueError('header too large')
        step('chunk',expr,f'(gk-rx-load-chunk {end} {crc(data[:end])})')
        offset=end
    step('verify',f"(print (list 'gk-rx-load-verified gk-rx-load-pos (buflen gk-rx-load-buffer) (crc16 gk-rx-load-buffer {n}) (bufget-u8 gk-rx-load-buffer {n})))",f'(gk-rx-load-verified {n} {n+1} {crc(data)} 0)')
    expr=f"(if (and (= gk-rx-load-pos {n}) (= (buflen gk-rx-load-buffer) {n+1}) (= (crc16 gk-rx-load-buffer {n}) {crc(data)}) (= (bufget-u8 gk-rx-load-buffer {n}) 0)) (progn (eval (read gk-rx-load-buffer)) (setvar 'gk-rx-load-buffer nil) (print (list 'gk-rx-load-ready gk-rx-filter-run gk-rx-filter-active gk-rx-filter-pid gk-rx-filter-applied))) (print 'gk-rx-load-reject))"
    step('eval_definitions_only',expr,'(gk-rx-load-ready nil nil -1 -1)')
    step('cleanup',"(progn (undefine '(gk-rx-load-buffer gk-rx-load-pos)) (gc) (print 'gk-rx-load-clean))",'gk-rx-load-clean')
    return dict(source_length=n,source_sha256=hashlib.sha256(data).hexdigest(),source_crc16=crc(data),max_payload=max(s['payload_length'] for s in steps),steps=steps)


def reviewed_artifacts():
    """Verify exact source pins and regenerate every transmitted expression."""
    human = HUMAN_SOURCE.read_bytes()
    if sha256(human) != HUMAN_SHA256:
        raise ValueError('Human candidate differs from the reviewed source')
    compact = compact_source(human)
    if sha256(compact) != COMPACT_SHA256:
        raise ValueError('Compacted source differs from the reviewed deployment')
    if COMPACT_SOURCE.read_bytes() != compact:
        raise ValueError('Committed compact source does not match regeneration')
    plan_bytes = LOAD_PLAN.read_bytes()
    if sha256(plan_bytes) != PLAN_SHA256:
        raise ValueError('Committed plan differs from the reviewed deployment')
    template = json.loads(plan_bytes)
    regenerated = build_plan(compact)
    for key, value in regenerated.items():
        if template.get(key) != value:
            raise ValueError('Regenerated plan field differs: ' + key)
    if (template.get('human_source_sha256') != HUMAN_SHA256 or
            template.get('human_source_length') != len(human)):
        raise ValueError('Plan human-source provenance differs')
    # Retain reviewed historical provenance bytes, including an old scratch path.
    # That metadata path is never resolved or opened. Rewriting it would change
    # the actual plan hash used during the original bench session.
    return compact, plan_bytes, template


def prepare(out=None):
    compact, plan_bytes, plan = reviewed_artifacts()
    result = {
        'human_source_sha256': HUMAN_SHA256,
        'source_sha256': COMPACT_SHA256,
        'plan_sha256': PLAN_SHA256,
        'source_length': len(compact),
        'source_crc16': plan['source_crc16'],
        'step_count': len(plan['steps']),
        'max_payload_bytes': plan['max_payload'],
        'hardware_accessed': False,
    }
    if out is not None:
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'rx-filter-candidate.compact.lisp').write_bytes(compact)
        (out / 'rx-filter-load-plan.json').write_bytes(plan_bytes)
        (out / 'plan.repl').write_text(
            '\n'.join(step['expression'] for step in plan['steps']) + '\n')
        (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='New offline review directory')
    args = parser.parse_args()
    print(json.dumps(prepare(args.out), indent=2))


if __name__ == '__main__':
    main()
