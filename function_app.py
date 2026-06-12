import datetime
import logging
import os
import azure.functions as fap
from azure.storage.blob import BlobServiceClient

# Initialisation de l'application de fonctions Azure
app = fap.FunctionApp()

# Configuration du déclencheur : s'exécute toutes les 30 minutes
# run_on_startup=True force l'exécution immédiate au démarrage de l'application
@app.timer_trigger(schedule="0 */30 * * * *", arg_name="myTimer", run_on_startup=True, use_monitor=False)
def clean_blob_storage(myTimer: fap.TimerRequest) -> None:
    logging.info('Début du nettoyage automatique du Storage Account...')
    
    # Récupération de la chaîne de connexion depuis les variables d'environnement d'Azure
    connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
    container_name = "fichiers-api" 
    
    # Ancienneté maximale configurable (5 minutes par défaut)
    max_age_minutes = int(os.getenv("MAX_AGE_MINUTES", "5"))
    
    if not connection_string:
        logging.error("Erreur : La variable d'environnement 'AZURE_STORAGE_CONNECTION_STRING' est manquante dans la configuration.")
        return

    try:
        # Connexion au service Azure Blob Storage
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
        
        # Récupération de l'heure actuelle au format UTC (Azure stocke les dates des fichiers en UTC)
        now = datetime.datetime.now(datetime.timezone.utc)
        logging.info(f"Heure de référence actuelle (UTC) : {now}")
        
        # Liste de tous les blobs du conteneur
        blobs = container_client.list_blobs()
        deleted_count = 0
        
        for blob in blobs:
            # blob.last_modified contient la date de dernière modification (avec fuseau horaire UTC)
            last_modified = blob.last_modified
            age = now - last_modified
            age_in_minutes = age.total_seconds() / 60
            
            logging.info(f"Analyse du fichier : '{blob.name}' | Âge actuel : {age_in_minutes:.2f} minutes")
            
            # Si le fichier dépasse le seuil autorisé
            if age_in_minutes > max_age_minutes:
                logging.info(f"--> Suppression requise : '{blob.name}' ({age_in_minutes:.2f} min > {max_age_minutes} min)")
                container_client.delete_blob(blob.name)
                deleted_count += 1
                
        logging.info(f"Opération terminée avec succès. Nombre de fichiers supprimés : {deleted_count}")
        
    except Exception as e:
        logging.error(f"Une erreur est survenue lors de l'exécution du nettoyage : {str(e)}")