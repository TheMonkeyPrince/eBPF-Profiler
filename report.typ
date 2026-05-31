#set document(
  title: "Profiling the Linux BPF Verifier",
  author: ("Author Name",),
  date: datetime(year: 2026, month: 5, day: 31),
)

#set page(
  paper: "a4",
  margin: (x: 2.5cm, y: 2.5cm),
  numbering: "1",
)

#set text(
  font: "Linux Libertine",
  size: 11pt,
  lang: "en",
)

#set heading(numbering: "1.1")

#set par(justify: true, leading: 0.65em)
#show heading.where(level: 1): it => {
  pagebreak(weak: true)
  block(above: 1.5em, below: 1em)[
    #text(size: 16pt, weight: "bold")[#it.body]
  ]
}
#show heading.where(level: 2): it => block(above: 1.2em, below: 0.6em)[
  #text(size: 13pt, weight: "semibold")[#it.body]
]

#align(center)[
  #text(size: 20pt, weight: "bold")[Profiling the Linux BPF Verifier]
  #v(0.4em)
  #text(size: 14pt)[Semester Project Report]
  #v(1.2em)
  #text(size: 12pt)[
    EPFL — Master Semester Project \
    #datetime.today().display("[day]/[month]/[year]")
  ]
]

#v(2em)

= Abstract

The eBPF verifier is a static analysis engine embedded in the Linux kernel. It must prove safety properties for every loaded BPF program before execution, yet its runtime cost can reach seconds for large workloads. This project implements an in-kernel profiler that instruments the verifier, records fine-grained timing events during verification, and post-processes them into hierarchical call trees and per-instruction statistics. We describe the methodology—from kernel patching through QEMU-based measurement to trace analysis and visualization—and present preliminary findings on two verifier hotspots. We also discuss fundamental limitations of the approach, including measurement overhead, incomplete coverage, and the gap between profiled wall time and verifier complexity metrics.

#v(1em)
*Keywords:* eBPF, Linux kernel, static analysis, performance profiling, verifier

= Introduction

Extended Berkeley Packet Filter (eBPF) programs run inside the kernel under strict safety guarantees enforced at load time. The BPF verifier performs abstract interpretation over the program's control-flow graph, tracking register and stack states, checking memory accesses, validating helper calls, and pruning redundant exploration paths. As BPF programs grow—through loop unrolling, large map access patterns, or multi-subprogram designs—verification time becomes a practical bottleneck for developers and CI pipelines.

Existing visibility into verifier performance is limited to coarse counters printed when verification completes (e.g., instructions processed, peak abstract states). These aggregates do not reveal *where* time is spent inside the verifier nor *which BPF instruction classes* correlate with slow verification paths.

This project addresses that gap by building an end-to-end profiling pipeline:

1. A patched Linux kernel that emits structured timing records from instrumented verifier sites.
2. A userspace recorder and trace analyser that reconstructs call trees and aggregates durations.
3. A web visualizer for exploring verification profiles interactively.

The remainder of this report details our methodology, presents illustrative results on two highlighted verifier regions, and discusses limitations that constrain interpretation of the measurements.

= Background

== The BPF verification model

When a userspace process loads a BPF program via `bpf(BPF_PROG_LOAD, ...)`, the kernel invokes `bpf_check()` in `kernel/bpf/verifier.c`. Verification proceeds in several phases: BTF and metadata checks, subprogram discovery, and the main abstract interpretation loop (`do_check` → `do_check_insn`). For each BPF instruction, the verifier may:

- validate arithmetic, memory, and control-flow operations;
- invoke helper, kfunc, or subprogram call checks;
- query and update the state graph (`bpf_is_state_visited`, `states_equal`);
- perform register liveness analysis for stack slot tracking.

The verifier explores multiple abstract states per instruction. State pruning—detecting when a newly reached state is subsumed by a previously stored state—is critical for termination but can itself be expensive when many states accumulate.

== Related work and motivation

