import streamlit as st
import os
import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from utils.file_upload import upload_file_to_blob

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

def display_file_uploader(container_name, connection_string_var, key=None):
    """
    Display a file uploader for uploading PDFs to Azure Blob Storage.
    
    Args:
        container_name: The name of the blob container
        connection_string_var: The environment variable containing the connection string
        key: Optional key for the Streamlit file_uploader widget
        
    Returns:
        Tuple of (success, document_id) where success is a boolean and document_id is the ID of the uploaded document
    """
    # Create the file uploader widget
    uploaded_file = st.file_uploader(
        "Upload a PDF document", 
        type=["pdf"], 
        key=key,
        help="Upload a PDF file to process. The file will be stored in Azure Blob Storage."
    )
    
    if uploaded_file is not None:
        # Display a preview of the file
        st.write(f"Selected file: **{uploaded_file.name}**")
        
        # Add an upload button
        if st.button("Upload to Azure", key=f"upload_btn_{key}"):
            with st.spinner("Uploading file to Azure..."):
                # Upload the file using our utility function
                success, document_id, error_message = upload_file_to_blob(
                    uploaded_file=uploaded_file,
                    container_name=container_name,
                    connection_string_var=connection_string_var
                )
                
                if success:
                    st.success(f"File uploaded successfully! Document ID: {document_id}")
                    return True, document_id
                else:
                    st.error(error_message)
                    return False, None
    
    return False, None

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
