# EHB326E HW2 — Dijkstra on microBee

Arty A7-100 (`xc7a100tcsg324-1`), Vivado/XSim 2025.2. Fixed n32 benchmark; no MCDM or final profile selection.

P1, P2, P3, P5 and P6 were measured. P4 has no quantitative result: original gshare RTL cannot elaborate in XSim 2025.2. No modified core is included. P5 prediction accuracy is unavailable. P6 uses 8192 DMEM words; the fixed program does not use the stack.

The official IP files are copied unchanged. The portable Vivado Tcl adapter is based on the previously verified workflow but has **not** been executed in a clean Vivado project. Host image rebuild and checks were previously verified; synthesis is not timing closure or board execution.

## Rebuild and run

Use Python 3 and the official Windows rv32 1.1.0 distribution. Run from this repository root:

```text
python -B compiled_assembly_files/rebuild_images.py --rv32 <rv32.exe> --out <fresh_external_directory>
```

For Vivado, close the current project and use the Tcl console. The new adapter requires a fresh output directory outside this repository and paths without spaces:

```tcl
set argv [list P1 n7 <external_output_root>]
source ./RTL_files/sources_1/run_hw2.tcl
```

For n32 use phases `correctness`, `performance`, and `synthesis`, host-verifying each phase before the next:

```text
python -B compiled_assembly_files/verify_experiment.py P1 correctness --out <external_output_root>
```

Replace the profile and phase as appropriate. `profiles.json` records the profile settings. See the limitations above before relying on the untested adapter.

## Files

