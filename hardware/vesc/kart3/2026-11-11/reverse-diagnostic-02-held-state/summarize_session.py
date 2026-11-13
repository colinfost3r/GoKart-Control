#!/usr/bin/env python3
"""Offline evidence summary; reads saved payloads, never opens devices."""
import argparse, collections, hashlib, json, statistics, struct
from pathlib import Path

FIELDS = [('mosfet_temp_c','h',10),('motor_temp_c','h',10),('motor_current_a','i',100),
('battery_current_a','i',100),('id_a','i',100),('iq_a','i',100),('duty','h',1000),
('erpm','i',1),('input_voltage_v','h',10),('amp_hours','i',10000),('amp_hours_charged','i',10000),
('watt_hours','i',10000),('watt_hours_charged','i',10000),('tachometer','i',1),
('tachometer_absolute','i',1),('fault_code','B',1),('pid_position','i',1000000),
('controller_id','B',1),('mosfet_temp_1_c','h',10),('mosfet_temp_2_c','h',10),
('mosfet_temp_3_c','h',10),('vd_v','i',1000),('vq_v','i',1000)]

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def decode(payload):
    assert len(payload)==74 and payload[0]==4
    out={}; pos=1
    for key,fmt,scale in FIELDS:
        value=struct.unpack_from('>'+fmt,payload,pos)[0];pos+=struct.calcsize(fmt)
        out[key]=value/scale if scale!=1 else value
    out['status_raw']=payload[pos];out['timeout_active']=bool(payload[pos]&1)
    out['kill_switch_active']=bool(payload[pos]&2);out['bytes_consumed']=pos+1
    assert pos+1==74
    return out

