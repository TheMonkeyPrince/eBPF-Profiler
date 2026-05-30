"""eBPF disassembler ported from linux/kernel/bpf/disasm.c."""

from __future__ import annotations

import sys
from pathlib import Path

from profiler_types import BPFInsn

_KERNEL_ROOT = Path("/mnt/linux") if Path("/mnt/linux").is_dir() else Path("../linux")
sys.path.append(str(_KERNEL_ROOT / "scripts"))
from bpf_doc import HeaderParser  # noqa: E402

p = HeaderParser(str(_KERNEL_ROOT / "include/uapi/linux/bpf.h"))
p.run()

BPF_FUNC_NAMES: dict[int, str] = {}
for name, hid in sorted(p.helper_enum_vals.items(), key=lambda x: x[1]):
    BPF_FUNC_NAMES[hid] = name

# bpf_common.h / bpf.h
BPF_LD = 0x00
BPF_LDX = 0x01
BPF_ST = 0x02
BPF_STX = 0x03
BPF_ALU = 0x04
BPF_JMP = 0x05
BPF_JMP32 = 0x06
BPF_ALU64 = 0x07

BPF_K = 0x00
BPF_X = 0x08

BPF_W = 0x00
BPF_H = 0x08
BPF_B = 0x10
BPF_DW = 0x18

BPF_IMM = 0x00
BPF_ABS = 0x20
BPF_IND = 0x40
BPF_MEM = 0x60
BPF_MEMSX = 0x80
BPF_ATOMIC = 0xC0
BPF_NOSPEC = 0xC0  # BPF_NOSPEC, no UAPI

BPF_ADD = 0x00
BPF_SUB = 0x10
BPF_MUL = 0x20
BPF_DIV = 0x30
BPF_OR = 0x40
BPF_AND = 0x50
BPF_LSH = 0x60
BPF_RSH = 0x70
BPF_NEG = 0x80
BPF_MOD = 0x90
BPF_XOR = 0xA0
BPF_MOV = 0xB0
BPF_ARSH = 0xC0
BPF_END = 0xD0

BPF_TO_LE = 0x00
BPF_TO_BE = 0x08

BPF_JA = 0x00
BPF_JEQ = 0x10
BPF_JGT = 0x20
BPF_JGE = 0x30
BPF_JSET = 0x40
BPF_JNE = 0x50
BPF_JSGT = 0x60
BPF_JSGE = 0x70
BPF_JLT = 0xA0
BPF_JLE = 0xB0
BPF_JSLT = 0xC0
BPF_JSLE = 0xD0
BPF_JCOND = 0xE0
BPF_CALL = 0x80
BPF_EXIT = 0x90

BPF_FETCH = 0x01
BPF_XCHG = 0xE0 | BPF_FETCH
BPF_CMPXCHG = 0xF0 | BPF_FETCH
BPF_LOAD_ACQ = 0x100
BPF_STORE_REL = 0x110

BPF_MAY_GOTO = 0

BPF_PSEUDO_MAP_FD = 1
BPF_PSEUDO_MAP_VALUE = 2
BPF_PSEUDO_CALL = 1
BPF_PSEUDO_KFUNC_CALL = 2

BPF_ADDR_SPACE_CAST = 1
BPF_ADDR_PERCPU = -1


def BPF_CLASS(code: int) -> int:
    return code & 0x07


def BPF_SIZE(code: int) -> int:
    return code & 0x18


def BPF_MODE(code: int) -> int:
    return code & 0xE0


def BPF_OP(code: int) -> int:
    return code & 0xF0


def BPF_SRC(code: int) -> int:
    return code & 0x08


BPF_CLASS_STRING: list[str | None] = [None] * 8
BPF_CLASS_STRING[BPF_LD] = "ld"
BPF_CLASS_STRING[BPF_LDX] = "ldx"
BPF_CLASS_STRING[BPF_ST] = "st"
BPF_CLASS_STRING[BPF_STX] = "stx"
BPF_CLASS_STRING[BPF_ALU] = "alu"
BPF_CLASS_STRING[BPF_JMP] = "jmp"
BPF_CLASS_STRING[BPF_JMP32] = "jmp32"
BPF_CLASS_STRING[BPF_ALU64] = "alu64"

