import os
from azure.storage.blob import BlobServiceClient, ContentSettings
import streamlit as st
import uuid
import time

def upload_file_to_blob(uploaded_file, container_name, connection_string_var=None, connection_string=None):
    """
    Upload a file to Azure Blob Storage.
    
    Files are stored directly in the container root with document_id as a prefix for uniqueness.
    Example: "doc_1234567_unique_id_filename.pdf" instead of "doc_1234567_unique_id/filename.pdf"
    
    Args:
        uploaded_file: The file uploaded through Streamlit's file_uploader
        container_name: The name of the container to upload to
        connection_string_var: The environment variable containing the connection string
        connection_string: The direct connection string (use this or connection_string_var)
        
    Returns:
        A tuple of (success, document_id, error_message)
    """
    try:
        # Get connection string (either direct or from environment variable)
        if connection_string is None:
            if connection_string_var is None:
                connection_string_var = "AZURE_STORAGE_CONNECTION_STRING"
            connection_string = os.environ.get(connection_string_var)
        
        if not connection_string:
            return False, None, f"Error: {connection_string_var} environment variable not set"
        
        # Initialize the blob service client
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        
        # Get or create the container
        try:
            container_client = blob_service_client.get_container_client(container_name)
            # Check if container exists
            container_client.get_container_properties()
        except Exception:
            # Create the container if it doesn't exist
            container_client = blob_service_client.create_container_client(container_name)
            container_client.create_container()
        
        # Generate a unique document ID (timestamp + UUID)
        timestamp = int(time.time())
        unique_id = str(uuid.uuid4())[:8]
        document_id = f"doc_{timestamp}_{unique_id}"
        
        # Store files directly in container root with document_id as prefix for uniqueness
        file_extension = uploaded_file.name.split('.')[-1].lower()
        # Use document_id as prefix to avoid filename collisions
        blob_name = f"{document_id}_{uploaded_file.name}"
        
        # Create a blob client and upload the file
        blob_client = container_client.get_blob_client(blob_name)
        
        # Set content settings based on file extension
        content_type = "application/pdf" if file_extension == "pdf" else uploaded_file.type
        content_settings = ContentSettings(content_type=content_type)
        
        # Upload the file
        blob_client.upload_blob(
            uploaded_file.getvalue(),
            content_settings=content_settings,
            overwrite=True
        )
        
        # Create a metadata JSON file with document information
        metadata = {
            "document_id": document_id,
            "original_filename": uploaded_file.name,
            "content_type": content_type,
            "upload_timestamp": timestamp,
            "size_bytes": len(uploaded_file.getvalue())
        }
        
        # Upload the metadata file (also in root container with document_id prefix)
        metadata_blob_client = container_client.get_blob_client(f"{document_id}_metadata.json")
        metadata_blob_client.upload_blob(
            str(metadata).encode('utf-8'),
            content_settings=ContentSettings(content_type="application/json"),
            overwrite=True
        )
        
        return True, document_id, None
        
    except Exception as e:
        return False, None, f"Error uploading file: {str(e)}"
