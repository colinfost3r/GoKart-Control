from pathlib import Path
import argparse,json,sys,re,hashlib,statistics,datetime
ROOT=Path(__file__).resolve().parents[6]
BASE=ROOT/'hardware/vesc/kart3/2026-11-11/reverse-filter-trial-01'
parser=argparse.ArgumentParser(description='Offline immutable filter-trial evidence review; never opens a device')
parser.add_argument('--out',required=True,type=Path,help='New output directory')
args=parser.parse_args()
OUT=args.out.resolve()
OUT.mkdir(parents=True,exist_ok=False)
sys.path.insert(0,str(ROOT/'tools/vesc'))
from decode import decode_configuration,decode_telemetry,DEFAULT_SCHEMA
from capture import PacketParser

def sha(data): return hashlib.sha256(data).hexdigest()
def rel(p): return str(p.relative_to(ROOT))
def windows(rows,predicate):
    groups=[]
    for i,r in enumerate(rows):
        if predicate(r['values']):
            if not groups or i!=groups[-1][-1][0]+1: groups.append([])
            groups[-1].append((i,r))
    return [{'first_elapsed_s':g[0][1]['elapsed_s'],'last_elapsed_s':g[-1][1]['elapsed_s'],
             'first_to_last_span_s':g[-1][1]['elapsed_s']-g[0][1]['elapsed_s'],'sample_count':len(g),
             'preceding_nonqualifying_sample_s':rows[g[0][0]-1]['elapsed_s'] if g[0][0]>0 else None,
             'following_nonqualifying_sample_s':rows[g[-1][0]+1]['elapsed_s'] if g[-1][0]+1<len(rows) else None}
            for g in groups]

summary={'schema_version':1,'reviewed_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'evidence_root':rel(BASE),'controller_uuid':'37004e000951343037353739','firmware':'6.02','hardware_reported':'75_300_R2',
 'scope':'Offline independent review of recorded supervised wheels-up trial; no device access during review.',
 'source_human_sha256':'1f49ab2370b5a5960723efd3e0a0b62dd1a9fd5549a2ed21ba9b1281b2def21f',
 'source_deployed_compact_sha256':'d530aeb20c81c185e25ba9b4954473a8bd7069fe5b59b1babeca3ca2b89e94dc',
 'plan_sha256':'c35588937d67f86bd90e67b40f59c2a60a1ed9bddc7edf168c564909ba264805',
 'traces':{},'configuration_checks':{},'status_observations':[],'source_files':[]}
source_paths=set()
for name in ('filtered-forward-trace','filtered-reverse-trace'):
    journal=BASE/name/'packets.jsonl'; manifest=BASE/name/'manifest.json';source_paths.update((journal,manifest))
    records=[json.loads(l) for l in journal.read_text().splitlines()]
    rows=[r for r in records if r.get('direction')=='rx' and r.get('command')==4]
    assert all(decode_telemetry(bytes.fromhex(r['payload_hex']))==r['values'] for r in rows)
    m=json.loads(manifest.read_text());assert len(rows)==m['trace']['telemetry_replies']
    rxtexts=[bytes.fromhex(r['payload_hex'])[1:].rstrip(b'\0').decode() for r in records if r.get('direction')=='rx' and r.get('command') in (135,138)]
    done=[re.fullmatch(r'\(done (\d+) (\d+)\)',t.strip()) for t in rxtexts];done=[x for x in done if x];assert len(done)==1
    tx_payloads=[]
    for r in records:
        if r.get('direction')=='tx_attempt':
            parsed=PacketParser().feed(bytes.fromhex(r['frame_hex']));assert len(parsed)==1;tx_payloads+=parsed
    interval=[b['elapsed_s']-a['elapsed_s'] for a,b in zip(rows,rows[1:])]
    keys=('erpm','iq_a','motor_current_a','battery_current_a','input_voltage_v','fault_code')
    summary['traces'][name]={
      'manifest':rel(manifest),'journal':rel(journal),'complete':m['complete'],'started_utc':m['started_utc'],
      'finished_utc':m['finished_utc'],'capture_elapsed_s':m['trace']['elapsed_s'],'telemetry_samples':len(rows),
      'telemetry_first_elapsed_s':rows[0]['elapsed_s'],'telemetry_last_elapsed_s':rows[-1]['elapsed_s'],
      'median_telemetry_reply_interval_s':statistics.median(interval),'max_telemetry_reply_interval_s':max(interval),
      'extents':{k:{'min':min(r['values'][k] for r in rows),'max':max(r['values'][k] for r in rows)} for k in keys},
      'motion_abs_erpm_gt_50_windows':windows(rows,lambda v:abs(v['erpm'])>50),
      'iq_abs_gt_1a_windows':windows(rows,lambda v:abs(v['iq_a'])>1),
      'iq_positive_gt_1a_windows':windows(rows,lambda v:v['iq_a']>1),
      'iq_negative_lt_minus1a_windows':windows(rows,lambda v:v['iq_a']<-1),
      'raw_rx_sampled_edges':int(done[0][1]),'raw_rx_samples':int(done[0][2]),'raw_monitor_nominal_seconds':30,
      'last_telemetry':rows[-1]['values'],
      'filter_applied_change_lines_during_trace':[t for t in rxtexts if 'gk-rx-filter-applied' in t],
      'raw_monitor_reports':m['trace']['monitor_text'],
      'transmitted_command_id_counts':{str(i):sum(p[0]==i for p in tx_payloads) for i in sorted(set(p[0] for p in tx_payloads))},
      'operator_report':('forward worked' if name=='filtered-forward-trace' else 'Yes—smooth reverse'),
      'operator_report_source':'Parent-recorded user observation; not inferred from packet capture.'}