BPF_ALU_STRING: list[str | None] = [None] * 16
BPF_ALU_STRING[BPF_ADD >> 4] = "+="
BPF_ALU_STRING[BPF_SUB >> 4] = "-="
BPF_ALU_STRING[BPF_MUL >> 4] = "*="
BPF_ALU_STRING[BPF_DIV >> 4] = "/="
BPF_ALU_STRING[BPF_OR >> 4] = "|="
BPF_ALU_STRING[BPF_AND >> 4] = "&="
BPF_ALU_STRING[BPF_LSH >> 4] = "<<="
BPF_ALU_STRING[BPF_RSH >> 4] = ">>="
BPF_ALU_STRING[BPF_NEG >> 4] = "neg"
BPF_ALU_STRING[BPF_MOD >> 4] = "%="
BPF_ALU_STRING[BPF_XOR >> 4] = "^="
BPF_ALU_STRING[BPF_MOV >> 4] = "="
BPF_ALU_STRING[BPF_ARSH >> 4] = "s>>="
BPF_ALU_STRING[BPF_END >> 4] = "endian"

BPF_ALU_SIGN_STRING: list[str | None] = [None] * 16
BPF_ALU_SIGN_STRING[BPF_DIV >> 4] = "s/="
BPF_ALU_SIGN_STRING[BPF_MOD >> 4] = "s%="

BPF_MOVSX_STRING: list[str | None] = [None] * 4
BPF_MOVSX_STRING[0] = "(s8)"
BPF_MOVSX_STRING[1] = "(s16)"
BPF_MOVSX_STRING[3] = "(s32)"

BPF_ATOMIC_ALU_STRING: list[str | None] = [None] * 16
BPF_ATOMIC_ALU_STRING[BPF_ADD >> 4] = "add"
BPF_ATOMIC_ALU_STRING[BPF_AND >> 4] = "and"
BPF_ATOMIC_ALU_STRING[BPF_OR >> 4] = "or"
BPF_ATOMIC_ALU_STRING[BPF_XOR >> 4] = "xor"

BPF_LDST_STRING: list[str | None] = [None] * 4
BPF_LDST_STRING[BPF_W >> 3] = "u32"
BPF_LDST_STRING[BPF_H >> 3] = "u16"
BPF_LDST_STRING[BPF_B >> 3] = "u8"
BPF_LDST_STRING[BPF_DW >> 3] = "u64"

BPF_LDSX_STRING: list[str | None] = [None] * 4
BPF_LDSX_STRING[BPF_W >> 3] = "s32"
BPF_LDSX_STRING[BPF_H >> 3] = "s16"
BPF_LDSX_STRING[BPF_B >> 3] = "s8"

BPF_JMP_STRING: list[str | None] = [None] * 16
BPF_JMP_STRING[BPF_JA >> 4] = "jmp"
BPF_JMP_STRING[BPF_JEQ >> 4] = "=="
BPF_JMP_STRING[BPF_JGT >> 4] = ">"
BPF_JMP_STRING[BPF_JLT >> 4] = "<"
BPF_JMP_STRING[BPF_JGE >> 4] = ">="
BPF_JMP_STRING[BPF_JLE >> 4] = "<="
BPF_JMP_STRING[BPF_JSET >> 4] = "&"
BPF_JMP_STRING[BPF_JNE >> 4] = "!="
BPF_JMP_STRING[BPF_JSGT >> 4] = "s>"
BPF_JMP_STRING[BPF_JSLT >> 4] = "s<"
BPF_JMP_STRING[BPF_JSGE >> 4] = "s>="
BPF_JMP_STRING[BPF_JSLE >> 4] = "s<="
BPF_JMP_STRING[BPF_CALL >> 4] = "call"
BPF_JMP_STRING[BPF_EXIT >> 4] = "exit"

BPF_ALU_NAME: list[str | None] = [None] * 16
BPF_ALU_NAME[BPF_ADD >> 4] = "add"
BPF_ALU_NAME[BPF_SUB >> 4] = "sub"
BPF_ALU_NAME[BPF_MUL >> 4] = "mul"
BPF_ALU_NAME[BPF_DIV >> 4] = "div"
BPF_ALU_NAME[BPF_OR >> 4] = "or"
BPF_ALU_NAME[BPF_AND >> 4] = "and"
BPF_ALU_NAME[BPF_LSH >> 4] = "lsh"
BPF_ALU_NAME[BPF_RSH >> 4] = "rsh"
BPF_ALU_NAME[BPF_NEG >> 4] = "neg"
BPF_ALU_NAME[BPF_MOD >> 4] = "mod"
BPF_ALU_NAME[BPF_XOR >> 4] = "xor"
BPF_ALU_NAME[BPF_MOV >> 4] = "mov"
BPF_ALU_NAME[BPF_ARSH >> 4] = "arsh"
BPF_ALU_NAME[BPF_END >> 4] = "end"