Kernel selftests include deliberately large verifier workloads (`verif_scale*`, `pyperf*`, `strobemeta*`) used to stress-test complexity limits. Prior to this project, diagnosing slow cases required manual inspection of verifier logs or ad-hoc `printk` timing. Our profiler aims to provide a systematic, repeatable measurement framework comparable in spirit to conventional application profilers, adapted to the verifier's event-driven, highly branching structure.

= Methodology

Our methodology spans kernel instrumentation, isolated execution environment, automated data collection, and offline trace reconstruction. Each stage is designed to preserve enough context (source location, BPF instruction index, verifier counters) to connect measured time back to both kernel code and the program under verification.

== Kernel instrumentation

=== Profiling primitives

The profiler is implemented in `kernel-patch/bpf/profiler.c` and exposed through macros in `profiler.h`. Each profile event is a fixed-size record (`bpf_profile_record_t`, 32 bytes) containing:

- `start_time` / `end_time`: timestamps from `ktime_get_ns()`;
- `type`: one of `START`, `END`, `BLOCK`, or `CALL`;
- `file_id`: logical source file identifier (verifier, liveness, or states);
- `line`: source line of the instrumentation site;
- `arg`: optional context (e.g., current BPF instruction index).

Three macro families instrument the kernel:

- `BPF_PROFILE_BLOCK(file_id, { ... })` — times a statement block.
- `BPF_PROFILE_CALL(file_id, func, ...)` — times a function call and records its return.
- `BPF_PROFILE_CALL_ARG(file_id, arg, func, ...)` — same as above, but attaches `arg` to the record.

Verification boundaries are marked with `BPF_PROFILE_START()` at the beginning of `bpf_check()` and `BPF_PROFILE_END()` at its conclusion.

=== Instrumentation coverage

Instrumentation is concentrated in three patched kernel files:

#figure(
  table(
    columns: (1.8fr, 2.2fr, 2fr),
    inset: 8pt,
    align: (left, left, left),
    table.header([*File*], [*Role*], [*Instrumentation pattern*]),
    [`verifier.c`], [Main verification loop and per-instruction checks], [`BPF_PROFILE_CALL_ARG` with `env->insn_idx` on `do_check_insn`, helper checks, state visits],
    [`states.c`], [Abstract state storage and equality], [`BPF_PROFILE_CALL_ARG` with instruction index on `states_equal` calls],
    [`liveness.c`], [Register/stack liveness analysis], [`BPF_PROFILE_BLOCK` and `BPF_PROFILE_CALL` around liveness queries],
  ),
  caption: [Kernel source files instrumented by the profiler.],
) <tab:coverage>

The `file_id` field maps to paths via a generated `file_ids.json` in the patched kernel tree, enabling the analyser to resolve records to filenames and function names.

=== Record persistence

At verification start (`bpf_profiler_start`), the kernel writes the BPF program bytecode (length + `struct bpf_insn` array) to `/tmp/bpf_profile_records`. At verification end (`bpf_profiler_end`), it appends:

1. Verifier statistics (`bpf_verification_profile_stats_t`): subprogram count, instructions processed, complexity limit, state counts, longest mark-read walk.
2. The number of profile records and the record array itself.

Records are stored in a pre-allocated buffer guarded by a spinlock. The buffer supports up to `BPF_PROFILE_MAX_RECORDS` entries; exceeding this cap silently drops additional records.

== Execution environment

=== Patched kernel and root filesystem

We build a custom Linux kernel from upstream sources with the profiler patch applied (`build-kernel.sh`). A minimal root filesystem image is produced separately (`build-rootfs.sh`, `setup-rootfs.sh`) and contains the BPF selftest infrastructure.

=== QEMU-based isolation

Programs are profiled inside a QEMU virtual machine (`qemu.sh`) configured with:

- KVM acceleration, 64 GiB RAM, 4 vCPUs;
- the patched kernel and rootfs disk;
- virtio-9p mounts exposing the `profiler/` userspace tooling, kernel sources, and build tools into the guest.

This setup ensures reproducible, non-invasive measurement: the host development environment does not affect verifier timing, and the guest can be reset between runs.

== Data collection pipeline

=== Launching and recording

The Python entry point (`profiler/main.py`) orchestrates profiling:

