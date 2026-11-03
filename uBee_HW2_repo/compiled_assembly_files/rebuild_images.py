"""Reproduce fixed images in a fresh external directory; never overwrite this package."""
import argparse,pathlib,shutil,subprocess,sys,hashlib,json
HERE=pathlib.Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser();p.add_argument('--rv32',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
 out=a.out.resolve();package=HERE.parent
 if out==package or package in out.parents:raise ValueError('Use an output directory outside Homework_N')
 if out.exists():raise ValueError('Choose a fresh output directory')
 src=out/'Homework_N/compiled_assembly_files';src.mkdir(parents=True)
 for f in HERE.iterdir():
  if f.is_file():shutil.copy2(f,src/f.name)
 rv=a.rv32.resolve();tool=out/'tool_work'
 manifest=json.loads((HERE/'expected_n7.json').read_text())
 if hashlib.sha256(rv.read_bytes()).hexdigest()!=manifest['assembler_sha256']:raise ValueError('Use the recorded official rv32 1.1.0 executable')
 for args in [[src/'check_p1.py','build','--rv32',rv,'--work',tool],[src/'check_p1.py','emulator','--rv32',rv,'--work',tool],[src/'prepare_n32_benchmark.py']]:
  subprocess.run([sys.executable,'-B',*map(str,args)],cwd=out,check=True)
 for name in ['p1_dijkstra.s','p1_imem.hex','p1_dmem_n7.hex','p1_dmem_n32.hex','graph_n7.json','graph_n32.json','benchmark_n32_edges.csv']:
  if (src/name).read_bytes()!=(HERE/name).read_bytes():raise ValueError('Rebuild differs: '+name)
 print('PASS: fixed assembly/data rebuilt byte-identically; official emulator n7 PASS. No RTL timing claim.')
if __name__=='__main__':main()
