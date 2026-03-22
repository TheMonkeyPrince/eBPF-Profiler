#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

struct event {
    char name[64];
    u64 timestamp;
};

// Perf output to userspace
BPF_PERF_OUTPUT(events);

int bpf_check_start(struct pt_regs *ctx) {
    bpf_trace_printk("BPF check start\\n");
    return 0;
}

int bpf_check_end(struct pt_regs *ctx) {
    bpf_trace_printk("BPF check end\\n");
    return 0;
}

int probe_point(struct pt_regs *ctx, char *name, u64 timestamp) {
    struct event e = {};

    // Safe read from kernel memory
    bpf_probe_read(&e.name, sizeof(e.name), name);
    e.timestamp = timestamp;

    // Send event to userspace
    events.perf_submit(ctx, &e, sizeof(e));
    return 0;
}