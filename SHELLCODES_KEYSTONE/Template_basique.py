# .\python.exe -m pip install keystone-engine
# WinDbg => Attach to process

from keystone import *
import ctypes
import sys

CODE = """
    int3
    ret
"""

# Vérification process 32-bit
if sys.maxsize > 2**32:
    print("[!] Lance ce script avec Python x86 (32-bit)")
    sys.exit(1)

ks = Ks(KS_ARCH_X86, KS_MODE_32)
encoding, count = ks.asm(CODE)
shellcode = bytes(encoding)

print(f"[*] {count} instructions assemblées")
print(f"[*] Shellcode ({len(shellcode)} bytes): {shellcode.hex()}")
print(f"[*] Null bytes: {shellcode.count(0x00)}")

kernel32 = ctypes.windll.kernel32
kernel32.VirtualAlloc.restype = ctypes.c_void_p

addr = kernel32.VirtualAlloc(None, len(shellcode), 0x3000, 0x40)

if not addr:
    print("[!] VirtualAlloc failed")
    sys.exit(1)

ctypes.memmove(addr, shellcode, len(shellcode))
print(f"[*] Shellcode @ 0x{addr:08X}")

input("[*] Attache WinDbg maintenant, puis appuie sur Entrée...")

func = ctypes.CFUNCTYPE(None)(addr)
func()
