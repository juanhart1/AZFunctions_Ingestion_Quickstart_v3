from azure.storage.blob import BlobServiceClient
import os
import json

class SummarizationSkill:
    def __init__(self):
        # Get Azure Blob Storage credentials from environment variables
        self.storage_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.summary_container = os.environ.get("SUMMARY_CONTAINER")
        
        # Initialize blob service client if credentials are available
        if self.storage_connection_string and self.summary_container:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
            self.container_client = self.blob_service_client.get_container_client(self.summary_container)
        else:
            self.blob_service_client = None
            self.container_client = None
            print("Warning: Azure Blob Storage credentials not found. Summarization Skill will not function.")
    
    def get_summary(self, document_id: str = None) -> str:
        """
        Retrieve the summary for a document from Azure Blob Storage.
        
        Args:
            document_id: The ID of the document to summarize
            
        Returns:
            The summary of the document
        """
        if not self.container_client:
            return "Error: Azure Blob Storage client not initialized."
        
        if not document_id:
            return "Error: No document ID provided."
        
        try:
            # Get the summary blob
            blob_client = self.container_client.get_blob_client(f"{document_id}/summary.json")
            
            # Download the summary
            download_stream = blob_client.download_blob()
            summary_data = json.loads(download_stream.readall().decode("utf-8"))
            
            # Format the summary
            if "summary" in summary_data:
                return summary_data["summary"]
            else:
                return "No summary available for this document."
                
        except Exception as e:
            return f"Error retrieving summary: {str(e)}"