1. Select target programs from the BPF selftest suite (see @sec:corpus) or from a saved program list.
2. For each program, `BPFRecorder` clears `/tmp/bpf_profile_records`, starts a timed recording window (default 1 s), and launches the selftest subprocess.
3. After the recording window, the recorder parses the binary profile file into `ProfilingResult` objects (program bytecode, verifier stats, trace records).
4. Results below configurable thresholds (default: > 200 instructions and > 8 ms verification time) are discarded to reduce storage of trivial runs.

Multiple verification attempts for the same program (e.g., repeated loads during selftest) produce distinct traces, deduplicated by bytecode hash.

=== Trace reconstruction

The `TraceAnalyser` (`profiler/trace_analyser.py`) processes each `ProfilingResult`:

1. *Validity check* — the trace must begin with `START` and end with `END`.
2. *Call tree construction* — `BLOCK` and `CALL` records are nested by timestamp intervals into a hierarchical `CallTree` (`profiler/call_tree.py`).
3. *Site aggregation* — records sharing the same `(file_id, line, is_call)` are merged into `RecordSite` nodes with inclusive and exclusive durations.
4. *Per-instruction attribution* — for call sites instrumented with `BPF_PROFILE_CALL_ARG(..., insn_idx, ...)`, durations are bucketed by BPF instruction index and aggregated by instruction name and class.
5. *Statistics export* — results are serialized as JSON under `profiler/out/analysis/`.

The analyser computes, for each site:

- percentage of total verification time (inclusive);
- percentage of parent time;
- visit count and average duration per visit;
- ranked instruction-type breakdown (when instruction indices are available).

A global pass (`GlobalAnalyser`) ranks all analysed programs by verification time and writes summary listings to `profiler/out/time_analysis.txt`.

== Evaluation corpus
<sec:corpus>

We profile a curated subset of the kernel BPF selftest suite, grouped by topic in `sources.json`:

- *Verifier scale* — large TC, pyperf, and strobemeta workloads designed to approach complexity limits.
- *Verifier features* — targeted tests for control flow (`verifier_gotol`) and register liveness (`verifier_liveness_exp`).
- *Networking, tracing, maps, CO-RE, and project harnesses* — representative real-world program shapes.

This corpus spans programs from a few hundred to tens of thousands of BPF instructions and covers diverse verifier subsystems (state graph, liveness, helper validation, subprograms).

== Visualization

A browser-based visualizer (`visualizer/`) loads analysis JSON and presents:

- an overview of verification time and verifier counters;
- an interactive call tree with duration bars (scaled by % of total or % of parent);
- source view with highlighted profiled lines (served from `kernel-patch/`);
- per-site and program-wide BPF instruction tables.

This closes the loop between raw kernel records and human-interpretable hotspots.

= Results

This section presents illustrative findings from profiling two verifier regions. *The numerical values below are placeholders representing the kind of output the profiler produces; they should be replaced with measurements from actual runs.*

== Experimental setup

All placeholder results assume profiling of `selftest_verif_scale_strobemeta`—a large strobemeta workload with partial LLVM loop unrolling (~20k BPF instructions, high abstract state count)—inside the QEMU environment described in @sec:corpus. Default analyser thresholds and a 1 s recording window were used.

== Hotspot 1: State deduplication (`states_equal`)
<sec:hotspot-states>

*Location:* `kernel/bpf/states.c` — calls to `states_equal` instrumented with `BPF_PROFILE_CALL_ARG(BPF_PROFILE_STATES_FILE_ID, insn_idx, ...)`.

During abstract interpretation, the verifier frequently checks whether a newly derived abstract state is equivalent to—or subsumed by—a state already stored at the current instruction index. These equality checks dominate verification time for programs that induce large state graphs.

