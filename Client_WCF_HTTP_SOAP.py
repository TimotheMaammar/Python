# Simple client servant à requêter un service WCF (Windows Communication Foundation) exposé en HTTP SOAP

# pipx install zeep --include-deps
# OU
# sudo apt install python3-zeep

from zeep import Client

adresse="http://IP:PORT/WS/SearchWS.svc?wsdl"
methode="GetPersonalAssignmentByPhone"
arguments="0123456789"

client = Client(adresse)

method_to_call = getattr(client.service, methode)
response = method_to_call(arguments)

print(response)
