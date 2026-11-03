file mkdir $evidence
set f [open [file join $evidence rtl_observation.txt] w]
set soc /$top/dut/design_1_i/uBee_soc_0/inst
foreach {name suffix} {
 S0_DMEM_BASE {u_top/u_core/u_regfile/normal_registers_q[8]}
 SP {u_top/u_core/u_regfile/normal_registers_q[2]}
 MTVEC {u_top/u_core/u_csr_trap/mtvec_q}
 DONE {u_dmem/u_bram/memory_q[5]}
 STATUS {u_dmem/u_bram/memory_q[6]}
 EXECUTED_ID {u_dmem/u_bram/memory_q[7]}
} {
 set value [get_value -radix hex $soc/$suffix]
 puts $f "$name = $value"
 puts "$name = $value"
}
close $f
