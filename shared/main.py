from profiler import BPFProfiler
from run_tests import run_tests
from time import sleep

if __name__ == "__main__":
    
    print("Loading BPF profiler...")
    bpf_profiler = BPFProfiler()
    
    print("Running tests...")
    run_tests()


    print("Starting event listener...")
    bpf_profiler.listen_for_events("test_program")    