"""Validate Stage 3A evidence, without launching or modifying Vivado.
Main window: first accepted BEGIN fetch through actual algorithm-exit retirement.
Previous preparation instructions can retire during its pipeline entry; report
raw minstret and the exactly reconciled algorithm-only instruction subset.
No result is accepted unless the separate XSim correctness checks also PASS.
"""
import argparse,csv,hashlib,json,pathlib,re,sys
HERE=pathlib.Path(__file__).resolve().parent

def require(condition,message):
    if not condition:raise ValueError(message)

def verify_run(m,trace,expected):
    require(m['cycles']==m['edge_cycles']==m['time_cycles'], 'cycle cross-check')
    require(m['cycles']==m['last_retire_edge']-m['first_fetch_edge']+1,'inclusive edge boundaries')
    require(m['first_fetch_edge']<m['first_issue_edge']<=m['first_ex_edge']<m['first_retire_edge']<=m['last_retire_edge'],'first-instruction latency excluded')
    require(all(m['first_fetch_edge']<=t['edge']<=m['last_retire_edge'] for t in trace),'trace outside window')
    require(all(a['edge']<b['edge'] for a,b in zip(trace,trace[1:])),'duplicate/out-of-order retirement')
    algo=[t for t in trace if t['scope']]
    require(len(algo)==len(expected)==m['algo_retired'],'algorithm instruction count')
    require(len(trace)==m['all_retired']==m['raw_retired'],'minstret/trace mismatch')
    require(m['raw_retired']==m['algo_retired']+m['outside_retired'],'outside tail reconciliation')
    require(algo[0]['edge']==m['first_retire_edge'] and algo[-1]['edge']==m['last_retire_edge'],'retirement boundaries')
    for actual,reference in zip(algo,expected):
        require(all(actual[k]==reference[k] for k in ['pc','instruction','branch','taken']),'independent machine-code execution differs from RTL trace')
    for prefix,items in [('',trace),('algo_',algo)]:
        counts={'branches':sum(t['branch'] for t in items), 'taken':sum(t['taken'] for t in items),
                'correct':sum(t['correct'] for t in items),'miss':sum(t['miss'] for t in items)}
        for key,value in counts.items():require(m[prefix+key]==value,f'{prefix}{key} trace mismatch')
        require(counts['correct']+counts['miss']==counts['branches'],'prediction coverage')
        for t in items:
            require(t['correct']+t['miss']==int(t['branch']),'invalid per-instruction prediction flags')
    for key in ['branches','taken','correct','miss']:
        require(m[key]==m['decoded_'+key],'monitor events differ from independent instruction decode')
    return True

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--evidence',required=True,type=pathlib.Path)
    args=parser.parse_args();out=args.evidence
    import check_p1 as p
    from rv32_trace_reference import execute
    manifest=json.loads((HERE/'expected_n7.json').read_text())
    for name,digest in manifest['sha256'].items():
        require(hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest,'original artifact hash changed: '+name)
    reference=[]
    final,_,_,_=execute(p.read_words(HERE/'p1_imem.hex'),p.read_words(HERE/'p1_dmem_n7.hex'),trace=reference)
    p.verify_result(manifest['graph'],final)
    begin,end=(manifest['symbols'][s] for s in ['p1_algorithm_begin','p1_algorithm_end'])
    reference=[t for t in reference if begin<=t['pc']<end]
    log=(out/'simulate.log').read_text(errors='replace')
    require('PASS: tb_design_1_dijkstra_perf' in log,'XSim correctness/measurement PASS absent')
    require(not re.search(r'Fatal:|FAIL:|ERROR:',log),'XSim failure')
    metrics=[{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)} for line in (out/'p1_perf_n7.log').read_text().splitlines() if line.startswith('METRIC ')]
    require([m['pass'] for m in metrics]==[1,2],'expected two reset passes')
    with (out/'p1_perf_n7_trace.csv').open() as f:
        traces=[{k:int(v,16 if k in ['pc','instruction'] else 10) for k,v in row.items()} for row in csv.DictReader(f)]
    results=[]
    for m in metrics:
        trace=[t for t in traces if t['pass']==m['pass']]
        verify_run(m,trace,reference)
        m['cpi_algorithm_subset']=m['cycles']/m['algo_retired']
        m['cpi_raw_window']=m['cycles']/m['raw_retired']
        m['misprediction_rate']=m['algo_miss']/m['algo_branches'] if m['algo_branches'] else None
        m['first_instruction_included_latency_cycles']=m['first_retire_edge']-m['first_fetch_edge']+1
        m['outside_retired_pcs']=[f"0x{t['pc']:08x}" for t in trace if not t['scope']]
        results.append(m)
    require(all(results[0][key]==results[1][key] for key in ['cycles','algo_retired','raw_retired','algo_branches','algo_miss','algo_correct']),'cold reset repetitions differ; investigate')
    result={'stage':'3A only','result':'PASS','target':'xc7a100tcsg324-1','clock_hz':100000000,
            'window':'first accepted BEGIN IMEM fetch through actual exit-branch retirement, inclusive',
            'pipeline_overlap':'raw minstret includes previous preparation tail; algorithm subset removes its instructions, not fictitious cycles',
            'cpi_interpretation':'fetch-to-retire window cycles / algorithm retired instructions; not an isolated pipeline-drained kernel',
            'cpi_same_window_definition':'cpi_raw_window = cycles / raw minstret delta; cpi_algorithm_subset is separately labelled normalization',
            'prediction_independence_limit':'host independently verifies branch PC/instruction/outcome; prediction correctness flags are existing RTL metadata, not a separate predictor model',
            'reference_algorithm_instructions':len(reference),'runs':results,'original_hashes':manifest['sha256'],
            '3B':'NOT STARTED','3C':'NOT STARTED'}
    (out/'measurement_result.json').write_text(json.dumps(result,indent=2)+'\n')
    for r in results:
        print(f"PASS run{r['pass']}: cycles={r['cycles']}, algorithm_retired={r['algo_retired']}, raw_minstret={r['raw_retired']}, CPI={r['cpi_algorithm_subset']:.6f}, branches={r['algo_branches']}, miss={r['algo_miss']}, outside_tail={r['outside_retired']}")
    print('Cycle=CSR/edge/time agreement; instruction=CSR/RTL trace/independent image execution; branch same-window checks PASS.')

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:print('FAIL:',error,file=sys.stderr);sys.exit(1)
