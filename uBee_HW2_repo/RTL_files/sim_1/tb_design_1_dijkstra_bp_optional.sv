`timescale 1ns/1ps
// Stage 3A measurement copy. Original correctness bench and assembly unchanged.
// Existing design_1_wrapper and all core/IP sources remain unchanged.
// Supply absolute paths via +P1_IMEM=<path> +P1_DMEM=<path>, or parameters.
// Hierarchical $readmemh is simulation initialization, NOT an IMEM write port.
// This bench checks two reset/load/run passes; it is not a timing benchmark.
`define P1_SOC  dut.design_1_i.uBee_soc_0.inst
`define P1_CORE `P1_SOC.u_top.u_core
`define P1_IMEM `P1_SOC.u_imem.u_bram.memory_q
`define P1_DMEM `P1_SOC.u_dmem.u_bram.memory_q

module tb_design_1_dijkstra_perf #(
    parameter string IMEM_FILE = "p1_imem.hex",
    parameter string DMEM_FILE = "p1_dmem_n7.hex",
    parameter integer RESET_CYCLES = 20000,
    parameter integer TIMEOUT_CYCLES = 2000000
);
    localparam integer WORDS=16384, MAX_N=64;
    localparam integer MATRIX=64, DIST=4160, VISITED=4224, PARENT=4288;
    localparam logic [31:0] INF=32'h7fffffff, NONE=32'hffffffff;
    localparam logic [31:0] DONE=32'h444f4e45, EXEC_ID=32'h44494a31;
    logic clk_100MHz=0, reset_0=1;
    wire uart_txd;
    always #5 clk_100MHz=~clk_100MHz;

    design_1_wrapper dut (
        .clk_in1_0(clk_100MHz), .reset_0(reset_0),
        .UART_0_rxd(1'b1), .UART_0_txd(uart_txd)
    );

    logic [31:0] imem_ref[0:WORDS-1], dmem_ref[0:WORDS-1];
    longint unsigned shortest[0:MAX_N-1][0:MAX_N-1];
    integer n, source_node, retired_seen=0;
    string imem_path, dmem_path;

    // TRACE_ENABLE is already 1 in the existing P1 IP. No parameter change.
    // Check actual retired PC/instruction against the loaded IMEM image.
    always @(posedge `P1_SOC.clk_i) begin : trace_check
        integer wi;
        if (reset_0) retired_seen=0;
        else if (`P1_SOC.trace_valid_o === 1'b1) begin
            if (retired_seen == 0 && `P1_SOC.trace_pc_o !== 32'h80000000)
                $fatal(1,"P1 first retired PC is not the hardware reset vector");
            if ($isunknown(`P1_SOC.trace_pc_o) ||
                `P1_SOC.trace_pc_o < 32'h80000000 ||
                `P1_SOC.trace_pc_o >= 32'h80010000 ||
                `P1_SOC.trace_pc_o[1:0] != 0)
                $fatal(1,"P1 unexpected retired PC");
            wi=(`P1_SOC.trace_pc_o-32'h80000000)>>2;
            if (`P1_SOC.trace_instruction_o !== imem_ref[wi] ||
                imem_ref[wi][1:0] !== 2'b11)
                $fatal(1,"P1 retired instruction differs from Dijkstra image at word %0d",wi);
            retired_seen=retired_seen+1;
        end
    end

    task automatic read_reference;
        integer f, i, j, k;
        longint unsigned candidate;
        begin
            imem_path=IMEM_FILE;
            dmem_path=DMEM_FILE;
            if ($value$plusargs("P1_IMEM=%s",imem_path)) begin end
            if ($value$plusargs("P1_DMEM=%s",dmem_path)) begin end
            f=$fopen(imem_path,"r");
            if (!f) $fatal(1,"P1 cannot open IMEM: %s",imem_path);
            $fclose(f);
            f=$fopen(dmem_path,"r");
            if (!f) $fatal(1,"P1 cannot open DMEM: %s",dmem_path);
            $fclose(f);
            for (i=0;i<WORDS;i=i+1) begin
                imem_ref[i]='x;
                dmem_ref[i]='x;
            end
            $readmemh(imem_path,imem_ref);
            $readmemh(dmem_path,dmem_ref);
            for (i=0;i<WORDS;i=i+1)
                if ($isunknown(imem_ref[i]) || $isunknown(dmem_ref[i]))
                    $fatal(1,"P1 missing/unknown image word %0d",i);
            n=dmem_ref[1];
            source_node=dmem_ref[2];
            if (dmem_ref[0] !== 32'h5031444a || n<1 || n>MAX_N ||
                source_node<0 || source_node>=n ||
                dmem_ref[3] !== NONE || dmem_ref[4] !== INF ||
                dmem_ref[5] !== 0 || dmem_ref[6] !== 0 || dmem_ref[7] !== 0)
                $fatal(1,"P1 invalid graph header or nonzero completion fields");
            // Independent Floyd-Warshall reference, not firmware's Dijkstra.
            for (i=0;i<n;i=i+1)
                for (j=0;j<n;j=j+1) begin
                    if (dmem_ref[MATRIX+i*n+j] !== NONE &&
                        dmem_ref[MATRIX+i*n+j]>1000000)
                        $fatal(1,"P1 invalid edge weight");
                    shortest[i][j]=(dmem_ref[MATRIX+i*n+j]===NONE) ?
                                    INF : dmem_ref[MATRIX+i*n+j];
                    if (i==j) shortest[i][j]=0;
                end
            for (k=0;k<n;k=k+1)
                for (i=0;i<n;i=i+1)
                    for (j=0;j<n;j=j+1)
                        if (shortest[i][k]!=INF && shortest[k][j]!=INF) begin
                            candidate=shortest[i][k]+shortest[k][j];
                            if (candidate<shortest[i][j]) shortest[i][j]=candidate;
                        end
        end
    endtask

    task automatic load_images;
        integer i;
        begin
            if (reset_0 !== 1'b1) $fatal(1,"P1 load requires active reset");
            $readmemh(imem_path,`P1_IMEM);
            $readmemh(dmem_path,`P1_DMEM);
            for (i=0;i<WORDS;i=i+1) begin
                if (`P1_IMEM[i] !== imem_ref[i]) $fatal(1,"P1 IMEM load mismatch %0d",i);
                if (`P1_DMEM[i] !== dmem_ref[i]) $fatal(1,"P1 DMEM load mismatch %0d",i);
            end
            // Poison outputs: prove initialization is performed by the CPU.
            for (i=0;i<n;i=i+1) begin
                `P1_DMEM[DIST+i]=32'hdeadbeef;
                `P1_DMEM[VISITED+i]=32'hdeadbeef;
                `P1_DMEM[PARENT+i]=32'hdeadbeef;
            end
        end
    endtask

    task automatic check_results;
        integer v, current, p, hops, i;
        longint unsigned path_cost;
        logic [63:0] seen;
        begin
            if (`P1_DMEM[5] !== DONE || `P1_DMEM[6] !== 0 ||
                `P1_DMEM[7] !== EXEC_ID || retired_seen<10)
                $fatal(1,"P1 completion/status/executed_id/trace check failed");
            for (i=0;i<5;i=i+1)
                if (`P1_DMEM[i] !== dmem_ref[i]) $fatal(1,"P1 input header modified");
            for (i=0;i<n*n;i=i+1)
                if (`P1_DMEM[MATRIX+i] !== dmem_ref[MATRIX+i])
                    $fatal(1,"P1 input matrix modified");
            for (v=0;v<n;v=v+1) begin
                if (`P1_DMEM[DIST+v] !== shortest[source_node][v][31:0])
                    $fatal(1,"P1 dist[%0d] mismatch actual=%0d expected=%0d",
                           v,`P1_DMEM[DIST+v],shortest[source_node][v]);
                if (shortest[source_node][v]==INF) begin
                    if (`P1_DMEM[PARENT+v] !== NONE || `P1_DMEM[VISITED+v] !== 0)
                        $fatal(1,"P1 unreachable node %0d has invalid parent/visited",v);
                end else begin
                    if (`P1_DMEM[VISITED+v] !== 1)
                        $fatal(1,"P1 reachable node %0d not visited",v);
                    if (v==source_node && `P1_DMEM[PARENT+v] !== NONE)
                        $fatal(1,"P1 source parent must be NONE");
                    current=v;
                    hops=0;
                    seen=0;
                    path_cost=0;
                    while (current!=source_node) begin
                        if (current<0 || current>=n || hops>=n)
                            $fatal(1,"P1 parent chain outside graph");
                        if (seen[current]) $fatal(1,"P1 cyclic parent chain");
                        seen[current]=1;
                        if ($isunknown(`P1_DMEM[PARENT+current]) ||
                            `P1_DMEM[PARENT+current]>=n)
                            $fatal(1,"P1 invalid parent at %0d",current);
                        p=`P1_DMEM[PARENT+current];
                        if (dmem_ref[MATRIX+p*n+current]===NONE)
                            $fatal(1,"P1 parent edge absent");
                        path_cost=path_cost+dmem_ref[MATRIX+p*n+current];
                        current=p;
                        hops=hops+1;
                    end
                    if (path_cost!=shortest[source_node][v])
                        $fatal(1,"P1 parent path cost mismatch at %0d",v);
                end
                $display("P1 node=%0d dist=%0d parent=%08x visited=%0d",v,
                         `P1_DMEM[DIST+v],`P1_DMEM[PARENT+v],`P1_DMEM[VISITED+v]);
            end
        end
    endtask

    // Stage 3A: observation only; original assembly and correctness bench preserved.
    // Main interval: first accepted IMEM request of BEGIN through the edge
    // retiring the actual exit branch, both edges inclusive. No done/halt timing.
    localparam logic [31:0] ALG_BEGIN=32'h8000011c, ALG_END=32'h800001d0;
    integer perf_fd, trace_fd, perf_pass=0;
    string perf_path, trace_path;
    bit measuring=0, perf_done=0;
    longint unsigned core_edge=0, start_edge, first_issue_edge, first_ex_edge;
    longint unsigned first_retire_edge, last_retire_edge, start_mcycle, start_instret;
    longint unsigned all_retired, algo_retired, outside_retired;
    longint unsigned branches,taken,correct,miss,decoded_branches,decoded_taken,decoded_correct,decoded_miss;
    longint unsigned algo_branches,algo_taken,algo_correct,algo_miss;
    longint unsigned cycles,raw_retired,edge_cycles,time_cycles,fetch_begin_count;
    realtime start_time, end_time;
    initial begin
        perf_path="p1_perf_n7.log";trace_path="p1_perf_n7_trace.csv";
        if ($value$plusargs("P1_PERF_LOG=%s",perf_path)) begin end
        if ($value$plusargs("P1_TRACE_LOG=%s",trace_path)) begin end
        perf_fd=$fopen(perf_path,"w");trace_fd=$fopen(trace_path,"w");
        if(!perf_fd || !trace_fd) $fatal(1,"Cannot open performance evidence files");
        $fdisplay(trace_fd,"pass,edge,pc,instruction,branch,taken,correct,miss,scope");
    end
    task automatic reset_performance;
        begin
            perf_pass=perf_pass+1;measuring=0;perf_done=0;
            first_issue_edge=0;first_ex_edge=0;first_retire_edge=0;last_retire_edge=0;
            all_retired=0;algo_retired=0;outside_retired=0;fetch_begin_count=0;
            branches=0;taken=0;correct=0;miss=0;
            decoded_branches=0;decoded_taken=0;decoded_correct=0;decoded_miss=0;
            algo_branches=0;algo_taken=0;algo_correct=0;algo_miss=0;
        end
    endtask
    always @(posedge `P1_SOC.clk_i) begin : performance_observer
        logic in_algorithm, is_branch, bt, pcorr, pmiss, exits_algorithm;
        logic [31:0] pc, insn, branch_imm;
        core_edge=core_edge+1;
        if(!reset_0 && `P1_SOC.rst_n_sync_q) begin
            if(`P1_CORE.fetch_request_fire && `P1_CORE.imem_req_addr_o==ALG_BEGIN && !perf_done && !first_retire_edge) begin
                fetch_begin_count=fetch_begin_count+1;
                if(!measuring) begin
                    measuring=1;start_edge=core_edge;start_time=$realtime;
                    start_mcycle={`P1_SOC.dbg_csr_mcycleh_o,`P1_SOC.dbg_csr_mcycle_o};
                    start_instret={`P1_SOC.dbg_csr_minstreth_o,`P1_SOC.dbg_csr_minstret_o};
                    $display("3A START pass=%0d edge=%0d time_ps=%0t first_algorithm_fetch=%08x",perf_pass,core_edge,$time,ALG_BEGIN);
                end
            end
            if(measuring) begin
                if(!first_issue_edge && `P1_CORE.fetch_buffer_consume && `P1_CORE.presented_pc==ALG_BEGIN)
                    first_issue_edge=core_edge;
                if(!first_ex_edge && `P1_CORE.id_ex_valid_q && `P1_CORE.id_ex_pc_q==ALG_BEGIN)
                    first_ex_edge=core_edge;
                if(`P1_SOC.trace_valid_o && `P1_SOC.trace_trap_o)
                    $fatal(1,"Unexpected trap inside 3A measurement interval");
                branches=branches+`P1_SOC.monitor_perf_events.branch;
                taken=taken+`P1_SOC.monitor_perf_events.branch_taken;
                correct=correct+`P1_SOC.monitor_perf_events.prediction_correct;
                miss=miss+`P1_SOC.monitor_perf_events.mispredict;
                if(`P1_SOC.trace_valid_o && !`P1_SOC.trace_trap_o) begin
                    pc=`P1_SOC.trace_pc_o;insn=`P1_SOC.trace_instruction_o;
                    in_algorithm=(pc>=ALG_BEGIN && pc<ALG_END);
                    is_branch=(insn[6:0]==7'h63);
                    bt=is_branch && `P1_CORE.mem_wb_branch_taken_q;
                    pcorr=is_branch && `P1_CORE.mem_wb_prediction_correct_q;
                    pmiss=is_branch && `P1_CORE.mem_wb_prediction_mispredict_q;
                    all_retired=all_retired+1;
                    decoded_branches=decoded_branches+is_branch;
                    decoded_taken=decoded_taken+bt;
                    decoded_correct=decoded_correct+pcorr;
                    decoded_miss=decoded_miss+pmiss;
                    if(in_algorithm) begin
                        algo_retired=algo_retired+1;
                        algo_branches=algo_branches+is_branch;algo_taken=algo_taken+bt;
                        algo_correct=algo_correct+pcorr;algo_miss=algo_miss+pmiss;
                        if(!first_retire_edge) begin
                            if(pc!=ALG_BEGIN) $fatal(1,"First algorithm retirement is not BEGIN");
                            first_retire_edge=core_edge;
                        end
                    end else outside_retired=outside_retired+1;
                    $fdisplay(trace_fd,"%0d,%0d,%08x,%08x,%0d,%0d,%0d,%0d,%0d",perf_pass,core_edge,pc,insn,is_branch,bt,pcorr,pmiss,in_algorithm);
                    branch_imm={{19{insn[31]}},insn[31],insn[7],insn[30:25],insn[11:8],1'b0};
                    exits_algorithm=in_algorithm && is_branch &&
                        ((bt && pc+branch_imm==ALG_END) || (!bt && pc+4==ALG_END));
                    if(exits_algorithm) begin
                        last_retire_edge=core_edge;end_time=$realtime;
                        // Wait only for this edge's NBA CSR updates, never another clock.
                        #1ps;
                        cycles={`P1_SOC.dbg_csr_mcycleh_o,`P1_SOC.dbg_csr_mcycle_o}-start_mcycle;
                        raw_retired={`P1_SOC.dbg_csr_minstreth_o,`P1_SOC.dbg_csr_minstret_o}-start_instret;
                        edge_cycles=last_retire_edge-start_edge+1;
                        time_cycles=$rtoi((end_time-start_time)/10.0)+1;
                        if(cycles!=edge_cycles || cycles!=time_cycles)
                            $fatal(1,"Cycle cross-check failed");
                        if(raw_retired!=all_retired || raw_retired!=algo_retired+outside_retired)
                            $fatal(1,"minstret/trace reconciliation failed");
                        if(branches!=decoded_branches || taken!=decoded_taken || correct!=decoded_correct || miss!=decoded_miss)
                            $fatal(1,"Monitor-event versus trace branch check failed");
                        // Disabled RTL gates prediction events off; do not call this perfect prediction.
                        if (`P1_CORE.BP_ENABLE) begin
                            if(correct+miss!=branches || algo_correct+algo_miss!=algo_branches)
                                $fatal(1,"Enabled predictor coverage check failed");
                        end else if(correct!=0 || miss!=0 || algo_correct!=0 || algo_miss!=0)
                            $fatal(1,"Disabled predictor produced prediction events");
                        if(!(start_edge<first_issue_edge && first_issue_edge<=first_ex_edge && first_ex_edge<first_retire_edge))
                            $fatal(1,"First instruction full-latency inclusion check failed");
                        if(fetch_begin_count!=1) $fatal(1,"Ambiguous/speculative BEGIN fetch: inspect boundary");
                        $fdisplay(perf_fd,"METRIC pass=%0d cycles=%0d edge_cycles=%0d time_cycles=%0d raw_retired=%0d all_retired=%0d algo_retired=%0d outside_retired=%0d branches=%0d taken=%0d correct=%0d miss=%0d decoded_branches=%0d decoded_taken=%0d decoded_correct=%0d decoded_miss=%0d algo_branches=%0d algo_taken=%0d algo_correct=%0d algo_miss=%0d first_fetch_edge=%0d first_issue_edge=%0d first_ex_edge=%0d first_retire_edge=%0d last_retire_edge=%0d",perf_pass,cycles,edge_cycles,time_cycles,raw_retired,all_retired,algo_retired,outside_retired,branches,taken,correct,miss,decoded_branches,decoded_taken,decoded_correct,decoded_miss,algo_branches,algo_taken,algo_correct,algo_miss,start_edge,first_issue_edge,first_ex_edge,first_retire_edge,last_retire_edge);
                        $fflush(perf_fd);$fflush(trace_fd);
                        $display("3A METRICS pass=%0d cycles=%0d raw_minstret=%0d algorithm_instructions=%0d outside_tail=%0d branches=%0d miss=%0d",perf_pass,cycles,raw_retired,algo_retired,outside_retired,algo_branches,algo_miss);
                        perf_done=1;measuring=0;
                    end
                end
            end
        end
    end

    initial begin : main
        integer pass_id, elapsed_cycles;
        // Avoid a time-zero race with IP initial $readmemh of the Hello image.
        #1;
        read_reference();
        for (pass_id=1;pass_id<=2;pass_id=pass_id+1) begin
            reset_0=1;
            // On the second pass let the core's reset synchronizer settle.
            repeat (20) @(negedge clk_100MHz);
            #1;
            reset_performance();
            load_images();
            repeat (RESET_CYCLES) @(negedge clk_100MHz);
            reset_0=0;
            elapsed_cycles=0;
            while (`P1_DMEM[5] !== DONE && elapsed_cycles<TIMEOUT_CYCLES) begin
                @(negedge clk_100MHz);
                elapsed_cycles=elapsed_cycles+1;
            end
            if (`P1_DMEM[5] !== DONE) $fatal(1,"P1 timeout on reset pass %0d",pass_id);
            check_results();
            if(!perf_done) $fatal(1,"Measurement window did not complete");
            $display("P1 reset pass %0d OK (input-clock timeout ticks=%0d; NOT algorithm cycles)",
                     pass_id,elapsed_cycles);
        end
        $display("PASS: tb_design_1_dijkstra_perf (results, parent paths, unreachable nodes, two resets)");
        $finish;
    end
endmodule
`undef P1_CORE
`undef P1_SOC
`undef P1_IMEM
`undef P1_DMEM
