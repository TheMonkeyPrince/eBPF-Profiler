#include <linux/sched.h>
#include <linux/string.h>
#include <uapi/linux/ptrace.h>

#define BPF_PROFILER_MAX_EVENT_RESULTS 1

typedef enum {
    START,
    END,
    BLOCK,
    CALL,
} bpf_profile_record_type_t;

typedef struct __attribute__((packed)) {
    bpf_profile_record_type_t type;
    const char file[64];
    int line;
    const char func_name[32];
    u32 arg;
    u64 start_time;
    u64 end_time;
} bpf_profile_record_t;

// Perf output map
BPF_PERF_OUTPUT(events);

int profiler_hook(struct pt_regs *ctx, const bpf_profile_record_t *record) {
    bpf_profile_record_t received;
    bpf_probe_read_kernel(&received, sizeof(received), record);
    events.perf_submit(ctx, &received, sizeof(received));
    
    // char message[] = "Hello from the kernel!";
    // events.perf_submit(ctx, &message, sizeof(message));
    return 0;
}