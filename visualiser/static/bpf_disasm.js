/**
 * Minimal eBPF disassembler (classic insn layout, common verifier opcodes).
 * Input: array of { code, dst, src, off, imm } (Linux struct bpf_insn).
 */
(function () {
  const BPF_LD = 0x00;
  const BPF_LDX = 0x01;
  const BPF_ST = 0x02;
  const BPF_STX = 0x03;
  const BPF_ALU = 0x04;
  const BPF_JMP = 0x05;
  const BPF_JMP32 = 0x06;
  const BPF_ALU64 = 0x07;

  const BPF_K = 0x00;
  const BPF_X = 0x08;

  const BPF_W = 0x00;
  const BPF_H = 0x08;
  const BPF_B = 0x10;
  const BPF_DW = 0x18;

  const BPF_IMM = 0x00;
  const BPF_ABS = 0x20;
  const BPF_IND = 0x40;
  const BPF_MEM = 0x60;
  const BPF_ATOMIC = 0xc0;

  const ALU_OPS = {
    0x00: "add",
    0x10: "sub",
    0x20: "mul",
    0x30: "div",
    0x40: "or",
    0x50: "and",
    0x60: "lsh",
    0x70: "rsh",
    0x80: "neg",
    0x90: "mod",
    0xa0: "xor",
    0xb0: "mov",
    0xc0: "arsh",
    0xd0: "end",
  };

  function r(n) {
    return n === 10 ? "fp" : `r${n}`;
  }

  function sizeName(sz) {
    if (sz === BPF_W) return "w";
    if (sz === BPF_H) return "h";
    if (sz === BPF_B) return "b";
    if (sz === BPF_DW) return "dw";
    return "?";
  }

  function disasmOne(insn, pc) {
    const { code, dst, src, off, imm } = insn;
    const cls = code & 0x07;
    const op = code & 0xf0;
    const srcReg = (code & 0x08) !== 0;
    const sz = code & 0x18;
    const mode = code & 0xe0;

    if (cls === BPF_ALU64 || cls === BPF_ALU) {
      const nm = ALU_OPS[op] || `alu0x${op.toString(16)}`;
      const bits = cls === BPF_ALU64 ? 64 : 32;
      if (op === 0xb0) {
        return srcReg ? `${r(dst)} = ${cls === BPF_ALU64 ? "" : "(u32)"}${r(src)}` : `${r(dst)} = ${imm}`;
      }
      if (op === 0x80) {
        return `${r(dst)} = -${r(src)}`;
      }
      const rhs = srcReg ? r(src) : String(imm);
      return bits === 64 ? `${r(dst)} ${nm}= ${rhs}` : `(u32) ${r(dst)} ${nm}= ${rhs}`;
    }

    if (cls === BPF_JMP || cls === BPF_JMP32) {
      const opn = op;
      const dstR = r(dst);
      const immOrSrc = srcReg ? r(src) : String(imm);
      const sfx = cls === BPF_JMP32 ? "32" : "";
      if (opn === 0x00) return `ja${sfx} +${off}`;
      if (opn === 0x10) return `jeq${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x20) return `jgt${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x30) return `jge${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x40) return `jset${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x50) return `jne${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x60) return `jsgt${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x70) return `jsge${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0x80) return `call${sfx} ${imm}`;
      if (opn === 0x90) return "exit";
      if (opn === 0xa0) return `jlt${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0xb0) return `jle${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0xc0) return `jslt${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      if (opn === 0xd0) return `jsle${sfx} ${dstR}, ${immOrSrc}, +${off}`;
      return `jmp? code=0x${code.toString(16)}`;
    }

    if (cls === BPF_LD || cls === BPF_LDX) {
      const s = sizeName(sz);
      if (mode === BPF_MEM) {
        const acc = cls === BPF_LDX ? "x" : "";
        const offStr = off === 0 ? "" : `${off >= 0 ? "+" : ""}${off}`;
        return `${r(dst)} = ${acc}[${r(src)}${offStr}]${s}`;
      }
      if (mode === BPF_IMM && sz === BPF_DW && cls === BPF_LD) {
        return `${r(dst)} = 0x${(imm >>> 0).toString(16)} /* ld_imm64 low */`;
      }
      if (mode === BPF_ATOMIC) {
        return `atomic${s} [${r(dst)}+${off}] ${r(src)} imm=${imm}`;
      }
    }

    if (cls === BPF_ST) {
      if (mode === BPF_MEM) {
        return `[${r(dst)}${off >= 0 ? "+" : ""}${off}]${sizeName(sz)} = ${imm}`;
      }
    }

    if (cls === BPF_STX) {
      if (mode === BPF_MEM) {
        return `[${r(dst)}${off >= 0 ? "+" : ""}${off}]${sizeName(sz)} = ${r(src)}`;
      }
      if (mode === BPF_ATOMIC) {
        return `stx atomic [${r(dst)}+${off}] ${r(src)} imm=${imm}`;
      }
    }

    return `(raw) code=0x${code.toString(16)} dst=${dst} src=${src} off=${off} imm=${imm}`;
  }

  function disasmProgramLines(insns) {
    if (!Array.isArray(insns) || insns.length === 0) {
      return [];
    }
    const lines = [];
    for (let pc = 0; pc < insns.length; pc += 1) {
      const insn = insns[pc];
      const asm = disasmOne(insn, pc);
      const pad = String(pc).padStart(4, "0");
      lines.push({ pc, text: `${pad}: ${asm}` });
    }
    return lines;
  }

  function disasmProgram(insns) {
    return disasmProgramLines(insns)
      .map((line) => line.text)
      .join("\n");
  }

  window.disasmBpfProgram = disasmProgram;
  window.disasmBpfProgramLines = disasmProgramLines;
})();
