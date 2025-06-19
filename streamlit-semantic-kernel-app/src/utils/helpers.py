import streamlit as st
import os
import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient

def display_file_selector(container_name, connection_string_var):
    """
    Display a file selector for a blob container.
    
    Args:
        container_name: The name of the blob container
        connection_string_var: The environment variable containing the connection string
        
    Returns:
        The selected document ID, or None if no document is selected
    """
    # Get the connection string from environment variables
    connection_string = os.environ.get(connection_string_var)
    
    if not connection_string:
        st.error(f"Error: {connection_string_var} environment variable not set")
        return None
    
    # Initialize the blob service client
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
    except Exception as e:
        st.error(f"Error connecting to blob storage: {str(e)}")
        return None
    
    # Get a list of document IDs
    try:
        # List all blobs in the container
        blobs = container_client.list_blobs()
        
        # Extract unique document IDs from blob names
        document_ids = set()
        for blob in blobs:
            # Blob names are expected to be in the format "document_id/file.ext"
            parts = blob.name.split('/')
            if len(parts) > 0:
                document_ids.add(parts[0])
        
        document_ids = sorted(list(document_ids))
        
    except Exception as e:
        st.error(f"Error listing blobs: {str(e)}")
        return None
    
    # Display the dropdown
    if len(document_ids) > 0:
        selected_document = st.selectbox("Select a document", document_ids)
        return selected_document
    else:
        st.info("No documents found in the container")
        return None

def display_result(result, result_type):
    """
    Display a formatted result.
    
    Args:
        result: The result to display
        result_type: The type of result ("qna", "summarization", or "proofreading")
    """
    if result_type == "qna":
        st.subheader("Answer")
        st.write(result)
    elif result_type == "summarization":
        st.subheader("Summary")
        st.write(result)
    elif result_type == "proofreading":
        st.subheader("Proofreading Results")
        st.write(result)
    else:
        st.write(result)
