"""P1 image builder and independent result verifier. Python 3 standard library only.

Usage: check_p1.py build --rv32 PATH --work PATH [--graph graph_n7.json]
       check_p1.py emulator --rv32 PATH --work PATH
       check_p1.py verify --dump WORD_IMAGE [--graph graph_n7.json]

All temporary board files, logs, combined emulator source and unused assembler
outputs go to --work, which MUST be outside Homework_N. No Vivado is invoked.
The emulator checks functional results only, never FPGA cycle performance.
"""
import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

BASE = 0x20000000
INF = 0x7fffffff
NO_EDGE = 0xffffffff
DONE = 0x444f4e45
EXEC_ID = 0x44494a31
MAGIC = 0x5031444a
MATRIX, DIST, VISITED, PARENT = 0x100, 0x4100, 0x4200, 0x4300
WORDS = 16384
HERE = pathlib.Path(__file__).resolve().parent


def graph_matrix(g):
    n, source = g['n'], g['source']
    if type(n) is not int or not 1 <= n <= 64:
        raise ValueError('N must be an integer in 1..64')
    if type(source) is not int or not 0 <= source < n:
        raise ValueError('source outside graph')
    if type(g.get('directed')) is not bool:
        raise ValueError('directed must be a boolean')
    matrix = [[NO_EDGE] * n for _ in range(n)]
    for i in range(n):
        matrix[i][i] = 0
    seen = set()
    for edge in g['edges']:
        if len(edge) != 3 or any(type(x) is not int for x in edge):
            raise ValueError('edge must contain three integers')
        u, v, w = edge
        if not (0 <= u < n and 0 <= v < n and 0 <= w <= 1000000):
            raise ValueError('edge endpoint or weight outside supported range')
        key = (u, v) if g['directed'] else tuple(sorted((u, v)))
        if key in seen:
            raise ValueError('duplicate edge')
        seen.add(key)
        matrix[u][v] = w
        if not g['directed']:
            matrix[v][u] = w
    return matrix


def reference(matrix, source):
    """Floyd-Warshall: independent of firmware's greedy Dijkstra loops."""
    n = len(matrix)
    d = [[INF if w == NO_EDGE else w for w in row] for row in matrix]
    for i in range(n):
        d[i][i] = 0
    for k in range(n):
        for i in range(n):
            for j in range(n):
                if d[i][k] != INF and d[k][j] != INF:
                    d[i][j] = min(d[i][j], d[i][k] + d[k][j])
    return d[source]


