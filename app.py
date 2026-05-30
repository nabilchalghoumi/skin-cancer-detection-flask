from flask import Flask, render_template, request, redirect, session, flash
import os
import numpy as np
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing import image
import mysql.connector

# Initialisation de l'application Flask
app = Flask(__name__)
app.secret_key = "secret"  # Clé obligatoire pour utiliser les sessions et messages flash

# Configuration du dossier de stockage des images
UPLOAD_FOLDER = "static/uploads/"
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# 1. Chargement du modèle VGG16 pré-entraîné
# Configuration dynamique du dossier du modèle
model_path = os.path.join(os.path.dirname(__file__), "model", "vgg16_skin_cancer.h5")
model = load_model(model_path)
# 2. Configuration de la connexion à la base de données MySQL
db = mysql.connector.connect(
    host="localhost",
    user="root",        # Utilisateur par défaut sous XAMPP
    password="",        # Pas de mot de passe par défaut
    database="skin_cancer_db"
)

# Création du curseur pour exécuter des requêtes SQL (avec option Dictionnaire)
cursor = db.cursor(dictionary=True)

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form["username"]
        pwd = request.form["password"]
        
        # Requête SQL pour vérifier si l'utilisateur existe
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (user, pwd))
        result = cursor.fetchone()
        
        if result:
            session["user"] = user  # Création de la session utilisateur
            flash("Login réussi ! ", "success")
            return redirect("/dashboard")
        else:
            flash("Erreur login ou mot de passe incorrect.", "danger")
            return render_template("login.html")
            
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    # Sécurisation : si l'utilisateur n'est pas connecté, retour à la page de connexion
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html")

@app.route("/predict", methods=["GET", "POST"])
def predict():
    if "user" not in session:
        return redirect("/")
        
    if request.method == "POST":
        try:
            name = request.form["name"]
            age = request.form["age"]
            file = request.files["image"]
            
            if file.filename == "":
                flash("Veuillez choisir une image", "warning")
                return redirect("/predict")
                
            # Sauvegarde physique du fichier dans static/uploads/
            path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(path)
            
            # Prétraitement de l'image pour l'IA VGG16
            img = image.load_img(path, target_size=(224, 224)) # Redimensionnement
            img_array = image.img_to_array(img) / 255.0         # Conversion en tableau et normalisation
            img_ready = np.expand_dims(img_array, axis=0)       # Expansion des dimensions (batch size)
            
            # Appel du modèle pour effectuer la prédiction
            pred = model.predict(img_ready)[0][0]
            
            # Seuil de décision : supérieur à 0.5 signifie Malin (Malignant), sinon Bénin (Benign)
            result = "Malignant" if pred > 0.5 else "Benign"
            
            # Enregistrement du diagnostic dans la base de données MySQL
            cursor.execute("""
                INSERT INTO patients (name, age, result, probability, image_path)
                VALUES (%s, %s, %s, %s, %s)
            """, (name, age, result, float(pred), path))
            db.commit() # Confirmation des changements
            
            flash("Analyse réussie ! ", "success")
            return render_template("result.html", result=result, prob=round(pred * 100, 2), img=file.filename)
            
        except Exception as e:
            flash(f"Erreur système lors de l'analyse : {str(e)}", "danger")
            return redirect("/predict")
            
    return render_template("predict.html")

@app.route("/patients")
def patients():
    if "user" not in session:
        return redirect("/")
        
    # Récupération de l'historique trié par date décroissante
    cursor.execute("SELECT * FROM patients ORDER BY created_at DESC")
    patients_data = cursor.fetchall()
    
    return render_template("patients.html", patients=patients_data)

@app.route("/logout")
def logout():
    session.clear() # Fermeture et nettoyage de la session
    flash("Vous avez été déconnecté avec succès.", "info")
    return redirect("/")

# Lancement de l'application de développement Flask
if __name__ == "__main__":
    app.run(debug=True)