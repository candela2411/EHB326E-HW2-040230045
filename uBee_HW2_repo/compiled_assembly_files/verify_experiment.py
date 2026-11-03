"""Verify external Vivado artifacts with packaged references; never edit original results."""
import argparse,pathlib,json,re,sys,io,contextlib
import check_p1 as p
import check_p1_n32_experiment as legacy
from check_p1_performance import require
from prediction_capability import verify_disabled
HERE=pathlib.Path(__file__).resolve().parent
def configuration(profile,out):
 text=(out/'preflight.txt').read_text();require('PART=xc7a100tcsg324-1' in text and 'TOP=design_1_wrapper' in text,'wrong target/top')
 actual={k:v.strip('"') for k,v in re.findall(r'^CONFIG\.(\w+)=(.*)$',text.split('AFTER:',1)[1],re.M)}
 wanted=json.loads((HERE/'reference_soc_config.json').read_text());table=json.loads((HERE/'profiles.json').read_text())
 wanted.update(dict(zip(table['keys'],map(str,table['profiles'][profile]))))
 for k in ['IMEM_INIT_FILE','DMEM_INIT_FILE']:
  path=pathlib.Path(actual[k]);require(p.sha(path)==p.sha(HERE/wanted[k]),'wrong initialization file content');actual[k]=path.name
 require(actual==wanted,'profile or non-profile configuration mismatch')
 return actual
def n7_check(out):
 manifest=json.loads((HERE/'expected_n7.json').read_text());log=(out/'simulate.log').read_text(errors='replace')
 require('PASS: tb_design_1_dijkstra (' in log and not re.search(r'Fatal:|ERROR:|FAIL:',log),'n7 XSim failure')
 require(all(f'P1 reset pass {i} OK' in log for i in [1,2]),'n7 reset passes incomplete')
 rows=re.findall(r'P1 node=(\d+) dist=(\d+) parent=([0-9a-fA-F]+) visited=(\d+)',log);require(len(rows)==14,'n7 coverage')
 obs=legacy.read_observation(out/'rtl_observation.txt');require(obs['DONE']==p.DONE and obs['STATUS']==0 and obs['EXECUTED_ID']==p.EXEC_ID,'n7 completion')
 runs=[]
 for subset in [rows[:7],rows[7:]]:
  require([int(r[0]) for r in subset]==list(range(7)),'n7 node order')
  words=p.initial_words(manifest['graph']);words[5:8]=[obs['DONE'],obs['STATUS'],obs['EXECUTED_ID']]
  for v,d,parent,visited in subset:
   v=int(v);words[p.DIST//4+v]=int(d);words[p.PARENT//4+v]=int(parent,16);words[p.VISITED//4+v]=int(visited)
  runs.append(p.verify_result(manifest['graph'],words))
 require(runs[0]==runs[1],'n7 reset mismatch')
 return {'result':'PASS','runs':runs,'scope':'n7 RTL correctness; not a performance measurement'}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('profile',choices=['P1','P2','P3','P5','P6']);ap.add_argument('phase',choices=['n7','correctness','performance','synthesis']);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
 base=a.out.resolve()/a.profile;out=base/a.phase
 require(HERE.parent not in out.parents,'evidence must be outside package')
 cfg=configuration(a.profile,out)
 manifest=json.loads((HERE/'expected_n32.json').read_text())
 for name,digest in manifest['sha256'].items():require(p.sha(HERE/name)==digest,'frozen workload changed: '+name)
 if a.phase in ['n7','correctness']:
  r=n7_check(out) if a.phase=='n7' else legacy.check_correctness(out,manifest)
  r.update(profile=a.profile,effective_config=cfg)
  (out/'correctness_result.json').write_text(json.dumps(r,indent=2)+'\n')
 elif a.phase=='performance':
  require((base/'correctness/host_accept.json').exists(),'verify correctness first')
  if a.profile=='P5':legacy.verify_run=verify_disabled
  sys.argv=['verify','performance','--evidence',str(out),'--correctness-evidence',str(base/'correctness')]
  with contextlib.redirect_stdout(io.StringIO()):legacy.main()
  r=json.loads((out/'measurement_result.json').read_text());r.update(profile=a.profile,stage='fixed n32 reproduction',effective_config=cfg)
  r.pop('3C',None);r.pop('other_profiles',None)
  if a.profile=='P5':
   for m in r['runs']:m['misprediction_rate']=None
   r['prediction_limit']='BP disabled: prediction metadata gated off; accuracy/rate unavailable'
  (out/'measurement_result.json').write_text(json.dumps(r,indent=2)+'\n')
 else:
  text=(out/'completion.txt').read_text();require('STATUS=synth_design Complete!' in text and 'BLACKBOXES=\n' in text,'synthesis incomplete/black boxes')
  rpt=(out/'utilization.rpt').read_text();require('xc7a100tcsg324-1' in rpt and 'Design State : Synthesized' in rpt,'wrong resource report')
  require(re.search(r'^clk_in1_0\s+10\.000',(out/'clocks.rpt').read_text(),re.M) is not None,'100MHz clock missing')
  labels={'LUT':'Slice LUTs*','FF':'Register as Flip Flop','BRAM_tiles':'Block RAM Tile','RAMB36':'RAMB36/FIFO*','RAMB18':'RAMB18','DSP':'DSPs'}
  resources={k:float(re.search(r'\|\s*'+re.escape(v)+r'\s*\|\s*([\d.]+)',rpt)[1]) for k,v in labels.items()}
  require(resources['BRAM_tiles']==resources['RAMB36']+resources['RAMB18']/2,'BRAM unit mismatch')
  r={'result':'PASS','profile':a.profile,'resources':resources,'scope':'whole-system post synthesis; no implementation/board claim'}
  (out/'synthesis_result.json').write_text(json.dumps(r,indent=2)+'\n')
 (out/'host_accept.json').write_text(json.dumps({'profile':a.profile,'result':'PASS'})+'\n')
 print(a.profile,a.phase,'PASS')
if __name__=='__main__':main()