def initial_words(g):
    matrix = graph_matrix(g)
    words = [0] * WORDS
    words[:8] = [MAGIC, g['n'], g['source'], NO_EDGE, INF, 0, 0, 0]
    flat = [w for row in matrix for w in row]
    words[MATRIX//4:MATRIX//4+len(flat)] = flat
    return words


def verify_result(g, words):
    matrix = graph_matrix(g)
    n, source = g['n'], g['source']
    expected = reference(matrix, source)
    if len(words) != WORDS:
        raise ValueError('result must contain exactly 16384 words')
    if words[:5] != [MAGIC,n,source,NO_EDGE,INF]:
        raise ValueError('input header changed')
    if words[5:8] != [DONE,0,EXEC_ID]:
        raise ValueError('missing done, firmware error status or wrong executed_id')
    flat = [w for row in matrix for w in row]
    if words[MATRIX//4:MATRIX//4+len(flat)] != flat:
        raise ValueError('input matrix was modified')
    dist = words[DIST//4:DIST//4+n]
    visited = words[VISITED//4:VISITED//4+n]
    parent = words[PARENT//4:PARENT//4+n]
    if dist != expected:
        raise ValueError(f'dist mismatch: actual={dist}, expected={expected}')
    for v in range(n):
        if dist[v] == INF:
            if parent[v] != NO_EDGE or visited[v] != 0:
                raise ValueError(f'unreachable node {v}: parent/visited invalid')
            continue
        if visited[v] != 1:
            raise ValueError(f'reachable node {v} not visited')
        if v == source and parent[v] != NO_EDGE:
            raise ValueError('source parent must be -1')
        current, cost, seen = v, 0, set()
        while current != source:
            if current in seen or len(seen) >= n:
                raise ValueError(f'cyclic parent chain at {v}')
            seen.add(current)
            p = parent[current]
            if p >= n or matrix[p][current] == NO_EDGE:
                raise ValueError(f'invalid parent edge at {current}')
            w = matrix[p][current]
            if dist[p] == INF or dist[p] + w != dist[current]:
                raise ValueError(f'parent distance equation failed at {current}')
            cost += w
            current = p
        if cost != dist[v]:
            raise ValueError(f'path cost mismatch at {v}')
    return {'dist':dist, 'parent':parent, 'visited':visited, 'done':words[5], 'status':words[6]}


def write_words(path, words):
    path.write_text(''.join(f'{w:08x}\n' for w in words), encoding='ascii')


def read_words(path):
    lines = path.read_text(encoding='ascii').splitlines()
    if len(lines) != WORDS or any(not re.fullmatch('[0-9a-fA-F]{8}', line) for line in lines):
        raise ValueError(f'{path.name}: expected 16384 plain 32-bit hex words')
    return [int(line,16) for line in lines]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def invoke(rv32, args, work, log_name, stdin=None):
    command = [str(rv32), *map(str,args)]
    result = subprocess.run(command, input=stdin, text=True, encoding='utf-8',
                            errors='replace', capture_output=True, cwd=work, timeout=120)
    (work/log_name).write_text(result.stdout+result.stderr, encoding='utf-8')
    if result.returncode:
        raise ValueError(f'assembler/emulator exit={result.returncode}: {result.stdout}{result.stderr}')
    return result.stdout


def setup(args):
    work = args.work.resolve()
    # Neither tool output nor transient source may be inside the submission.
    package = HERE.parent
    if work == package or package in work.parents:
        raise ValueError('--work must be outside Homework_N')
    work.mkdir(parents=True, exist_ok=True)
    board = work/'p1_soc.toml'
    # Release 1.1.0 supports sizes but not the newer imem_base/dmem_base keys.
    # Firmware boot code selects SoC or teaching bases from PC bit31.
    board.write_text('[machine]\nimem = 65536\ndmem = 65536\n', encoding='ascii')
    return work, board


def build(args):
    work, board = setup(args)
    g = json.loads(args.graph.read_text(encoding='utf-8'))
    words = initial_words(g)
    # Fixed n7 filenames prevent accidental replacement when exploring later sizes.
    if g['n'] != 7:
        raise ValueError('this first-step build emits only n7; use new filenames for later workloads')
    version = invoke(args.rv32,['--version'],work,'version.log').strip()
    if not version.startswith('rv32 1.1.0 '):
        raise ValueError(f'unverified assembler version: {version}')
    asm_args=['asm',HERE/'p1_dijkstra.s','--devices',board,'--pad',
              '-o',HERE/'p1_imem.hex','--dmem',work/'unused_dmem.hex']
    print(invoke(args.rv32,asm_args,work,'assemble.log').strip())
    read_words(HERE/'p1_imem.hex')
    write_words(HERE/'p1_dmem_n7.hex',words)
    symbols=invoke(args.rv32,['dbg',HERE/'p1_dijkstra.s','--devices',board],
                   work,'symbols.log','info symbols\nquit\n')
    addresses={name:int(addr,16) for addr,name in
               re.findall(r'\b0x([0-9a-fA-F]{8})\s+\d+\s+(p1_\w+|_start)',symbols)}
    for label in ['_start','p1_algorithm_begin','p1_algorithm_end','p1_halt']:
        if label not in addresses:
            raise ValueError(f'missing assembler symbol {label}')
    if addresses['_start'] != 0:
        raise ValueError('expected official assembler text offsets from zero')
    addresses = {name:addr+0x80000000 for name,addr in addresses.items()}
    imem = read_words(HERE/'p1_imem.hex')
    used=(addresses['p1_halt']-0x80000000)//4+1
    if any((w & 3)!=3 for w in imem[:used]):
        raise ValueError('unexpected compressed/non-instruction word in program')
    expected={'graph':g, 'dist':reference(graph_matrix(g),g['source']),
              'unreachable_parent':NO_EDGE, 'done':DONE, 'executed_id':EXEC_ID,
              'layout':{'base':BASE,'matrix':MATRIX,'dist':DIST,'visited':VISITED,'parent':PARENT},
              'assembler':version,'assembler_sha256':sha(args.rv32),
              'assembler_origin':0,'hardware_reset':0x80000000,
              'boot_relocation':'PC bit31 selects DMEM=0 or 0x20000000; mtvec rebased; branches are PC-relative',
              'release_url':'https://github.com/A-Eren/rv32_emulator/releases/tag/v1.1.0',
              'release_zip_sha256':'1e3b27d7cae98994af05cf89a4e5cee13c97da9b95b3b92248c42538e4d5244f',
              'symbols':addresses,'program_bytes':used*4,
              'sha256':{name:sha(HERE/name) for name in ['p1_dijkstra.s','graph_n7.json','p1_imem.hex','p1_dmem_n7.hex']},
              'verification':{'xsim':'NOT RUN; separate approval required','synthesis':'NOT RUN'}}
    (HERE/'expected_n7.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8')
    print(f'BUILD OK: {used*4} code bytes; both images {WORDS} words; done initially zero')


def emulator(args):
    work, board = setup(args)
    manifest=json.loads((HERE/'expected_n7.json').read_text(encoding='utf-8'))
    for name,digest in manifest['sha256'].items():
        if sha(HERE/name)!=digest:
            raise ValueError(f'build hash mismatch: {name}')
    words=read_words(HERE/'p1_dmem_n7.hex')
    # Official debugger accepts source, not a separate initial data image.
    # Append the exact DMEM words to identical firmware text in work only.
    combined=work/'p1_emulator_input.s'
    combined.write_text((HERE/'p1_dijkstra.s').read_text(encoding='utf-8')+
                        '\n.data\n'+''.join(f'.word 0x{w:08x}\n' for w in words),encoding='utf-8')
    invoke(args.rv32,['asm',combined,'--devices',board,'--pad','-o',work/'combined_imem.hex',
                     '--dmem',work/'combined_dmem.hex'],work,'combined_assemble.log')
    if read_words(work/'combined_imem.hex')!=read_words(HERE/'p1_imem.hex') or read_words(work/'combined_dmem.hex')!=words:
        raise ValueError('emulator program/data differ from deliverable images')
    commands='break p1_halt\ncontinue\nx/8xw 0x00000000\n'
    for offset in [DIST,VISITED,PARENT]:
        commands+=f'x/64xw 0x{offset:08x}\n'
    commands+='quit\n'
    log=invoke(args.rv32,['dbg',combined,'--devices',board],work,'emulator.log',commands)
    if 'breakpoint' not in log.lower() or 'TRAP:' in log:
        raise ValueError('debugger did not reach a normal completion')
    values={}
    for line in log.splitlines():
        match=re.match(r'^(?:0x)?([0-9a-fA-F]{8}):\s+(.*?)\s+\|',line)
        if match:
            address=int(match[1],16)
            for i,value in enumerate(re.findall(r'\b(?:0x)?([0-9a-fA-F]{8})\b',match[2])):
                values[address+4*i]=int(value,16)
    for offset,count in [(0,8),(DIST,64),(VISITED,64),(PARENT,64)]:
        for i in range(count):
            address=offset+4*i
            if address not in values:
                raise ValueError(f'debugger output missing address {address:08x}')
            words[address//4]=values[address]
    # Read the matrix from actual machine memory too, rather than assuming unchanged input.
    matrix_cmd=f'break p1_halt\ncontinue\nx/{manifest["graph"]["n"]**2}xw 0x00000100\nquit\n'
    matrix_log=invoke(args.rv32,['dbg',combined,'--devices',board],work,'emulator_matrix.log',matrix_cmd)
    matrix_values=[]
    for line in matrix_log.splitlines():
        match=re.match(r'^(?:0x)?([0-9a-fA-F]{8}):\s+(.*?)\s+\|',line)
        if match:matrix_values.extend(int(v,16) for v in re.findall(r'\b(?:0x)?([0-9a-fA-F]{8})\b',match[2]))
    if len(matrix_values)!=manifest['graph']['n']**2:
        raise ValueError('actual matrix dump incomplete')
    words[MATRIX//4:MATRIX//4+len(matrix_values)]=matrix_values
    result=verify_result(manifest['graph'],words)
    write_words(work/'emulator_result.hex',words)
    (work/'emulator_result.json').write_text(json.dumps(result,indent=2)+'\n')
    manifest['verification']['official_emulator']={
        'result':'FUNCTIONAL PASS', 'actual':result,
        'same_imem_and_dmem_words_verified':True,
        'address_map':'emulator origin 0; firmware selects DMEM 0',
        'performance':'not cycle accurate; no FPGA metrics measured'}
    (HERE/'expected_n7.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    print('EMULATOR FUNCTIONAL PASS:',json.dumps(result))
    print('No FPGA cycle/resource measurement and no XSim run performed.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['build','emulator','verify'])
    parser.add_argument('--rv32',type=pathlib.Path)
    parser.add_argument('--work',type=pathlib.Path)
    parser.add_argument('--graph',type=pathlib.Path,default=HERE/'graph_n7.json')
    parser.add_argument('--dump',type=pathlib.Path)
    args=parser.parse_args()
    try:
        if args.action=='verify':
            if not args.dump:raise ValueError('--dump required')
            result=verify_result(json.loads(args.graph.read_text()),read_words(args.dump))
            print('RESULT PASS:',json.dumps(result))
        else:
            if not args.rv32 or not args.work:raise ValueError('--rv32 and --work required')
            args.rv32=args.rv32.resolve()
            (build if args.action=='build' else emulator)(args)
    except (ValueError,OSError,subprocess.TimeoutExpired) as error:
        print('FAIL:',error,file=sys.stderr)
        return 1
    return 0


if __name__=='__main__':
    sys.exit(main())
