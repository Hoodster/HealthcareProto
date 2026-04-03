from pathlib import Path
from typing import Literal

from openai import OpenAI
import os
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv

load_dotenv()

__connection_string__ = os.getenv('STORAGE_CONNECTION_STRING', '')
__base_container_name__ = os.getenv('STORAGE_CONTAINER', '')
__blob_service__ = BlobServiceClient.from_connection_string(conn_str=__connection_string__)

type BlobDocumentType = Literal['patient_file', 'knowledge_base']

try:
    base_container = __blob_service__.create_container(__base_container_name__)
except Exception as e:
    print(f"Container creation failed: {e}")
    base_container = __blob_service__.get_container_client(__base_container_name__)


def __upload_to_blob_storage__(file_path: str | Path, blob_name: str, overwrite: bool = True):
    if isinstance(file_path, str):
        file_path = Path(file_path)

    with file_path.open("rb") as upfile:
        base_container.upload_blob(name=blob_name, data=upfile, overwrite=overwrite)
        upfile.close()

def upload(
                          file_name: str,
                          file_path: str,
                          document_type: BlobDocumentType,
                          overwrite: bool = True):
    upload_file = Path(file_path)
    if not upload_file.is_file():
        raise ValueError("Couldn't retrieve file for upload")

    if document_type == 'patient_file':
        subcontainer_name = "docs/"
    elif document_type == 'knowledge_base':
        subcontainer_name = "kb/"
    else:
        raise ValueError("Invalid document type")

    if document_type == 'patient_file' and "/" not in file_name:
        raise ValueError("Patient related files must have {reference}/file.ext format")

    blob_path = f"{subcontainer_name}/{file_name}"
    __upload_to_blob_storage__(
        file_path=upload_file,
        blob_name=blob_path,
        overwrite=overwrite
    )


def ai_document_upload(
    client: OpenAI,
    file_path: str,
    document_type: BlobDocumentType
):
    pass

