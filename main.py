import os
from html import escape
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from fastapi.responses import HTMLResponse

# Chargement sécurisé de la variable d'environnement
load_dotenv(dotenv_path=Path(__file__).with_name(".env"))

app = FastAPI(title="API Fichiers Azure")

CONTAINER_NAME = "fichiers-api"


def get_container_client(create_if_missing: bool = False):
    """Récupère le client du conteneur Azure. Lève une erreur si la connexion manque."""
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    
    if not connection_string:
        raise HTTPException(status_code=500, detail="La chaîne de connexion Azure n'est pas configurée dans le fichier .env")
    
    blob_service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = blob_service_client.get_container_client(CONTAINER_NAME)
    
    if create_if_missing:
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass  # Le conteneur existe déjà
            
    return container_client


def upload_to_blob(file: UploadFile) -> dict:
    """Logique d'envoi du fichier vers Azure."""
    try:
        container_client = get_container_client(create_if_missing=True)
        blob_client = container_client.get_blob_client(file.filename)
        
        # On envoie le flux du fichier (file.file) directement vers Azure
        blob_client.upload_blob(file.file, overwrite=True)
        return {"message": f"Fichier '{file.filename}' uploadé avec succès."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur d'upload: {str(e)}")


def delete_blob(filename: str) -> dict:
    """Logique de suppression d'un blob sur Azure."""
    try:
        container_client = get_container_client()
        blob_client = container_client.get_blob_client(filename)
        blob_client.delete_blob()
        return {"message": f"Fichier '{filename}' supprimé avec succès."}
    except ResourceNotFoundError:
        raise HTTPException(status_code=404, detail="Fichier introuvable sur Azure.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erreur de suppression: {str(e)}")


# ==========================================
# ROUTES DE L'API REST
# ==========================================

@app.get("/files")
def list_files() -> dict:
    """Liste les noms de tous les blobs présents dans le conteneur."""
    try:
        container_client = get_container_client()
        blobs = container_client.list_blobs()
        # On extrait uniquement les noms des fichiers
        return {"files": [blob.name for blob in blobs]}
    except ResourceNotFoundError:
        return {"files": []} # Le conteneur n'existe pas encore
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
def upload_file(file: UploadFile = File(...)) -> dict:
    """Reçoit un fichier et l'envoie dans le conteneur Azure."""
    return upload_to_blob(file)


@app.delete("/remove")
def remove_file(filename: str) -> dict:
    """Supprime un fichier spécifique."""
    return delete_blob(filename)


# ==========================================
# INTERFACE UTILISATEUR (RACINE)
# ==========================================

@app.get("/", response_class=HTMLResponse)
def upload_page() -> str:
    """Interface simple pour appeller les 3 routes ci-dessus."""
    html_content = """
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="UTF-8">
        <title>Gestionnaire de fichiers Azure</title>
    </head>
    <body>
        <h1>Stockage Azure</h1>
        
        <div class="card">
            <h3>Envoyer un fichier</h3>
            <form id="uploadForm">
                <input type="file" id="fileInput" required>
                <button type="submit">Uploader</button>
            </form>
            <div id="status"></div>
        </div>

        <div class="card">
            <h3>Fichiers disponibles <button onclick="loadFiles()" style="font-size: 0.8em;">Actualiser</button></h3>
            <ul id="fileList"></ul>
        </div>

        <script>
            // Appelle GET /files
            async function loadFiles() {
                const response = await fetch('/files');
                const data = await response.json();
                const list = document.getElementById('fileList');
                list.innerHTML = '';
                
                if (data.files && data.files.length > 0) {
                    data.files.forEach(filename => {
                        const li = document.createElement('li');
                        li.textContent = filename;
                        
                        const btn = document.createElement('button');
                        btn.textContent = 'Supprimer';
                        btn.onclick = () => deleteFile(filename);
                        
                        li.appendChild(btn);
                        list.appendChild(li);
                    });
                } else {
                    list.innerHTML = '<li>Aucun fichier trouvé.</li>';
                }
            }

            // Appelle DELETE /remove
            async function deleteFile(filename) {
                if (!confirm(`Voulez-vous vraiment supprimer "${filename}" ?`)) return;
                
                const response = await fetch(`/remove?filename=${encodeURIComponent(filename)}`, { 
                    method: 'DELETE' 
                });
                
                if (response.ok) {
                    loadFiles(); // On recharge la liste après suppression
                } else {
                    alert('Erreur lors de la suppression.');
                }
            }

            // Appelle POST /upload
            document.getElementById('uploadForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                const fileInput = document.getElementById('fileInput');
                if (fileInput.files.length === 0) return;
                
                const formData = new FormData();
                formData.append('file', fileInput.files[0]);
                
                const statusDiv = document.getElementById('status');
                statusDiv.textContent = "Upload en cours...";
                
                const response = await fetch('/upload', {
                    method: 'POST',
                    body: formData
                });
                
                if (response.ok) {
                    statusDiv.textContent = "Fichier envoyé avec succès !";
                    fileInput.value = ''; // On vide le champ
                    loadFiles();          // On met à jour la liste
                    setTimeout(() => statusDiv.textContent = '', 3000);
                } else {
                    statusDiv.textContent = "Erreur lors de l'upload.";
                    statusDiv.style.color = "red";
                }
            });

            // Charge les fichiers au démarrage de la page
            loadFiles();
        </script>
    </body>
    </html>
    """
    return html_content