BPF_ALU_SIGN_NAME: list[str | None] = [None] * 16
BPF_ALU_SIGN_NAME[BPF_DIV >> 4] = "sdiv"
BPF_ALU_SIGN_NAME[BPF_MOD >> 4] = "smod"

BPF_JMP_NAME: list[str | None] = [None] * 16
BPF_JMP_NAME[BPF_JA >> 4] = "ja"
BPF_JMP_NAME[BPF_JEQ >> 4] = "jeq"
BPF_JMP_NAME[BPF_JGT >> 4] = "jgt"
BPF_JMP_NAME[BPF_JLT >> 4] = "jlt"
BPF_JMP_NAME[BPF_JGE >> 4] = "jge"
BPF_JMP_NAME[BPF_JLE >> 4] = "jle"
BPF_JMP_NAME[BPF_JSET >> 4] = "jset"
BPF_JMP_NAME[BPF_JNE >> 4] = "jne"
BPF_JMP_NAME[BPF_JSGT >> 4] = "jsgt"
BPF_JMP_NAME[BPF_JSLT >> 4] = "jslt"
BPF_JMP_NAME[BPF_JSGE >> 4] = "jsge"
BPF_JMP_NAME[BPF_JSLE >> 4] = "jsle"
BPF_JMP_NAME[BPF_CALL >> 4] = "call"
BPF_JMP_NAME[BPF_EXIT >> 4] = "exit"


def _is_ldimm64(insn: BPFInsn) -> bool:
    return (
        BPF_CLASS(insn.code) == BPF_LD
        and BPF_MODE(insn.code) == BPF_IMM
        and BPF_SIZE(insn.code) == BPF_DW
    )


def _is_ldimm64_continuation(program: list[BPFInsn], idx: int) -> bool:
    return idx > 0 and _is_ldimm64(program[idx - 1])


def _func_get_name(insn: BPFInsn) -> str:
    if (
        not insn.src_reg
        and insn.imm >= 0
        and insn.imm in BPF_FUNC_NAMES
    ):
        return BPF_FUNC_NAMES[insn.imm]

    if insn.src_reg == BPF_PSEUDO_CALL:
        # return f"{insn.imm:+d}"
        return f"+offset"
    if insn.src_reg == BPF_PSEUDO_KFUNC_CALL:
        return "kernel-function"
    return "unknown"


def _func_imm_name(insn: BPFInsn, full_imm: int, allow_ptr_leaks: bool) -> str:
    is_ptr = insn.src_reg in (BPF_PSEUDO_MAP_FD, BPF_PSEUDO_MAP_VALUE)
    if is_ptr and not allow_ptr_leaks:
        full_imm = 0
    return f"0x{full_imm:x}"


def _is_sdiv_smod(insn: BPFInsn) -> bool:
    op = BPF_OP(insn.code)
    return (op == BPF_DIV or op == BPF_MOD) and insn.off == 1


def _is_movsx(insn: BPFInsn) -> bool:
    return BPF_OP(insn.code) == BPF_MOV and insn.off in (8, 16, 32)


def _is_addr_space_cast(insn: BPFInsn) -> bool:
    return insn.code == (BPF_ALU64 | BPF_MOV | BPF_X) and insn.off == BPF_ADDR_SPACE_CAST


def _is_mov_percpu_addr(insn: BPFInsn) -> bool:
    return insn.code == (BPF_ALU64 | BPF_MOV | BPF_X) and insn.off == BPF_ADDR_PERCPU


def _alu_op_str(insn: BPFInsn) -> str:
    idx = BPF_OP(insn.code) >> 4
    if _is_sdiv_smod(insn):
        return BPF_ALU_SIGN_STRING[idx] or "?"
    return BPF_ALU_STRING[idx] or "?"


