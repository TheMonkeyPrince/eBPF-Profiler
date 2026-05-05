#include "profiler.h"
#include <linux/spinlock.h>
#include <linux/types.h>

static DEFINE_SPINLOCK(bpf_profiler_lock);

static bpf_profile_record_list_t bpf_profile_records = {0};

void bpf_profiler_add_record(
    bpf_profile_record_type_t type, const char *file, int line,
    const char *func_name, u32 arg, u64 start_time, u64 end_time)
{
    unsigned long flags;
    u32 idx;

    spin_lock_irqsave(&bpf_profiler_lock, flags);
    idx = bpf_profile_records.count;
    if (idx < BPF_PROFILE_MAX_RECORDS)
    {
        bpf_profile_records.records[idx].type = type;
        if (file) {
            strscpy(bpf_profile_records.records[idx].file, file, sizeof(bpf_profile_records.records[idx].file));
        }
        bpf_profile_records.records[idx].line = line;
        if (func_name) {
            strscpy(bpf_profile_records.records[idx].func_name, func_name, sizeof(bpf_profile_records.records[idx].func_name));
        }
        bpf_profile_records.records[idx].arg = arg;
        bpf_profile_records.records[idx].start_time = start_time;
        bpf_profile_records.records[idx].end_time = end_time;
        bpf_profile_records.count = idx + 1;
    }
    spin_unlock_irqrestore(&bpf_profiler_lock, flags);
}

noinline __used void bpf_profiler_push_records(void) {
    bpf_profiler_hook(&bpf_profile_records.records[0]);
    for (u32 i = 0; i < bpf_profile_records.count; i++) {
        bpf_profiler_hook(&bpf_profile_records.records[i]);
    }
}

volatile u64 bpf_profiler_sink;
noinline __used void bpf_profiler_hook(const bpf_profile_record_t *record) {
    bpf_profiler_sink += (u64)record;
}