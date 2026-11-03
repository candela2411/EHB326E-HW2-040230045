"""Stage3B only: validate correctness first, then unchanged3A measurement contract.
Does not run Vivado or rebuild assembly. Uses frozen n7 checkers as libraries.
"""
import argparse,csv,json,pathlib,re,sys,hashlib
import check_p1 as p
from check_p1_performance import verify_run,require
from rv32_trace_reference import execute
HERE=pathlib.Path(__file__).resolve().parent

def read_observation(path):
    return {k:int(v,16) for k,v in re.findall(r'^(\w+) = ([0-9a-fA-F]+)$',path.read_text(),re.M)}

def check_correctness(out,manifest,performance=False):
    log=(out/'simulate.log').read_text(errors='replace')
    top='tb_design_1_dijkstra_perf' if performance else 'tb_design_1_dijkstra'
    require('PASS: '+top+' (' in log,'required XSim PASS absent')
    require(not re.search(r'Fatal:|FAIL:|ERROR:',log),'XSim correctness failure')
    require('P1 reset pass 1 OK' in log and 'P1 reset pass 2 OK' in log,'both reset passes must PASS')
    rows=[tuple(int(v,16 if i==2 else 10) for i,v in enumerate(values)) for values in
          re.findall(r'P1 node=(\d+) dist=(\d+) parent=([0-9a-fA-F]+) visited=(\d+)',log)]
    require(len(rows)==64,'expected32 nodes in each of two runs')
    obs=read_observation(out/'rtl_observation.txt')
    require(obs['DONE']==p.DONE and obs['STATUS']==0 and obs['EXECUTED_ID']==p.EXEC_ID,'actual completion fields fail')
    require(obs['S0_DMEM_BASE']==0x20000000 and obs['SP']==0x2000fff0,'wrong hardware address map')
    require(obs['MTVEC']==manifest['symbols']['p1_trap'],'wrong hardware trap address')
    runs=[]
    for subset in [rows[:32],rows[32:]]:
        require([r[0] for r in subset]==list(range(32)),'node ordering/coverage')
        words=p.initial_words(manifest['graph']);words[5:8]=[obs['DONE'],obs['STATUS'],obs['EXECUTED_ID']]
        for v,d,parent,visited in subset:
            words[p.DIST//4+v]=d;words[p.PARENT//4+v]=parent;words[p.VISITED//4+v]=visited
        runs.append(p.verify_result(manifest['graph'],words))
    require(runs[0]==runs[1],'two reset runs disagree')
    return {'result':'PASS','runs':runs,'rtl_observation':obs,
            'initial_matrix_preserved':'asserted by unchanged RTL correctness bench',
            'graph_sha256':manifest['sha256']['graph_n32.json'],
            'dmem_sha256':manifest['sha256']['p1_dmem_n32.hex'],
            'imem_sha256':manifest['sha256']['p1_imem.hex']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['correctness','performance'])
    parser.add_argument('--evidence',type=pathlib.Path,required=True)
    parser.add_argument('--correctness-evidence',type=pathlib.Path)
    args=parser.parse_args();out=args.evidence
    manifest=json.loads((HERE/'expected_n32.json').read_text())
    for name,digest in manifest['sha256'].items():
        require(p.sha(HERE/name)==digest,'frozen artifact mismatch: '+name)
    actual=check_correctness(out,manifest,args.phase=='performance')
    if args.phase=='correctness':
        (out/'correctness_result.json').write_text(json.dumps(actual,indent=2)+'\n')
        print('N32 RTL CORRECTNESS PASS: two resets, dist/parent/visited/done/status/trap/address checks.')
        print('Actual distances:',actual['runs'][0]['dist'])
        return
    require(args.correctness_evidence is not None,'prior correctness checkpoint required')
    prior=json.loads((args.correctness_evidence/'correctness_result.json').read_text())
    require(prior['result']=='PASS' and all(prior[k]==actual[k] for k in ['graph_sha256','dmem_sha256','imem_sha256']),'prior correctness gate mismatch')
    trace=[]
    final,_,_,_=execute(p.read_words(HERE/'p1_imem.hex'),p.read_words(HERE/'p1_dmem_n32.hex'),trace=trace)
    p.verify_result(manifest['graph'],final)
    begin,end=[manifest['symbols'][s] for s in ['p1_algorithm_begin','p1_algorithm_end']]
    expected=[t for t in trace if begin<=t['pc']<end]
    metrics=[{k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)} for line in (out/'p1_perf_n32.log').read_text().splitlines() if line.startswith('METRIC ')]
    require([m['pass'] for m in metrics]==[1,2],'expected2 performance reset passes')
    with (out/'p1_perf_n32_trace.csv').open() as f:
        rows=[{k:int(v,16 if k in ['pc','instruction'] else 10) for k,v in r.items()} for r in csv.DictReader(f)]
    for m in metrics:
        subset=[t for t in rows if t['pass']==m['pass']]
        # This is exactly the 3A verification function, imported without editing it.
        verify_run(m,subset,expected)
        m['cpi_raw_window']=m['cycles']/m['raw_retired']
        m['cpi_algorithm_subset']=m['cycles']/m['algo_retired']
        m['misprediction_rate']=m['algo_miss']/m['algo_branches']
        m['not_taken']=m['algo_branches']-m['algo_taken']
        m['first_instruction_included_latency_cycles']=m['first_retire_edge']-m['first_fetch_edge']+1
        m['outside_retired_pcs']=[f"0x{t['pc']:08x}" for t in subset if not t['scope']]
    require(all(metrics[0][k]==metrics[1][k] for k in ['cycles','raw_retired','algo_retired','branches','taken','correct','miss']),'reset performance inconsistency')
    result={'stage':'3B','result':'PASS','target':'xc7a100tcsg324-1','clock_hz':100000000,
            'graph_statistics':manifest['statistics'],'graph_generation':manifest['graph']['generation'],
            'correctness':actual,'runs':metrics,'source_hashes':manifest['sha256'],
            'window':'unchanged3A: first accepted BEGIN IMEM fetch through actual exit retirement; inclusive edges',
            'cpi_interpretation':'raw-window CPI and algorithm-subset normalization are distinct; pipeline entry can overlap preparation tail',
            'prediction_limit':'existing RTL prediction flags, not an independent predictor-model validation',
            '3C':'NOT STARTED','other_profiles':'NOT STARTED'}
    (out/'measurement_result.json').write_text(json.dumps(result,indent=2)+'\n')
    for m in metrics:print(f"PASS n32 run{m['pass']}: cycles={m['cycles']}, raw_minstret={m['raw_retired']}, algo={m['algo_retired']}, CPI_window={m['cpi_raw_window']:.6f}, CPI_subset={m['cpi_algorithm_subset']:.6f}, branches={m['algo_branches']}, taken={m['algo_taken']}, correct={m['algo_correct']}, miss={m['algo_miss']}, miss_rate={m['misprediction_rate']:.6%}, overlap={m['outside_retired']}")

if __name__=='__main__':
    try:main()
    except (ValueError,OSError) as error:print('FAIL:',error,file=sys.stderr);sys.exit(1)