def _movsx_str(insn: BPFInsn) -> str:
    if not _is_movsx(insn):
        return ""
    return BPF_MOVSX_STRING[(insn.off >> 3) - 1] or ""


def _alu_name(insn: BPFInsn) -> str:
    idx = BPF_OP(insn.code) >> 4
    if _is_sdiv_smod(insn):
        return BPF_ALU_SIGN_NAME[idx] or "?"
    if _is_movsx(insn):
        return "movsx"
    return BPF_ALU_NAME[idx] or "?"


def disasm_insn_name(insn: BPFInsn) -> str:
    """Return the mnemonic name for a single BPF instruction."""
    code = insn.code
    cls = BPF_CLASS(code)

    if _is_ldimm64(insn):
        return "ldimm64"
    if insn.code == 0 and not insn.dst_reg and not insn.src_reg and not insn.off:
        return "ldimm64"

    if cls == BPF_ALU or cls == BPF_ALU64:
        if BPF_OP(code) == BPF_END and cls == BPF_ALU64:
            return "bswap"
        if _is_addr_space_cast(insn):
            return "addr_space_cast"
        if _is_mov_percpu_addr(insn):
            return "mov_percpu"
        return _alu_name(insn)

    if cls == BPF_STX:
        if BPF_MODE(code) == BPF_MEM:
            return "stx"
        if BPF_MODE(code) == BPF_ATOMIC:
            if insn.imm in (BPF_ADD, BPF_AND, BPF_OR, BPF_XOR):
                return f"atomic_{BPF_ATOMIC_ALU_STRING[BPF_OP(insn.imm) >> 4]}"
            if insn.imm in (
                BPF_ADD | BPF_FETCH,
                BPF_AND | BPF_FETCH,
                BPF_OR | BPF_FETCH,
                BPF_XOR | BPF_FETCH,
            ):
                return f"atomic_fetch_{BPF_ATOMIC_ALU_STRING[BPF_OP(insn.imm) >> 4]}"
            if insn.imm == BPF_CMPXCHG:
                return "atomic_cmpxchg"
            if insn.imm == BPF_XCHG:
                return "atomic_xchg"
            if insn.imm == BPF_LOAD_ACQ:
                return "load_acquire"
            if insn.imm == BPF_STORE_REL:
                return "store_release"
        return f"stx_0x{code:02x}"

    if cls == BPF_ST:
        if BPF_MODE(code) == BPF_MEM:
            return "st"
        if BPF_MODE(code) == BPF_NOSPEC:
            return "nospec"
        return f"st_0x{code:02x}"

    if cls == BPF_LDX:
        if BPF_MODE(code) == BPF_MEMSX:
            return "ldx_sx"
        if BPF_MODE(code) == BPF_MEM:
            return "ldx"
        return f"ldx_0x{code:02x}"

    if cls == BPF_LD:
        if BPF_MODE(code) == BPF_ABS:
            return "ld_abs"
        if BPF_MODE(code) == BPF_IND:
            return "ld_ind"
        return f"ld_0x{code:02x}"

    if cls in (BPF_JMP32, BPF_JMP):
        sfx = "32" if cls == BPF_JMP32 else ""
        opcode = BPF_OP(code)

        if opcode == BPF_CALL:
            name = _func_get_name(insn)
            if insn.src_reg == BPF_PSEUDO_CALL:
                return f"call pc{name}"
            return f"call {name}"

        if code == (BPF_JMP | BPF_JA):
            return "goto"
        if code == (BPF_JMP | BPF_JA | BPF_X):
            return "gotox"
        if code == (BPF_JMP | BPF_JCOND) and insn.src_reg == BPF_MAY_GOTO:
            return "may_goto"
        if code == (BPF_JMP32 | BPF_JA):
            return "gotol"
        if code == (BPF_JMP | BPF_EXIT):
            return "exit"

        jmp_name = BPF_JMP_NAME[opcode >> 4]
        if jmp_name:
            return f"{jmp_name}{sfx}"
        return f"jmp_0x{code:02x}"

    return BPF_CLASS_STRING[cls] or f"cls_{cls}"


