#!/usr/bin/python

from bcc import BPF
import os

def run_dns_matching():
	bpf = BPF(src_file=f"{os.path.dirname(__file__)}/dns_matching.c", debug=0)
	bpf.load_func("dns_matching", BPF.SOCKET_FILTER)
