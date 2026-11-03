from check_p1_performance import require

def verify_disabled(m,trace,expected):
    """Stage3A boundaries/counts/trace checks; predictor flags must all be zero.
    Branch prediction rate is unavailable because RTL gates flags with BP_ENABLE.
    No synthetic 'correct' or 'miss' flags are added to the hardware trace.
    """
    require(m['cycles']==m['edge_cycles']==m['time_cycles'],'cycle cross-check')
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
        require(all(actual[k]==reference[k] for k in ['pc','instruction','branch','taken']),'independent execution differs from RTL trace')
    for prefix,items in [('',trace),('algo_',algo)]:
        for key in ['branches','taken','correct','miss']:
            field='branch' if key=='branches' else key
            require(m[prefix+key]==sum(t[field] for t in items),f'{prefix}{key} trace mismatch')
        require(m[prefix+'correct']==m[prefix+'miss']==0,'disabled prediction flags must be zero')
        require(all(t['correct']==t['miss']==0 for t in items),'disabled per-instruction prediction flags')
    for key in ['branches','taken','correct','miss']:
        require(m[key]==m['decoded_'+key],'monitor events differ from instruction decode')
    return True