def disasm_insn(
    program: list[BPFInsn],
    idx: int,
    *,
    allow_ptr_leaks: bool = True,
) -> str:
    """Disassemble one BPF instruction (linux/kernel/bpf/disasm.c)."""
    if idx < 0 or idx >= len(program):
        raise IndexError(f"instruction index {idx} out of range [0, {len(program)})")

    if _is_ldimm64_continuation(program, idx):
        insn = program[idx]
        return f"({insn.code:02x}) /* ldimm64 */"

    insn = program[idx]
    code = insn.code
    cls = BPF_CLASS(code)

    if cls == BPF_ALU or cls == BPF_ALU64:
        reg = "w" if cls == BPF_ALU else "r"
        if BPF_OP(code) == BPF_END:
            if cls == BPF_ALU64:
                return f"({idx}) r{insn.dst_reg} = bswap{insn.imm} r{insn.dst_reg}"
            endian = "be" if BPF_SRC(code) == BPF_TO_BE else "le"
            return (
                f"({idx}) r{insn.dst_reg} = {endian}{insn.imm} "
                f"r{insn.dst_reg}"
            )
        if BPF_OP(code) == BPF_NEG:
            return (
                f"({idx}) {reg}{insn.dst_reg} = -{reg}{insn.dst_reg}"
            )
        if _is_addr_space_cast(insn):
            return (
                f"({idx}) r{insn.dst_reg} = addr_space_cast("
                f"r{insn.src_reg}, {(insn.imm & 0xFFFFFFFF) >> 16}, "
                f"{insn.imm & 0xFFFF})"
            )
        if _is_mov_percpu_addr(insn):
            return (
                f"({idx}) r{insn.dst_reg} = "
                f"&(void __percpu *)(r{insn.src_reg})"
            )
        op = _alu_op_str(insn)
        movsx = _movsx_str(insn)
        if BPF_SRC(code) == BPF_X:
            return (
                f"({idx}) {reg}{insn.dst_reg} {op} {movsx}"
                f"{reg}{insn.src_reg}"
            )
        return f"({idx}) {reg}{insn.dst_reg} {op} {insn.imm}"

    if cls == BPF_STX:
        size = BPF_LDST_STRING[BPF_SIZE(code) >> 3] or "?"
        if BPF_MODE(code) == BPF_MEM:
            return (
                f"({idx}) *({size} *)(r{insn.dst_reg} {insn.off:+d}) = "
                f"r{insn.src_reg}"
            )
        if BPF_MODE(code) == BPF_ATOMIC and insn.imm in (
            BPF_ADD,
            BPF_AND,
            BPF_OR,
            BPF_XOR,
        ):
            return (
                f"({idx}) lock *({size} *)(r{insn.dst_reg} {insn.off:+d}) "
                f"{BPF_ALU_STRING[BPF_OP(insn.imm) >> 4]} r{insn.src_reg}"
            )
        if BPF_MODE(code) == BPF_ATOMIC and insn.imm in (
            BPF_ADD | BPF_FETCH,
            BPF_AND | BPF_FETCH,
            BPF_OR | BPF_FETCH,
            BPF_XOR | BPF_FETCH,
        ):
            dw = "64" if BPF_SIZE(code) == BPF_DW else ""
            return (
                f"({idx}) r{insn.src_reg} = atomic{dw}_fetch_"
                f"{BPF_ATOMIC_ALU_STRING[BPF_OP(insn.imm) >> 4]}("
                f"({size} *)(r{insn.dst_reg} {insn.off:+d}), r{insn.src_reg})"
            )
        if BPF_MODE(code) == BPF_ATOMIC and insn.imm == BPF_CMPXCHG:
            dw = "64" if BPF_SIZE(code) == BPF_DW else ""
            return (
                f"({idx}) r0 = atomic{dw}_cmpxchg("
                f"({size} *)(r{insn.dst_reg} {insn.off:+d}), r0, r{insn.src_reg})"
            )
        if BPF_MODE(code) == BPF_ATOMIC and insn.imm == BPF_XCHG:
            dw = "64" if BPF_SIZE(code) == BPF_DW else ""
            return (
                f"({idx}) r{insn.src_reg} = atomic{dw}_xchg("
                f"({size} *)(r{insn.dst_reg} {insn.off:+d}), r{insn.src_reg})"
            )
        if BPF_MODE(code) == BPF_ATOMIC and insn.imm == BPF_LOAD_ACQ:
            return (
                f"({idx}) r{insn.dst_reg} = load_acquire("
                f"({size} *)(r{insn.src_reg} {insn.off:+d}))"
            )
        if BPF_MODE(code) == BPF_ATOMIC and insn.imm == BPF_STORE_REL:
            return (
                f"({idx}) store_release("
                f"({size} *)(r{insn.dst_reg} {insn.off:+d}), r{insn.src_reg})"
            )
        return f"BUG_{code:02x}"

    if cls == BPF_ST:
        size = BPF_LDST_STRING[BPF_SIZE(code) >> 3] or "?"
        if BPF_MODE(code) == BPF_MEM:
            return (
                f"({idx}) *({size} *)(r{insn.dst_reg} {insn.off:+d}) = "
                f"{insn.imm}"
            )
        if BPF_MODE(code) == BPF_NOSPEC:
            return f"({idx}) nospec"
        return f"BUG_st_{code:02x}"

    if cls == BPF_LDX:
        if BPF_MODE(code) not in (BPF_MEM, BPF_MEMSX):
            return f"BUG_ldx_{code:02x}"
        size_tbl = BPF_LDST_STRING if BPF_MODE(code) == BPF_MEM else BPF_LDSX_STRING
        size = size_tbl[BPF_SIZE(code) >> 3] or "?"
        return (
            f"({idx}) r{insn.dst_reg} = *({size} *)(r{insn.src_reg} "
            f"{insn.off:+d})"
        )

    if cls == BPF_LD:
        size = BPF_LDST_STRING[BPF_SIZE(code) >> 3] or "?"
        if BPF_MODE(code) == BPF_ABS:
            return f"({idx}) r0 = *({size} *)skb[{insn.imm}]"
        if BPF_MODE(code) == BPF_IND:
            return (
                f"({idx}) r0 = *({size} *)skb[r{insn.src_reg} + {insn.imm}]"
            )
        if BPF_MODE(code) == BPF_IMM and BPF_SIZE(code) == BPF_DW:
            if idx + 1 >= len(program):
                raise IndexError(
                    f"ldimm64 at index {idx} requires a following instruction"
                )
            imm = (program[idx + 1].imm << 32) | (insn.imm & 0xFFFFFFFF)
            imm_str = _func_imm_name(insn, imm, allow_ptr_leaks)
            return f"({idx}) r{insn.dst_reg} = {imm_str}"
        return f"BUG_ld_{code:02x}"

    if cls in (BPF_JMP32, BPF_JMP):
        reg = "w" if cls == BPF_JMP32 else "r"
        opcode = BPF_OP(code)

        if opcode == BPF_CALL:
            name = _func_get_name(insn)
            if insn.src_reg == BPF_PSEUDO_CALL:
                return f"({idx}) call pc{name}"
            return f"({idx}) call {name}#{insn.imm}"

        if code == (BPF_JMP | BPF_JA):
            return f"({idx}) goto pc{insn.off:+d}"
        if code == (BPF_JMP | BPF_JA | BPF_X):
            return f"({idx}) gotox r{insn.dst_reg}"
        if code == (BPF_JMP | BPF_JCOND) and insn.src_reg == BPF_MAY_GOTO:
            return f"({idx}) may_goto pc{insn.off:+d}"
        if code == (BPF_JMP32 | BPF_JA):
            return f"({idx}) gotol pc{insn.imm:+d}"
        if code == (BPF_JMP | BPF_EXIT):
            return f"({idx}) exit"

        jmp_op = BPF_JMP_STRING[BPF_OP(code) >> 4] or "?"
        if BPF_SRC(code) == BPF_X:
            return (
                f"({idx}) if {reg}{insn.dst_reg} {jmp_op} "
                f"{reg}{insn.src_reg} goto pc{insn.off:+d}"
            )
        return (
            f"({idx}) if {reg}{insn.dst_reg} {jmp_op} "
            f"0x{insn.imm & 0xFFFFFFFF:x} goto pc{insn.off:+d}"
        )

    cls_name = BPF_CLASS_STRING[cls] or "?"
    return f"({idx}) {cls_name}"


def disasm_program(
    program: list[BPFInsn],
    *,
    allow_ptr_leaks: bool = True,
) -> list[str]:
    """Disassemble every instruction; one string per index (aligned with insn_idx)."""
    return [
        disasm_insn(program, idx, allow_ptr_leaks=allow_ptr_leaks)
        for idx in range(len(program))
    ]