#figure(
  table(
    columns: (2fr, 1fr, 1fr, 1fr),
    inset: 8pt,
    align: (left, right, right, right),
    table.header([*Metric*], [*Value*], [*Unit*], [*Notes*]),
    [Inclusive time (site aggregate)], [312.4], [ms], [41.2% of total verification time],
    [Number of visits], [2.87], [million], [One visit per state comparison attempt],
    [Average time per visit], [108.9], [µs], [],
    [Peak concurrent states (verifier stat)], [1\,842], [], [From `peak_states` counter],
    [Slowest compared instruction class], [`jmp:jgt`], [], [Conditional branches expand state fan-out],
  ),
  caption: [Placeholder summary for the `states_equal` profiling site. *Replace with measured values.*],
) <tab:hotspot-states>

The call tree places this site under `do_check` → `do_check_insn` → `bpf_is_state_visited`. Instruction-type breakdown within the site shows that conditional jumps (`jmp:jgt`, `jmp:jne`) incur above-average per-visit cost, consistent with deeper state-list walks triggered by branch-heavy BPF bytecode.

*Interpretation (placeholder):* Optimizations to state canonicalization or early subsumption checks at high fan-out instructions would likely yield the largest verification speedups for strobemeta-class workloads.

== Hotspot 2: Per-instruction checking (`do_check_insn`)
<sec:hotspot-dci>

*Location:* `kernel/bpf/verifier.c:17790` — the main per-instruction dispatch loop, instrumented with `BPF_PROFILE_CALL_ARG` passing `env->insn_idx`.

Each BPF instruction passes through `do_check_insn`, which dispatches to specialized checkers (`check_alu_op`, `check_mem_access`, `check_helper_call`, etc.) depending on opcode class. For large programs, this loop executes hundreds of thousands to millions of times across all explored abstract states.

#figure(
  table(
    columns: (2fr, 1fr, 1fr, 1fr),
    inset: 8pt,
    align: (left, right, right, right),
    table.header([*Metric*], [*Value*], [*Unit*], [*Notes*]),
    [Inclusive time (site aggregate)], [441.9], [ms], [57.6% of total verification time],
    [Exclusive time], [248.9], [ms], [Time spent inside `do_check_insn` itself],
    [Number of visits], [551\,525], [], [Matches `insn_processed` order of magnitude],
    [Average time per visit], [801.2], [ns], [],
    [Dominant callee (child site)], [`check_mem_access`], [], [28.4% of parent inclusive time],
  ),
  caption: [Placeholder summary for the `do_check_insn` profiling site. *Replace with measured values.*],
) <tab:hotspot-dci>

Within this site, memory access validation (`check_mem_access`, `check_load_mem`) and helper call validation (`check_helper_call`) account for the majority of exclusive time not attributed to child state-graph operations. Program-wide instruction tables rank `ldx:ldx` and `alu:rsh32` among the most frequently verified opcodes, with above-average per-instance duration due to repeated state re-exploration.

*Interpretation (placeholder):* The split between `do_check_insn` overhead and nested callees suggests that micro-optimizations at the dispatch layer alone would be insufficient; targeted improvements to memory bounds checking or helper prototype matching may be necessary.

== Cross-cutting observations

Across both hotspots, total verification time in the placeholder run is approximately *767 ms* for a *12\,409*-instruction program, with *1.2 million* profile records and *48* distinct call-tree sites. Verifier counters report *555\,708* instructions processed (including re-visits across states) and *4\,095* total abstract states—indicating substantial state-space exploration relative to static program size.

These figures demonstrate that the profiler resolves aggregate verification latency into actionable sub-system contributions rather than a single opaque timing measurement.

= Limitations

While the profiler provides unprecedented visibility into verifier execution, several limitations affect the accuracy, completeness, and generalizability of results. These must be considered when drawing conclusions or proposing kernel optimizations.

== Measurement overhead (observer effect)

Every instrumented site executes two `ktime_get_ns()` calls and acquires a global spinlock to append a record. For hot paths visited millions of times— notably `do_check_insn` and `states_equal`—this overhead is non-negligible.

Consequences:

- Reported verification times are *longer* than an uninstrumented kernel; relative rankings are more trustworthy than absolute timings.
- The slowest sites are also the most frequently visited, so they suffer the greatest inflation—a form of *systematic bias* toward making high-traffic paths appear even slower.
- Spinlock contention may serialize record writes under heavy profiling, distorting concurrency behavior (though the verifier itself is largely single-threaded per program load).

