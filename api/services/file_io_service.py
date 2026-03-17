from pathlib import Path

from openai import OpenAI
import os
from azure.storage.blob import BlobClient, BlobServiceClient

__connection_string = os.getenv('STORAGE_CONNECTION_STRING') or ''
__base_container_name = os.getenv('STORAGE_CONTAINER') or 'healthproto-container'


def get_blob_service():
    
    if not __connection_string:
        raise ValueError("STORAGE_CONNECTION_STRING environment variable is not set.")
    
    return BlobServiceClient.from_connection_string(conn_str=__connection_string)

def upload_to_blob_storage(blob_storage: BlobServiceClient,
                           file_path: str, blob_name: str):
    blob_storage.get_blob_client(__connection_string, blob_name)
    

def upload_file_to_bstore(
                          blob_service: BlobServiceClient,
                          file_path: str, 
                          blob_name: str,
                          container_name: str,
                          overwrite: bool = True):
    upload_file = Path(file_path)
    
    if not upload_file.is_file():
        raise ValueError("Couldn't retrieve file for upload")
    
    blob_client =blob_service.get_blob_client(
        container=container_name,
        blob=blob_name or upload_file.name
    )
    
    blob_client.upload_blob(upload_file.open("rb"), overwrite=overwrite)
    
    
def create_container(blob_service: BlobServiceClient, container_name: str):
    try:
        blob_service.create_container(f"{__base_container_name}/{container_name}")
    except Exception as e:
        print(f"Container creation failed: {e}")
    

def upload_data_file(client: OpenAI, path: str) -> str:
    """
    Uploads a local file at path to OpenAI as a user data file using the
    provided client. Returns the uploaded file's ID. Raises ValueError if
    the file does not exist.
    """
    p = Path(path)
    if not p.is_file():
        raise ValueError("File does not exist")
    
    with p.open("rb") as f:
        f_object = client.files.create(file=f, purpose="user_data")
    return f_object.id