- `compiled_assembly_files/benchmark_n32_edges.csv` — Benchmark edge endpoints and weights.
- `compiled_assembly_files/check_p1.py` — Image builder and independent correctness checks.
- `compiled_assembly_files/check_p1_n32_experiment.py` — n32 correctness and measurement evidence checker.
- `compiled_assembly_files/check_p1_performance.py` — Cycle-window and retirement-trace checks.
- `compiled_assembly_files/comparison.csv` — Previously measured profile results; P4 has no measurements.
- `compiled_assembly_files/expected_n32.json` — 32-node reference results, image hashes and symbols.
- `compiled_assembly_files/expected_n7.json` — Seven-node reference results and image hashes.
- `compiled_assembly_files/graph_n32.json` — Deterministic 4×8 benchmark graph.
- `compiled_assembly_files/graph_n7.json` — Seven-node graph, including a disconnected node.
- `compiled_assembly_files/p1_dijkstra.s` — Dijkstra assembly program, shared by all measured profiles.
- `compiled_assembly_files/p1_dmem_n32.hex` — Fixed 32-node benchmark data image.
- `compiled_assembly_files/p1_dmem_n7.hex` — Seven-node validation data image.
- `compiled_assembly_files/p1_imem.hex` — Initial instruction memory image.
- `compiled_assembly_files/prediction_capability.py` — Prediction-disabled event verification used for P5.
- `compiled_assembly_files/prepare_n32_benchmark.py` — Deterministic graph and n32 image generator.
- `compiled_assembly_files/profiles.json` — Parameters for P1–P6; P4 is excluded from measured results.
- `compiled_assembly_files/rebuild_images.py` — Rebuilds and checks images in a fresh external directory.
- `compiled_assembly_files/reference_soc_config.json` — Reference SoC settings used by the experiment.
- `compiled_assembly_files/rv32_trace_reference.py` — Independent functional RV32 instruction-trace reference.
- `compiled_assembly_files/verify_experiment.py` — Host checker for externally generated experiment evidence.
- `IP/uBee_soc/component.xml` — Original uBee SoC IP packaging definition.
- `IP/uBee_soc/src/uBee_alu.sv` — Unmodified official microBee RTL module/header: uBee_alu.
- `IP/uBee_soc/src/uBee_branch_compare.sv` — Unmodified official microBee RTL module/header: uBee_branch_compare.
- `IP/uBee_soc/src/uBee_branch_predictor.sv` — Unmodified official microBee RTL module/header: uBee_branch_predictor.
- `IP/uBee_soc/src/uBee_clint.sv` — Unmodified official microBee RTL module/header: uBee_clint.
- `IP/uBee_soc/src/uBee_core.sv` — Unmodified official microBee RTL module/header: uBee_core.
- `IP/uBee_soc/src/uBee_csr_trap.sv` — Unmodified official microBee RTL module/header: uBee_csr_trap.
- `IP/uBee_soc/src/uBee_decoder.sv` — Unmodified official microBee RTL module/header: uBee_decoder.
- `IP/uBee_soc/src/uBee_decompress.sv` — Unmodified official microBee RTL module/header: uBee_decompress.
- `IP/uBee_soc/src/uBee_defs.svh` — Unmodified official microBee RTL module/header: uBee_defs.
- `IP/uBee_soc/src/uBee_div.sv` — Unmodified official microBee RTL module/header: uBee_div.
- `IP/uBee_soc/src/uBee_dmem.sv` — Unmodified official microBee RTL module/header: uBee_dmem.
- `IP/uBee_soc/src/uBee_gpio.sv` — Unmodified official microBee RTL module/header: uBee_gpio.
- `IP/uBee_soc/src/uBee_hazard_unit.sv` — Unmodified official microBee RTL module/header: uBee_hazard_unit.
- `IP/uBee_soc/src/uBee_imem.sv` — Unmodified official microBee RTL module/header: uBee_imem.
- `IP/uBee_soc/src/uBee_immediate_gen.sv` — Unmodified official microBee RTL module/header: uBee_immediate_gen.
- `IP/uBee_soc/src/uBee_monitor.sv` — Unmodified official microBee RTL module/header: uBee_monitor.
- `IP/uBee_soc/src/uBee_monitor_regs.svh` — Unmodified official microBee RTL module/header: uBee_monitor_regs.
- `IP/uBee_soc/src/uBee_mul.sv` — Unmodified official microBee RTL module/header: uBee_mul.
- `IP/uBee_soc/src/uBee_native_bram.sv` — Unmodified official microBee RTL module/header: uBee_native_bram.
- `IP/uBee_soc/src/uBee_native_to_axi4lite.sv` — Unmodified official microBee RTL module/header: uBee_native_to_axi4lite.
- `IP/uBee_soc/src/uBee_perf_events.svh` — Unmodified official microBee RTL module/header: uBee_perf_events.
- `IP/uBee_soc/src/uBee_perf_probe.sv` — Unmodified official microBee RTL module/header: uBee_perf_probe.
- `IP/uBee_soc/src/uBee_plic.sv` — Unmodified official microBee RTL module/header: uBee_plic.
- `IP/uBee_soc/src/uBee_regfile.sv` — Unmodified official microBee RTL module/header: uBee_regfile.
- `IP/uBee_soc/src/uBee_request_router.sv` — Unmodified official microBee RTL module/header: uBee_request_router.
- `IP/uBee_soc/src/uBee_soc.sv` — Unmodified official microBee RTL module/header: uBee_soc.
- `IP/uBee_soc/src/uBee_timer.sv` — Unmodified official microBee RTL module/header: uBee_timer.
- `IP/uBee_soc/src/uBee_top.sv` — Unmodified official microBee RTL module/header: uBee_top.
- `IP/uBee_soc/src/uBee_uart.sv` — Unmodified official microBee RTL module/header: uBee_uart.
- `IP/uBee_soc/xgui/uBee_soc_v1_0.tcl` — Original Vivado IP configuration interface.
- `report/latex_src/figure1_microbee_architecture.pdf` — Vector diagram of the actual SoC and block-design connections.
- `report/latex_src/figure2_n32_weighted_graph.pdf` — Vector drawing of all 32 nodes and 70 weighted edges.
- `report/latex_src/figure3_performance_resources.pdf` — Vector chart of cycles and LUT/FF for measured profiles.
- `RTL_files/sim_1/tb_design_1_dijkstra.sv` — n7/n32 RTL correctness testbench.
- `RTL_files/sim_1/tb_design_1_dijkstra_bp_optional.sv` — Performance testbench adapted for prediction disabled (P5).
- `RTL_files/sim_1/tb_design_1_dijkstra_dmem8k.sv` — Correctness testbench adapted to P6’s 8192-word DMEM.
- `RTL_files/sim_1/tb_design_1_dijkstra_perf.sv` — n32 performance testbench and measurement window.
- `RTL_files/sim_1/tb_design_1_dijkstra_perf_dmem8k.sv` — Performance testbench adapted to P6’s 8192-word DMEM.
- `RTL_files/sources_1/bd/design_1/design_1.bd` — Vivado block design; image path metadata made relative.
- `RTL_files/sources_1/bd/design_1/design_1.bda` — Block-design metadata.
- `RTL_files/sources_1/bd/design_1/ip/design_1_axi_uartlite_0_0/design_1_axi_uartlite_0_0.xci` — Vivado IP instance configuration for design_1_axi_uartlite_0_0.
- `RTL_files/sources_1/bd/design_1/ip/design_1_clk_wiz_0_0/design_1_clk_wiz_0_0.xci` — Vivado IP instance configuration for design_1_clk_wiz_0_0.
- `RTL_files/sources_1/bd/design_1/ip/design_1_uBee_soc_0_0/design_1_uBee_soc_0_0.xci` — Vivado IP instance configuration for design_1_uBee_soc_0_0.
- `RTL_files/sources_1/bd/design_1/ip/design_1_util_vector_logic_0_0/design_1_util_vector_logic_0_0.xci` — Vivado IP instance configuration for design_1_util_vector_logic_0_0.
- `RTL_files/sources_1/bd/design_1/ip/design_1_xlconstant_0_0/design_1_xlconstant_0_0.xci` — Vivado IP instance configuration for design_1_xlconstant_0_0.
- `RTL_files/sources_1/bd/design_1/ip/design_1_xlconstant_1_0/design_1_xlconstant_1_0.xci` — Vivado IP instance configuration for design_1_xlconstant_1_0.
- `RTL_files/sources_1/bd/design_1/ip/design_1_xlconstant_2_0/design_1_xlconstant_2_0.xci` — Vivado IP instance configuration for design_1_xlconstant_2_0.
- `RTL_files/sources_1/bd/design_1/ui/bd_1f5defd0.ui` — Block-design diagram layout metadata.
- `RTL_files/sources_1/observe_results.tcl` — Reads completion and register observations from XSim.
- `RTL_files/sources_1/run_hw2.tcl` — Portable Vivado project/simulation/synthesis adapter; not clean-run tested.

- `README.md` — This file, experiment limits and usage guide.
- `SHA256SUMS.json` — SHA-256 hashes of repository files (excluding itself).

The final report PDF and LaTeX report text are intentionally not included yet.
