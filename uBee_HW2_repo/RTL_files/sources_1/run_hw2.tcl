# Portable adaptation of the recorded Vivado2025.2 flow.
# New-path Vivado execution has NOT been tested; see README.md.
# argv: PROFILE PHASE OUTPUT_ROOT; phase=n7|correctness|performance|synthesis.
set hw2_package [file normalize [file join [file dirname [info script]] ../..]]
proc hw2_run {} {
 global argv hw2_package
 if {[llength $argv]!=3} {error {Expected: PROFILE PHASE OUTPUT_ROOT}}
 lassign $argv profile phase work_root
 if {$profile eq {P4}} {error {P4 excluded: original RTL is unsupported by XSim2025.2; no core patch permitted}}
 set profiles [dict create P1 {1 128 0 5 16384} P2 {1 32 0 5 16384} P3 {1 256 0 5 16384} P5 {0 128 0 5 16384} P6 {1 128 0 5 8192}]
 if {![dict exists $profiles $profile] || $phase ni {n7 correctness performance synthesis}} {error {Unknown profile/phase}}
 if {$phase eq {n7} && $profile ne {P1}} {error {n7 validation is defined for P1}}
 set work_root [file normalize $work_root]
 if {[regexp {\s} "$hw2_package$work_root"]} {error {Use package/output paths without spaces, matching the recorded XSim plusarg flow}}
 if {[string first [string tolower "$hw2_package/"] [string tolower "$work_root/"]]==0} {error {Output root must be outside Homework_N}}
 if {[llength [get_projects -quiet]]} {error {Close the current project before running this script}}
 set base [file join $work_root $profile]
 set evidence [file join $base $phase]
 if {[file exists $evidence]} {error {Evidence directory exists: choose a fresh output root; do not overwrite results}}
 if {$phase eq {performance} && ![file exists [file join $base correctness host_accept.json]]} {error {Run and host-verify correctness first}}
 if {$phase eq {synthesis} && ![file exists [file join $base performance host_accept.json]]} {error {Run and host-verify performance first}}
 set project_dir [file join $base project]
 set name EHB326E-HW2-Dijkstra
 set xpr [file join $project_dir ${name}.xpr]
 if {![file exists $xpr]} {
  if {$phase in {performance synthesis}} {error {A verified project is required}}
  create_project $name $project_dir -part xc7a100tcsg324-1
  set_property ip_repo_paths [list [file join $hw2_package IP]] [current_project]
  update_ip_catalog
  set parent [file join $project_dir ${name}.srcs sources_1]
  file mkdir $parent
  file copy [file join $hw2_package RTL_files sources_1 bd] $parent
  add_files -norecurse [file join $parent bd design_1 design_1.bd]
 } else {open_project $xpr}
 if {[get_property PART [current_project]] ne {xc7a100tcsg324-1}} {error {Wrong FPGA part}}
 set bd [get_files design_1.bd]
 open_bd_design $bd
 set soc [get_bd_cells uBee_soc_0]
 lassign [dict get $profiles $profile] enabled entries gshare history words
 set data [file join $hw2_package compiled_assembly_files]
 set_property -dict [list CONFIG.BP_ENABLE $enabled CONFIG.BP_ENTRIES $entries CONFIG.BP_GSHARE $gshare CONFIG.GHR_WIDTH $history CONFIG.DMEM_WORDS $words CONFIG.IMEM_INIT_FILE [file join $data p1_imem.hex] CONFIG.DMEM_INIT_FILE [file join $data p1_dmem_n32.hex]] $soc
 validate_bd_design
 save_bd_design
 set_property synth_checkpoint_mode None $bd
 generate_target all $bd
 set wrapper [make_wrapper -files $bd -top]
 add_files -norecurse $wrapper
 set_property top design_1_wrapper [get_filesets sources_1]
 update_compile_order -fileset sources_1
 file mkdir $evidence
 set f [open [file join $evidence preflight.txt] w]
 puts $f "PART=[get_property PART [current_project]]"
 puts $f "TOP=[get_property TOP [get_filesets sources_1]]"
 puts $f {AFTER:}
 foreach p [lsort [list_property $soc]] {if {[string match CONFIG.* $p]} {puts $f "$p=[get_property $p $soc]"}}
 close $f
 if {$phase eq {synthesis}} {
  launch_runs synth_1 -jobs 4
  wait_on_run synth_1
  if {![string match {*Complete*} [get_property STATUS [get_runs synth_1]]]} {error {Synthesis failed}}
  open_run synth_1
  report_utilization -file [file join $evidence utilization.rpt]
  report_utilization -hierarchical -file [file join $evidence utilization_hierarchical.rpt]
  report_clocks -file [file join $evidence clocks.rpt]
  set f [open [file join $evidence completion.txt] w]
  puts $f "PART=[get_property PART [current_project]]"
  puts $f "STATUS=[get_property STATUS [get_runs synth_1]]"
  puts $f "BLACKBOXES=[get_cells -hier -quiet -filter {IS_BLACKBOX == 1}]"
  close $f
 } else {
  set fs sim_hw2_$phase
  create_fileset -simset $fs
  set_property SOURCE_SET sources_1 [get_filesets $fs]
  set top tb_design_1_dijkstra
  set source tb_design_1_dijkstra.sv
  if {$phase eq {performance}} {
   set top tb_design_1_dijkstra_perf
   set source tb_design_1_dijkstra_perf.sv
   if {$profile eq {P5}} {set source tb_design_1_dijkstra_bp_optional.sv}
   if {$profile eq {P6}} {set source tb_design_1_dijkstra_perf_dmem8k.sv}
  } elseif {$profile eq {P6}} {set source tb_design_1_dijkstra_dmem8k.sv}
  add_files -fileset $fs -norecurse [file join $hw2_package RTL_files sim_1 $source]
  set dmem p1_dmem_n32.hex
  if {$phase eq {n7}} {set dmem p1_dmem_n7.hex}
  set opts [format {-testplusarg P1_IMEM=%s -testplusarg P1_DMEM=%s} [file join $data p1_imem.hex] [file join $data $dmem]]
  if {$phase eq {performance}} {append opts [format { -testplusarg P1_PERF_LOG=%s -testplusarg P1_TRACE_LOG=%s} [file join $evidence p1_perf_n32.log] [file join $evidence p1_perf_n32_trace.csv]]}
  set_property -dict [list top $top top_auto_set false xsim.simulate.runtime all xsim.simulate.xsim.more_options $opts] [get_filesets $fs]
  current_fileset -simset $fs
  update_compile_order -fileset $fs
  launch_simulation -simset $fs -mode behavioral
  source [file join $hw2_package RTL_files sources_1 observe_results.tcl]
  close_sim
  foreach filename {simulate.log compile.log elaborate.log xvlog.log xvhdl.log} {
   set src [file join $project_dir ${name}.sim $fs behav xsim $filename]
   if {[file exists $src]} {file copy $src [file join $evidence $filename]}
  }
 }
 close_project
 puts "HW2 $profile $phase returned: host verification required; no automatic PASS claim"
}
hw2_run
