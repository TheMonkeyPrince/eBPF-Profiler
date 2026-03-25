from profiler import BPFProfiler

if __name__ == "__main__":
    profiler = BPFProfiler()
    trace = profiler.profile_program("some_program")

    profiler.analyse_trace("some_program", trace)
    # profiler.analyse_trace_from_file("some_program")
