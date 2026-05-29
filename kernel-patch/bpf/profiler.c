#include "profiler.h"
#include <linux/spinlock.h>
#include <linux/fs.h>
#include <linux/uaccess.h>
#include <linux/kernel.h>
#include <linux/slab.h>


static DEFINE_SPINLOCK(bpf_profiler_lock);

static bpf_profile_record_list_t *bpf_profile_records = NULL;

void bpf_profiler_add_record(
    bpf_profile_record_type_t type, unsigned char file_id, int line, u32 arg, u64 start_time, u64 end_time)
{
    unsigned long flags;
    u32 idx;

    spin_lock_irqsave(&bpf_profiler_lock, flags);
    idx = bpf_profile_records->count;
    if (idx < BPF_PROFILE_MAX_RECORDS)
    {
        bpf_profile_records->records[idx].type = type;
        bpf_profile_records->records[idx].file_id = file_id;
        bpf_profile_records->records[idx].line = line;
        bpf_profile_records->records[idx].arg = arg;
        bpf_profile_records->records[idx].start_time = start_time;
        bpf_profile_records->records[idx].end_time = end_time;
        bpf_profile_records->count = idx + 1;
    }
    spin_unlock_irqrestore(&bpf_profiler_lock, flags);
}

int bpf_profiler_start(struct bpf_prog *prog)
{
    struct file *file;
    loff_t pos = 0;
    ssize_t ret;

    unsigned long flags;

    if (bpf_profile_records == NULL) {
        bpf_profile_records = vzalloc(sizeof(bpf_profile_record_list_t));
        if (!bpf_profile_records)
            return -ENOMEM;
    }

    file = filp_open("/tmp/bpf_profile_records", O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (IS_ERR(file))
        return PTR_ERR(file);

    ret = kernel_write(file, &prog->len, sizeof(prog->len), &pos);
    if (ret < 0)
        goto out;

    ret = kernel_write(file, prog->insnsi, sizeof(struct bpf_insn) * prog->len, &pos);
    if (ret < 0)
        goto out;

    ret = 0;

out:
    filp_close(file, NULL);

    spin_lock_irqsave(&bpf_profiler_lock, flags);
    bpf_profile_records->count = 0;
    spin_unlock_irqrestore(&bpf_profiler_lock, flags);
    return ret;
}

static void bpf_profiler_capture_stats(struct bpf_verifier_env *env, bpf_verification_profile_stats_t *stats)
{
    if (!env || !stats)
        return;

    stats->subprog_cnt = env->subprog_cnt;
    stats->insn_processed = env->insn_processed;
    stats->complexity_limit_insns = BPF_COMPLEXITY_LIMIT_INSNS;
    stats->max_states_per_insn = env->max_states_per_insn;
    stats->total_states = env->total_states;
    stats->peak_states = env->peak_states;
    stats->longest_mark_read_walk = env->longest_mark_read_walk;
}

int bpf_profiler_end(struct bpf_verifier_env *env) {
    struct file *file;
    loff_t pos = 0;
    ssize_t ret;
    bpf_verification_profile_stats_t stats;
    unsigned long flags;

    file = filp_open("/tmp/bpf_profile_records", O_WRONLY | O_CREAT | O_APPEND, 0644);
    if (IS_ERR(file))
        return PTR_ERR(file);
   
    bpf_profiler_capture_stats(env, &stats);
    ret = kernel_write(file, &stats, sizeof(stats), &pos);
    if (ret < 0)
        goto out;

    ret = kernel_write(file, &bpf_profile_records->count,
                       sizeof(bpf_profile_records->count), &pos);
    if (ret < 0)
        goto out;

    ret = kernel_write(file, bpf_profile_records->records,
                       sizeof(bpf_profile_record_t) * bpf_profile_records->count, &pos);
    if (ret < 0)
        goto out;

    ret = 0;

out:    
    spin_lock_irqsave(&bpf_profiler_lock, flags);
    bpf_profile_records->count = 0;
    spin_unlock_irqrestore(&bpf_profiler_lock, flags);
    filp_close(file, NULL);
    
    return ret;
}
