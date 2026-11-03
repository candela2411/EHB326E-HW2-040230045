# P1 classical Dijkstra, RV32IM + Zicsr (no compressed instructions).
# Harvard map: text/reset 0x80000000; data 0x20000000, 64 KiB each.
# No UART/model-specific IO, no core changes, no graph-specific distances.
# Header byte offsets: magic=0, N=4, source=8, NO_EDGE=12, INF=16,
# done=20, status=24, executed_id=28. CPU publishes done LAST.
# Matrix at +0x100: N*N row-major words, stride N (not MAX_N).
# dist +0x4100; visited +0x4200; parent +0x4300 (64 words each).
# status: 0 success; 1 invalid header/weight; 2 unexpected trap.
# done=0x444f4e45; executed_id=0x44494a31. INF=0x7fffffff.
        .text
        .globl _start
_start:
# Official rv32 v1.1.0 executes at IMEM/DMEM base zero; hardware resets
# at 0x80000000 with DMEM at 0x20000000. Select ONLY these two maps from
# PC bit31 so the exact same instruction image can be checked on both.
# The official assembler encodes text labels as offsets from zero.
        auipc   s0, 0
        srli    s0, s0, 31
        slli    s0, s0, 29
        li      t0, 0xfff0
        add     sp, s0, t0
        la      t0, p1_trap
        slli    t1, s0, 2
        or      t0, t0, t1
        csrw    mtvec, t0
        csrw    mie, zero
        sw      zero, 20(s0)
        sw      zero, 24(s0)
        li      t0, 0x44494a31
        sw      t0, 28(s0)
        lw      t0, 0(s0)
        li      t1, 0x5031444a
        bne     t0, t1, p1_bad_input
        lw      s1, 4(s0)
        beqz    s1, p1_bad_input
        li      t0, 64
        bltu    t0, s1, p1_bad_input
        lw      s2, 8(s0)
        bgeu    s2, s1, p1_bad_input
        lw      t0, 12(s0)
        li      t1, -1
        bne     t0, t1, p1_bad_input
        lw      s3, 16(s0)
        li      t0, 0x7fffffff
        bne     s3, t0, p1_bad_input
        li      t0, 0x100
        add     s4, s0, t0
        li      t0, 0x4100
        add     s5, s0, t0
        li      t0, 0x4200
        add     s6, s0, t0
        li      t0, 0x4300
        add     s7, s0, t0
# Validate all N*N weights before the algorithm. -1 means absent;
# zero is a legal weight. Accepted weights are 0..1,000,000.
        mul     t0, s1, s1
        mv      t1, s4
        li      t2, -1
        li      t3, 1000000
p1_validate_weight:
        lw      t4, 0(t1)
        beq     t4, t2, p1_weight_ok
        bltu    t3, t4, p1_bad_input
p1_weight_ok:
        addi    t1, t1, 4
        addi    t0, t0, -1
        bnez    t0, p1_validate_weight
# dist=INF, visited=0, parent=-1. No dependence on initial RAM zeros.
        li      t0, 0
        li      t5, -1
p1_init:
        slli    t1, t0, 2
        add     t2, s5, t1
        sw      s3, 0(t2)
        add     t2, s6, t1
        sw      zero, 0(t2)
        add     t2, s7, t1
        sw      t5, 0(t2)
        addi    t0, t0, 1
        bltu    t0, s1, p1_init
        slli    t0, s2, 2
        add     t0, s5, t0
        sw      zero, 0(t0)
        li      s8, 0
# Future measurement boundary: p1_algorithm_begin .. p1_algorithm_end.
# Header/weight validation, array initialization and result publication are outside.
p1_algorithm_begin:
p1_outer:
        li      s9, -1
        mv      s10, s3
        li      t0, 0
# Select the smallest finite unvisited distance, ties by lowest index.
p1_select:
        slli    t1, t0, 2
        add     t2, s6, t1
        lw      t3, 0(t2)
        bnez    t3, p1_select_next
        add     t2, s5, t1
        lw      t3, 0(t2)
        bgeu    t3, s10, p1_select_next
        mv      s10, t3
        mv      s9, t0
p1_select_next:
        addi    t0, t0, 1
        bltu    t0, s1, p1_select
        li      t0, -1
        beq     s9, t0, p1_algorithm_end
        slli    t0, s9, 2
        add     t1, s6, t0
        li      t2, 1
        sw      t2, 0(t1)
        mul     t1, s9, s1
        slli    t1, t1, 2
        add     t1, s4, t1
        li      t0, 0
# Relax row u: if not visited, edge exists, and sum is finite and smaller.
p1_relax:
        slli    t2, t0, 2
        add     t3, s6, t2
        lw      t4, 0(t3)
        bnez    t4, p1_relax_next
        lw      t4, 0(t1)
        li      t5, -1
        beq     t4, t5, p1_relax_next
        sub     t5, s3, t4
        bgeu    s10, t5, p1_relax_next
        add     t5, s10, t4
        add     t3, s5, t2
        lw      t6, 0(t3)
        bgeu    t5, t6, p1_relax_next
        sw      t5, 0(t3)
        add     t3, s7, t2
        sw      s9, 0(t3)
p1_relax_next:
        addi    t1, t1, 4
        addi    t0, t0, 1
        bltu    t0, s1, p1_relax
        addi    s8, s8, 1
        bltu    s8, s1, p1_outer
p1_algorithm_end:
        sw      zero, 24(s0)
        j       p1_publish
p1_bad_input:
        li      t0, 1
        sw      t0, 24(s0)
        j       p1_publish
p1_trap:
        auipc   s0, 0
        srli    s0, s0, 31
        slli    s0, s0, 29
        li      t0, 2
        sw      t0, 24(s0)
p1_publish:
        fence
        li      t0, 0x444f4e45
        sw      t0, 20(s0)
        fence
p1_halt:
        j       p1_halt
