"""Deterministic P1 n32 workload preparation; never rebuilds firmware or runs Vivado.
Run with Python -B. Existing n7 source/images and instrumentation are read-only.
"""
import csv,hashlib,json,pathlib
import check_p1 as p
from rv32_trace_reference import execute
HERE=pathlib.Path(__file__).resolve().parent

def make_graph():
    edges={}
    def add(r,c,rr,cc,w,family):
        u,v=sorted((8*r+c,8*rr+cc))
        if (u,v) in edges:raise ValueError('duplicate edge')
        edges[u,v]=(w,family)
    for r in range(4):
        for c in range(7):add(r,c,r,c+1,1+(5*r+3*c)%9,'horizontal')
    for r in range(3):
        for c in range(8):add(r,c,r+1,c,2+(7*r+5*c)%11,'vertical')
    for r in range(3):
        for c in range(7):
            if (r+c)%2==0:add(r,c,r+1,c+1,3+(11*r+7*c)%13,'down_right')
    for r in range(3):
        for c in range(1,8):
            if (r+c)%3==0:add(r,c,r+1,c-1,2+(3*r+11*c)%10,'down_left')
    return {'name':'P1_grid4x8_weighted_diagonals_v1','n':32,'source':0,'directed':False,
            'generation':{'version':1,'node_id':'u = 8*r+c; 0<=r<4, 0<=c<8','random_seed':None,
                'horizontal':'(r,c)-(r,c+1), c<7; w=1+((5*r+3*c)%9)',
                'vertical':'(r,c)-(r+1,c), r<3; w=2+((7*r+5*c)%11)',
                'down_right':'r<3,c<7,(r+c)%2==0; (r,c)-(r+1,c+1); w=3+((11*r+7*c)%13)',
                'down_left':'r<3,1<=c<8,(r+c)%3==0; (r,c)-(r+1,c-1); w=2+((3*r+11*c)%10)',
                'edge_order':'canonical u<v, sorted by (u,v)',
                'family_counts':{f:sum(f==family for w,family in edges.values()) for f in ['horizontal','vertical','down_right','down_left']}},
            'edges':[[u,v,w] for (u,v),(w,family) in sorted(edges.items())]}

def bellman_ford(g):
    """Independent edge-list relaxation reference, unlike matrix Dijkstra."""
    d=[p.INF]*g['n'];d[g['source']]=0
    arcs=[(u,v,w) for u,v,w in g['edges']]
    if not g['directed']:arcs += [(v,u,w) for u,v,w in g['edges']]
    for _ in range(g['n']-1):
        changed=False
        for u,v,w in arcs:
            if d[u]!=p.INF and d[u]+w<d[v]:d[v]=d[u]+w;changed=True
        if not changed:break
    return d

def main():
    old=json.loads((HERE/'expected_n7.json').read_text())
    for name,digest in old['sha256'].items():
        if p.sha(HERE/name)!=digest:raise ValueError('original n7 artifact changed: '+name)
    g=make_graph();matrix=p.graph_matrix(g)
    fw=p.reference(matrix,g['source']);bf=bellman_ford(g)
    if fw!=bf or p.INF in fw:raise ValueError('reference disagreement/unreachable node')
    words=p.initial_words(g);trace=[]
    final,_,_,steps=execute(p.read_words(HERE/'p1_imem.hex'),words,trace=trace)
    actual=p.verify_result(g,final)
    p.write_words(HERE/'p1_dmem_n32.hex',words)
    (HERE/'graph_n32.json').write_text(json.dumps(g,indent=2)+'\n')
    with (HERE/'benchmark_n32_edges.csv').open('w',newline='') as f:
        w=csv.writer(f);w.writerow(['u','v','weight']);w.writerows(g['edges'])
    e=len(g['edges']);degrees=[0]*32
    for u,v,w in g['edges']:degrees[u]+=1;degrees[v]+=1
    begin,end=[old['symbols'][s] for s in ['p1_algorithm_begin','p1_algorithm_end']]
    scoped=[t for t in trace if begin<=t['pc']<end]
    manifest={'graph':g,'dist':fw,'references':['Floyd-Warshall','Bellman-Ford'],
              'host_machine_code_result':actual,'host_algorithm_instruction_count':len(scoped),
              'host_algorithm_conditional_branches':sum(t['branch'] for t in scoped),
              'host_instructions_until_done':steps,'symbols':old['symbols'],
              'statistics':{'vertices':32,'undirected_edges':e,'possible_undirected_edges':496,
                'density':e/496,'average_degree':2*e/32,'degrees':degrees,
                'matrix_diagonal_included':False,'random_seed':None},
              'sha256':{name:p.sha(HERE/name) for name in ['p1_dijkstra.s','p1_imem.hex','p1_dmem_n32.hex','graph_n32.json','benchmark_n32_edges.csv']},
              'stage':'3B','rtl_correctness':'NOT RUN','performance':'NOT RUN','synthesis':'NOT RUN'}
    (HERE/'expected_n32.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('N32 reference preparation PASS: source0, E=',e,'density=',e/496,'families=',g['generation']['family_counts'])
    print('Independent FW = BF = host image execution:',fw)
    print('Host algorithm instructions:',len(scoped),'branches:',sum(t['branch'] for t in scoped),'(no cycle estimate)')

if __name__=='__main__':main()