def trace(base,name):
    path=base/name; manifest=read(path/'manifest.json')
    records=[json.loads(x) for x in (path/'packets.jsonl').read_text().splitlines()]
    values=[];rows=[];done=None;pending=0;maximum_pending=0;tx=collections.Counter();rx=collections.Counter()
    for record in records:
        if record.get('direction')=='tx_attempt':
            tx[record['action']]+=1
            frame=bytes.fromhex(record['frame_hex']);header=frame[0]
            size=int.from_bytes(frame[1:header],'big');payload=frame[header:header+size]
            assert len(frame)==header+size+3 and frame[-1]==3
            import binascii
            assert binascii.crc_hqx(payload,0)==int.from_bytes(frame[-3:-1],'big')
            if record['action']=='values':pending+=1;maximum_pending=max(maximum_pending,pending)
            continue
        rx[str(record['command'])]+=1
        if record['command']==4:
            value=decode(bytes.fromhex(record['payload_hex']))
            assert value==record['values'], 'Independent decode differs from live log'
            values.append({'host_elapsed_s':record['elapsed_s'],**value});pending-=1
            assert pending>=0
        elif record['command']==135:
            text=bytes.fromhex(record['payload_hex'])[1:].decode().strip('\0')
            assert text==record['text']
            words=text.translate(str.maketrans('','','{}()')).split()
            if words[0]=='done':
                done={'host_elapsed_s':record['elapsed_s'],'edges':int(words[1]),'samples':int(words[2]),'text':text}
            elif len(words)==7:
                rows.append(dict(zip(('lisp_elapsed_s','rx','edges','samples','adc_decoded','erpm','fault'),map(float,words)),host_elapsed_s=record['elapsed_s']))
    assert maximum_pending==1 and pending==0 and done and len(values)==manifest['trace']['telemetry_replies']
    extrema={}
    for field in ('motor_current_a','battery_current_a','id_a','iq_a','duty','erpm','input_voltage_v','tachometer','tachometer_absolute','vd_v','vq_v'):
        low=min(values,key=lambda x:x[field]);high=max(values,key=lambda x:x[field])
        extrema[field]={'min':low[field],'min_at_host_s':low['host_elapsed_s'],'max':high[field],'max_at_host_s':high['host_elapsed_s']}
    def first_motion(threshold):
        return next(({'host_elapsed_s':x['host_elapsed_s'],'erpm':x['erpm']} for x in values if abs(x['erpm'])>threshold),None)
    intervals=[b['host_elapsed_s']-a['host_elapsed_s'] for a,b in zip(values,values[1:])]
    stationary=[x['adc_decoded'] for x in rows if abs(x['erpm'])<=50 and x['adc_decoded']<0.15]
    result={'manifest':f'{name}/manifest.json','packets':f'{name}/packets.jsonl',
      'started_utc':manifest['started_utc'],'finished_utc':manifest['finished_utc'],'complete':manifest['complete'],
      'capture_elapsed_s':manifest['trace']['elapsed_s'],'tx_action_counts':dict(tx),'rx_command_counts':dict(rx),
      'max_outstanding_values_queries_reconstructed':maximum_pending,'telemetry_samples':len(values),
      'telemetry_first_host_s':values[0]['host_elapsed_s'],'telemetry_last_host_s':values[-1]['host_elapsed_s'],
      'telemetry_interarrival_seconds':{'min':min(intervals),'median':statistics.median(intervals),'max':max(intervals)},
      'requested_telemetry_hz':10,'observed_rate_over_entire_capture_hz':len(values)/manifest['trace']['elapsed_s'],
      'extrema':extrema,'fault_codes':sorted(set(x['fault_code'] for x in values)),
      'timeout_seen':any(x['timeout_active'] for x in values),'kill_switch_seen':any(x['kill_switch_active'] for x in values),
      'first_nonzero_erpm':first_motion(0),'first_abs_erpm_gt_50':first_motion(50),
      'last_abs_erpm_gt_50':next(({'host_elapsed_s':x['host_elapsed_s'],'erpm':x['erpm']} for x in reversed(values) if abs(x['erpm'])>50),None),
      'monitor':{'nominal_window_s':30,'printed_rows':len(rows),'rx_at_print_times':sorted(set(int(x['rx']) for x in rows)),
        'done':done,'adc_min':min(x['adc_decoded'] for x in rows),'adc_max':max(x['adc_decoded'] for x in rows),
        'stationary_below_deadband_adc_min':min(stationary),'stationary_below_deadband_adc_max':max(stationary),
        'rows':rows,'limitation':'2ms nominal samples with cumulative edge count; only 1Hz rows saved. No individual pulse-width record. RX monitoring ends at done, before telemetry capture ends.'}}
    if name=='forward-trace-01':
        late=[x for x in values if 18<=x['host_elapsed_s']<=21.1]
        result['early_chatter']={'first_row_host_s':rows[0]['host_elapsed_s'],'edges_by_first_row':int(rows[0]['edges']),
         'first_nonzero_erpm_host_s':first_motion(0)['host_elapsed_s'],'precedes_first_nonzero_erpm':rows[0]['host_elapsed_s']<first_motion(0)['host_elapsed_s']}
        before=next(x for x in rows if 18<x['lisp_elapsed_s']<19);after=next(x for x in rows if 21<x['lisp_elapsed_s']<22)
        result['late_stationary_burst']={'monitor_interval_host_s':[before['host_elapsed_s'],after['host_elapsed_s']],
         'edges_before':int(before['edges']),'edges_after':int(after['edges']),'edge_increase':int(after['edges']-before['edges']),
         'telemetry_check_interval_host_s':[18,21.1],'telemetry_samples':len(late),'erpm_values':sorted(set(x['erpm'] for x in late)),
         'max_abs_motor_current_a':max(abs(x['motor_current_a']) for x in late)}
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source',required=True,type=Path);ap.add_argument('--out',required=True,type=Path);args=ap.parse_args()
    base=args.source; args.out.mkdir(parents=True,exist_ok=False)
    mc=read(base/'decoded-after-reconnect/motor_configuration.json')['values'];app=read(base/'decoded-after-reconnect/app_configuration.json')['values']
    oldbase=base.parent/'reverse-diagnostic-01';oldmc=read(oldbase/'decoded-after-monitor/motor_configuration.json')['values']
    snapshots={}
    for name in ('reverse-01','forward-01','reverse-before-trace'):
        manifest=read(base/name/'manifest.json');rows=[json.loads(x) for x in (base/name/'packets.jsonl').read_text().splitlines()]
        texts=[bytes.fromhex(x['payload_hex'])[1:].decode().strip('\0') for x in rows if x['command']==135]
        line=next(x for x in texts if x.startswith('(pins '));w=line.translate(str.maketrans('','','{}()')).split()
        snapshots[name]={'manifest':f'{name}/manifest.json','packets':f'{name}/packets.jsonl','manifest_complete':manifest['complete'],
          'raw_line':line,'rx':int(w[1]),'tx':int(w[2]),'adc_decoded':float(w[3]),'erpm':float(w[4]),'fault':int(w[5]),
          'identity_before_present':(base/name/'identity_before.bin').exists(),'identity_after_present':(base/name/'identity_after.bin').exists()}
    summary={'schema_version':1,'session':'kart3-reverse-diagnostic-02-held-state','date':'2026-11-11',
      'evidence_paths_relative_to':'reverse-diagnostic-02-held-state directory','uuid':'37004e000951343037353739',
      'firmware':'6.02','firmware_name':'no_hw_limits','reported_hardware_target':'75_300_R2',
      'operator_identified_physical_controller':'Flipsky 75100 Pro V2.0','analysis_method':'Independently decoded every saved74-byte GET_VALUES payload with signed big-endian fields; cross-checked stored decoded values; counted raw prints/TX/RX; recomputed extrema/timing. Incoming CRC verification relies on live capture metadata because logs retain payloads, not RX frame CRCs. TX frame CRCs independently checked.',
      'snapshots':snapshots,'traces':{n:trace(base,n) for n in ('failure-trace-01','forward-trace-01')},
      'configuration_after_owner_reported_power_cycle':{
        'scope':'runtime readback; not an independent flash dump','motor_json':'decoded-after-reconnect/motor_configuration.json','app_json':'decoded-after-reconnect/app_configuration.json',
        'sport_equivalent_limits':{k:mc[k] for k in ('l_current_max','l_current_max_scale','l_current_min_scale','l_min_erpm','l_max_erpm')},
        'unchanged_braking_settings':{k:mc[k] for k in ('l_current_min','l_in_current_min')},
        'app':{k:app[k] for k in ('app_to_use','servo_out_enable','app_adc_conf.ctrl_type','app_adc_conf.buttons','app_adc_conf.hyst','app_adc_conf.safe_start','app_adc_conf.voltage_start','app_adc_conf.voltage_end')},
        'app_blob_identical_to_previous_session':(base/'raw-after-reconnect/app_configuration.bin').read_bytes()==(oldbase/'raw-after-monitor/app_configuration.bin').read_bytes(),
        'motor_differences_vs_previous_runtime':{k:{'before':oldmc.get(k),'after':v} for k,v in mc.items() if oldmc.get(k)!=v},
        'differences_interpretation':'Owner power-cycle/reconnect preceded this readback. SPORT-equivalent scale/ERPM limits and small current/voltage ADC offset differences observed; no diagnostic config-write or detection command was sent. Do not label the offset differences Hall/pedal recalibration.'},
      'operator_reports':{
        'reverse_trace_result':'Operator confirmed reverse worked during failure-trace-01; folder name records original test intent, not outcome.',
        'earlier_symptom':'Owner previously described failed reverse/stuttering forwards; not assumed reproduced by failure-trace-01.',
        'meter_caveat':'Meter descriptions were corrected during troubleshooting; some terminal/reference/unit descriptions were uncertain. They are reported observations, not calibrated measurements retained in this evidence set; do not infer a resistance value or exact connector voltage from them.',
        'end_state':'Owner reported VESC powered off; Heltec off. This is end-of-session status, not a live reading.'},
      'scope_and_limits':{
        'configuration_writes_sent':False,'motor_actuation_commands_sent':False,'flash_writes_sent':False,'hall_or_pedal_detection_sent':False,'direction_filter_loaded_or_activated':False,
        'operator_actuation':'Any motion used the owner-operated wired throttle and direction switch.',
        'diagnostic_actions':'Identity/configuration/telemetry reads; fixed read-only faults/foc_state terminal commands; volatile input-reading Lisp snapshot/monitor expressions. REPL can initialize/pause/GC/resume interpreter; not a controller reset.',
        'reverse_rx_after_monitor_done':'UNKNOWN. Reverse acceleration/coastdown continued after monitor ended; later telemetry does not prove RX remained low.',
        'motor_temperature':'No motor temperature sensors wired; do not interpret returned motor_temp_c as a valid thermal measurement.',
        'cause_not_proven':'Forward trial demonstrates unstable sampled RX, including before first nonzero ERPM and a later stationary burst. It does not locate the electrical cause or prove every historical symptom has this cause.',
        'next_step':'With controller off, isolate switch contacts and short local wiring/ground path before considering the software filter. No-throttle electrical isolation first; filter deferred.'},
      'helper_provenance':{
        'monitor_file_sha256_from_manifests':'6ba5d52cec8608cf295b5a98a96b26a9bd6fea9ddd364db3dbc9a25150610e1f',
        'limitation':'Historical helper-source hashes were not embedded in run manifests. Current helper files may include later parser/console changes; their hashes are inventory only, not proof of the exact executed version. Logged TX frames and payloads provide stronger action-level evidence.',
        'current_file_inventory':[]},
      'evidence_file_inventory':[]}
    for p in [Path('/tmp/gokart-rx-session-20261111/rx_failure_trace.py'),Path('/tmp/gokart-rx-session-20261111/rx_probe.py'),base.parents[4]/'tools/vesc/rx_probe.py']:
        if p.exists():summary['helper_provenance']['current_file_inventory'].append({'path':str(p),'sha256_now':sha(p),'bytes':p.stat().st_size})
    for p in sorted(base.rglob('*')):
        if p.is_file() and not (p.parent==base and p.name in {'README.md','summary.json','summarize_session.py','candidate-offline-validation.json'}):summary['evidence_file_inventory'].append({'path':str(p.relative_to(base)),'bytes':p.stat().st_size,'sha256':sha(p)})
    summary['snapshot_parser_failure']={'run':'reverse-before-trace','manifest_complete':False,'valid_raw_input_packet_observed':True,
      'reason':'Host-side numeric recognizer rejected LispBM curly-brace float notation; the raw135 packet contains '+snapshots['reverse-before-trace']['raw_line']+' and >t followed.',
      'handling':'Keep original incomplete manifest/error and missing identity-after evidence. Use raw packet as an observed snapshot, not as a completed automated session.'}
    (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('Summarized',[(n,v['telemetry_samples'],v['monitor']['done']) for n,v in summary['traces'].items()])

if __name__=='__main__':main()
