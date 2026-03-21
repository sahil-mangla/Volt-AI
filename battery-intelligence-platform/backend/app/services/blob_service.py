import os
import logging
from azure.storage.blob import BlobServiceClient
from fastapi import UploadFile

logger = logging.getLogger(__name__)

# Constants
CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
CONTAINER_NAME = os.getenv("BLOB_CONTAINER_NAME", "battery-data")

class BlobService:
    def __init__(self):
        self.blob_service_client = None
        self.container_client = None
        
        if CONNECTION_STRING:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(CONNECTION_STRING)
                self.container_client = self.blob_service_client.get_container_client(CONTAINER_NAME)
                
                # Auto-create container if missing
                if not self.container_client.exists():
                    self.container_client.create_container()
                    logger.info(f"Created Azure Blob Container: {CONTAINER_NAME}")
            except Exception as e:
                logger.error(f"Failed to initialize Blob Client: {e}")
        else:
            logger.warning("AZURE_STORAGE_CONNECTION_STRING is not set. Blob storage features will be unavailable.")

    async def upload_file(self, file: UploadFile) -> str:
        if not self.container_client:
            raise ValueError("Blob storage is not configured properly.")
            
        try:
            blob_client = self.container_client.get_blob_client(file.filename)
            # Support huge async streams using spooled temps
            contents = await file.read()
            blob_client.upload_blob(contents, overwrite=True)
            logger.info(f"Successfully uploaded {file.filename} to Blob Storage.")
            
            # Reset cursor cleanly
            await file.seek(0)
            return blob_client.url
        except Exception as e:
            logger.error(f"Upload failed: {e}")
            raise Exception(f"Upload logic failure: {e}")

    def list_files(self) -> list:
        if not self.container_client:
            raise ValueError("Blob storage is not configured properly.")
            
        files = []
        try:
            blobs = self.container_client.list_blobs()
            for blob in blobs:
                files.append({
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified
                })
            return files
        except Exception as e:
            logger.error(f"Listing failed: {e}")
            raise Exception("Listing failure")

    def download_file_to_bytes(self, filename: str) -> bytes:
        if not self.container_client:
            raise ValueError("Blob storage is not configured properly.")
            
        try:
            blob_client = self.container_client.get_blob_client(filename)
            downloader = blob_client.download_blob()
            return downloader.readall()
        except Exception as e:
            logger.error(f"Download failed for {filename}: {e}")
            raise Exception(f"Download failure: {e}")

blob_service = BlobService()