for kind,command,schema in [('motor',14,'parameters_mcconf.xml'),('app',17,'parameters_appconf.xml')]:
    before_path=BASE/'preflight/raw'/f'{kind}_configuration.bin';before=before_path.read_bytes();source_paths.add(before_path)
    decoded=decode_configuration(before,DEFAULT_SCHEMA/schema,command)['values']
    comparisons=[]
    for p in sorted(BASE.glob(f'*/{kind}_*.bin')):
        actual=p.read_bytes();fields=decode_configuration(actual,DEFAULT_SCHEMA/schema,command)['values'];source_paths.add(p)
        comparisons.append({'file':rel(p),'sha256':sha(actual),'bytes_equal_preflight':actual==before,'decoded_fields_equal_preflight':fields==decoded})
    assert all(x['bytes_equal_preflight'] and x['decoded_fields_equal_preflight'] for x in comparisons)
    summary['configuration_checks'][kind]={'baseline':rel(before_path),'baseline_sha256':sha(before),
       'payload_bytes':len(before),'decoded_fields':len(decoded),'snapshots_compared':len(comparisons),
       'all_match':True,'comparisons':comparisons}
for p in sorted(BASE.glob('status*/manifest.json')):
    m=json.loads(p.read_text());source_paths.add(p)
    s=m['status_before'];contexts=m['contexts_before']['context_id_lines']
    summary['status_observations'].append({'source':rel(p),'started_utc':m['started_utc'],'complete':m['complete'],
       'state':s,'worker_pid_positively_listed':f"ContextID: {s['pid']}" in contexts})
initial_path=BASE/'start-forward/manifest.json';initial=json.loads(initial_path.read_text());source_paths.add(initial_path)
summary['initial_start']={'source':rel(initial_path),'complete':initial['complete'],'lifecycle_sent':initial['lifecycle_sent'],
   'status_after':initial['status_after'],'error':initial['error'],
   'interpretation':'Start occurred once and applied forward, but initial context snapshot did not list PID1244. This verification failure was retained and later resolved by positive PID listings plus at-rest applied direction changes; no second start.'}
load_path=BASE/'load/manifest.json';load=json.loads(load_path.read_text());source_paths.add(load_path)
summary['load']={k:load.get(k) for k in ('complete','steps_completed','activation_sent','stream_sent','flash_written','memory_after')}
assert load['complete'] and load['steps_completed']==24 and not any(load[k] for k in ('activation_sent','stream_sent','flash_written'))
plan_path=BASE/'load/plan.json';source_paths.add(plan_path)
assert sha(plan_path.read_bytes())==summary['plan_sha256']
lifecycle_attempts={'start':[],'stop':[],'rollback':[]}
fixed={"(print (list 'gk-rx-start-result (gk-rx-filter-start t)))":'start',"(print (list 'gk-rx-stop-result (gk-rx-filter-stop)))":'stop',"(print (list 'gk-rx-rollback-result (gk-rx-filter-rollback t)))":'rollback'}
for p in sorted(BASE.glob('*/tx-attempts.bin')):
    source_paths.add(p);parser=PacketParser();packets=parser.feed(p.read_bytes());assert not parser.buffer
    for packet in packets:
        if packet[0]==138:
            expression=packet[1:].rstrip(b'\0').decode()
            if expression in fixed:lifecycle_attempts[fixed[expression]].append(rel(p))
assert len(lifecycle_attempts['start'])==1 and not lifecycle_attempts['stop'] and not lifecycle_attempts['rollback']
summary['recorded_fixed_lifecycle_attempts']=lifecycle_attempts
summary['final_status_source']=rel(BASE/'status-final-forward/manifest.json')
summary['limits']=[
 'Requested gentle manual throttle pulse was at most one second; the capture does not prove pedal duration. Electrical current and coasting continue beyond that requested duration, and telemetry windows must not be labelled exact pedal pulses.',
 'Raw edge count represents changes between approximately 2 ms requested GPIO reads, not every electrical transition and not filtered direction changes.',
 'Forward trace had 152 raw changes while sampled ERPM remained nonnegative; source/state evidence is consistent with filtering, but there is no continuous readback of the native override or every worker iteration.',
 'Reverse trace had a single +45 ERPM sample near rest after negative rotation; this does not establish a physical reversal.',
 'Fault code0 applies to the captured samples. Operator statements establish observed physical behavior, not instrumented direction/range/endurance acceptance.',
 'This was a wheels-up volatile RAM trial with bench supervision. It does not establish road/fleet reliability, permanent wiring repair, autostart or reboot behavior.']
for p in sorted(source_paths):summary['source_files'].append({'file':rel(p),'sha256':sha(p.read_bytes()),'bytes':p.stat().st_size})
(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({'traces':{k:{z:v[z] for z in ('telemetry_samples','extents','raw_rx_sampled_edges','raw_rx_samples','motion_abs_erpm_gt_50_windows','iq_positive_gt_1a_windows','iq_negative_lt_minus1a_windows')} for k,v in summary['traces'].items()},'configuration':{k:{z:v[z] for z in ('baseline_sha256','decoded_fields','snapshots_compared','all_match')} for k,v in summary['configuration_checks'].items()}},indent=2))
