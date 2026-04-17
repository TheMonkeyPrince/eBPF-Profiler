#!/usr/bin/python

import os

def run_dns_matching():
	from bcc import BPF
	bpf = BPF(src_file=f"{os.path.dirname(__file__)}/dns_matching.c", debug=0)
	bpf.load_func("dns_matching", BPF.SOCKET_FILTER)
