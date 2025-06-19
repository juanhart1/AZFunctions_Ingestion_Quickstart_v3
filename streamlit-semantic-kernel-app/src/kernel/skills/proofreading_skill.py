from azure.storage.blob import BlobServiceClient
import os
import json

class ProofreadingSkill:
    def __init__(self):
        # Get Azure Blob Storage credentials from environment variables
        self.storage_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.proofreading_container = os.environ.get("PROOFREADING_CONTAINER")
        
        # Initialize blob service client if credentials are available
        if self.storage_connection_string and self.proofreading_container:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
            self.container_client = self.blob_service_client.get_container_client(self.proofreading_container)
        else:
            self.blob_service_client = None
            self.container_client = None
            print("Warning: Azure Blob Storage credentials not found. Proofreading Skill will not function.")
    
    def get_proofread(self, document_id: str = None) -> str:
        """
        Retrieve the proofreading results for a document from Azure Blob Storage.
        
        Args:
            document_id: The ID of the document to proofread
            
        Returns:
            The proofreading results for the document
        """
        if not self.container_client:
            return "Error: Azure Blob Storage client not initialized."
        
        if not document_id:
            return "Error: No document ID provided."
        
        try:
            # Get the proofreading blob
            blob_client = self.container_client.get_blob_client(f"{document_id}/proofreading.json")
            
            # Download the proofreading results
            download_stream = blob_client.download_blob()
            proofreading_data = json.loads(download_stream.readall().decode("utf-8"))
            
            # Format the proofreading results
            if "errors" in proofreading_data and len(proofreading_data["errors"]) > 0:
                result = "Proofreading found the following issues:\n\n"
                for i, error in enumerate(proofreading_data["errors"], 1):
                    result += f"{i}. {error['type']}: {error['text']} - {error['suggestion']}\n"
                return result
            else:
                return "No proofreading issues found in this document."
                
        except Exception as e:
            return f"Error retrieving proofreading results: {str(e)}"
