# Script permettant de faire des captures d'écran de tout un document protégé et de les fusionner en PDF
# Créer un dossier par document à scanner et mettre le script dedans
# Il y a parfois un petit décalage à cause de la touche PgDn qui ne descend pas toujours strictement d'une page
# Faire des tests et ajuster le nombre de pages si besoin


import subprocess, time, os
from pynput.keyboard import Key, Controller
from PIL import Image

clavier = Controller()
pages = int(input("Entrez le nombre de pages : "))
print("OK. Retournez sur le document et activez le mode plein écran (F11), le scan va démarrer dans cinq secondes")
time.sleep(5)

### Itération
i = 0
liste_images = []
for i in range(pages):
    nom = str(i)+".png" 
    subprocess.call(["spectacle", "-b", "-n", "-o", nom]) # À changer si besoin, Spectacle est l'outil de capture d'écran natif de KDE
    image = Image.open(nom)
    liste_images.append(image)

    clavier.press(Key.page_down)
    clavier.release(Key.page_down)

### Conversion
pdf = "./Scan.pdf"
image = Image.open("./0.png") # Évite que la page de fin se retrouve copiée au tout début du PDF
image.save(pdf, "PDF", resolution=100.0, save_all=True, append_images=liste_images)



### Nettoyage
dossier = os.listdir("./")
for fichier in dossier:
    if fichier.endswith(".png"):
        os.remove(os.path.join("./",fichier))

