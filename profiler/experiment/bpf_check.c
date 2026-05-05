#include <uapi/linux/ptrace.h>
#include <linux/sched.h>

// struct filename_t {
//     const char *name;
// };

struct event_t {
    u32 i;
};

BPF_PERF_OUTPUT(events);

int bpf_check(struct pt_regs *ctx) {
    // struct filename_t *fn = (struct filename_t *)PT_REGS_PARM2(ctx);
    // const char *name_ptr = NULL;
    struct event_t event = {};
    event.i = 42;

    // event.pid = bpf_get_current_pid_tgid() >> 32;
    // bpf_get_current_comm(&event.comm, sizeof(event.comm));
    // bpf_probe_read_kernel(&name_ptr, sizeof(name_ptr), &fn->name);
    // event.read_ret = bpf_probe_read_kernel_str(&event.fname, sizeof(event.fname), name_ptr);
    events.perf_submit(ctx, &event, sizeof(event));
    return 0;
}