== Wall-clock time vs. CPU time

Timestamps come from `ktime_get_ns()` (monotonic wall time), not CPU cycle counters or `task_sched_runtime`. Verification runs in kernel context during `bpf()` syscall handling; interrupt latency, scheduling, and VM timing artifacts (QEMU/KVM) can add noise. Comparisons across machines or kernel configurations require identical environments.

== Incomplete instrumentation coverage

Only three kernel files are instrumented. Time spent in uninstrumented verifier helpers, BTF parsing, subprogram setup, or unrelated kernel subsystems during program load is attributed only indirectly (as gaps in the call tree) or not at all. The profile therefore explains *instrumented* verification work, not the entire `BPF_PROG_LOAD` syscall latency.

== Silent record truncation

When the number of events exceeds `BPF_PROFILE_MAX_RECORDS`, additional records are dropped without error. Very long verifications with fine-grained instrumentation could produce truncated traces, leading to underestimated inclusive durations for deep subtrees. Practitioners should cross-check `num_records` against expected visit counts and watch for incomplete call trees.

== Argument semantics and attribution granularity

`BPF_PROFILE_CALL_ARG` attaches the current BPF instruction index (`env->insn_idx`) at call entry. For nested calls or instructions revisited under many abstract states, the same index aggregates durations across semantically distinct verification contexts. Instruction-type breakdowns show *which opcodes* correlate with slow paths, but not *which abstract state* caused the slowness.

== Trace validity assumptions

The analyser requires well-formed traces (matching `START`/`END`, properly nested intervals). Kernel panics, interrupted loads, or partial writes to `/tmp/bpf_profile_records` yield unusable traces. The recorder filters duplicate bytecode runs but does not validate record ordering beyond the analyser's checks.

== Environment specificity

Results were obtained (or will be obtained) on a patched kernel running in QEMU with 64 GiB guest memory and a specific selftest corpus. Findings may not transfer directly to:

- production kernels without the profiler patch (different code layout and cache behavior);
- real program load paths outside selftests (different attach types, BTF complexity, or concurrent loads);
- hardware with different timer resolution or without KVM acceleration.

== Functional impact of patching

The profiler patch modifies core verifier sources. While designed to be non-functional (timing only), any patch carries risk of subtle behavioral change. Validation relies on existing BPF selftests passing on the patched kernel—a necessary but not sufficient condition for equivalence to upstream.

== Storage and analysis cost

Large programs generate traces with millions of records (tens to hundreds of megabytes per run). Offline analysis reconstructs full call trees in userspace Python, which can take seconds to minutes per trace. The current pipeline is suited to offline diagnosis, not continuous production monitoring.

= Conclusion

We presented an end-to-end methodology for profiling the Linux BPF verifier: kernel-level instrumentation with structured timing records, QEMU-isolated execution of BPF selftests, automated trace reconstruction into call trees and instruction-level aggregates, and interactive visualization.

Placeholder results highlight two representative hotspots—state equality checking and the per-instruction verification loop—that together account for the majority of verification time on large strobemeta-class workloads. Replacing these placeholders with measured data from the project's analysis pipeline will ground the findings in empirical evidence.

The profiler's limitations, chiefly measurement overhead and partial coverage, mean that it is best used for *comparative* diagnosis (before/after optimization, or slow vs. fast program shapes) rather than as an absolute benchmark. Nevertheless, it transforms verifier performance from an opaque latency into a structured profile actionable by kernel developers.

Future work includes reducing instrumentation overhead through sampling, extending coverage to additional verifier phases, correlating profile data with verifier log output, and validating optimization hypotheses on upstream-bound patches.

= References

+ Linux kernel documentation — *BPF verifier* (`Documentation/bpf/verifier.rst`).
+ Linux kernel source — `kernel/bpf/verifier.c`, `kernel/bpf/states.c`, `kernel/bpf/liveness.c`.
+ Linux BPF selftests — `tools/testing/selftests/bpf/`.
+ Project repository — kernel patch (`kernel-patch/bpf/`), profiler tooling (`profiler/`), visualizer (`visualizer/`).
