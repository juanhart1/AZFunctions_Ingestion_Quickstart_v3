import os
import json
import requests
import streamlit as st
from datetime import datetime

def trigger_ingestion_workflow(
    document_path: str,
    source_container: str = "rtx-transcripts",
    extract_container: str = "rtx-transcripts-extract",
    index_name: str = None,
    automatically_delete: bool = False,
    analyze_images: bool = False,
    overlapping_chunks: bool = True,
    chunk_size: int = 600,
    overlap: int = 200,
    embedding_model: str = "text-embedding-3-large",
    cosmos_logging: bool = False
) -> dict:
    """
    Trigger the document ingestion workflow using the Durable Function endpoint.
    
    Args:
        document_path: The path/name of the document in the source container
        source_container: The container where the document is stored
        extract_container: The container where extracted content will be stored
        index_name: The name of the index to use (if None, use the default)
        automatically_delete: Whether to delete the source document after processing
        analyze_images: Whether to analyze images in the document
        overlapping_chunks: Whether to create overlapping chunks
        chunk_size: The size of each chunk
        overlap: The amount of overlap between chunks
        embedding_model: The embedding model to use
        cosmos_logging: Whether to enable Cosmos DB logging
        
    Returns:
        A dictionary containing the response from the function or error info
    """
    try:
        # Get the function endpoint from environment variables
        function_url = os.environ.get("INGESTION_FUNCTION_URL")
        if not function_url:
            return {
                "success": False,
                "error": "INGESTION_FUNCTION_URL environment variable not set."
            }
            
        # Use default index if none provided
        if not index_name:
            index_name = os.environ.get("DEFAULT_INDEX_NAME", "test-index-20250603184251")
            
        # Prepare the request payload
        payload = {
            "source_container": source_container,
            "extract_container": extract_container,
            "prefix_path": document_path,
            "index_name": index_name,
            "automatically_delete": automatically_delete,
            "analyze_images": analyze_images,
            "overlapping_chunks": overlapping_chunks,
            "chunk_size": chunk_size,
            "overlap": overlap,
            "embedding_model": embedding_model,
            "cosmos_logging": cosmos_logging
        }
        
        # Make the HTTP request to the function endpoint
        response = requests.post(
            function_url,
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        # Check if the request was successful
        if response.status_code in (200, 201, 202):
            # Parse the response which contains the Durable Functions status URLs
            durable_response = response.json() if response.text else {"message": "Ingestion process started"}
            
            # Create a result object with both success status and the full response for status tracking
            result = {
                "success": True,
                "data": durable_response,
                "status_code": response.status_code,
                "document_path": document_path,
                "timestamp": datetime.now().isoformat()
            }
            
            return result
        else:
            return {
                "success": False,
                "error": f"Error {response.status_code}: {response.text}",
                "status_code": response.status_code
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception occurred: {str(e)}"
        }
        
def display_ingestion_params_form():
    """
    Display a form for configuring ingestion parameters.
    
    Returns:
        A dictionary containing the ingestion parameters if the form is submitted,
        None otherwise.
    """
    # Initialize session state for storing ingestion params if it doesn't exist
    if "ingestion_settings" not in st.session_state:
        st.session_state.ingestion_settings = {
            "index_name": os.environ.get("DEFAULT_INDEX_NAME", "test-index-1-20250604155829"),
            "automatically_delete": False,
            "analyze_images": False,  # Set to False by default
            "overlapping_chunks": True,
            "chunk_size": 600,
            "overlap": 200,
            "embedding_model": "text-embedding-3-large",
            "cosmos_logging": False
        }
    
    with st.expander("Advanced Ingestion Settings", expanded=False):
        # Get available indexes or use a default
        default_index = os.environ.get("DEFAULT_INDEX_NAME", "test-index-20250603184251")
        
        # Try to get a list of indexes (this would be implemented based on your system)
        # In a real implementation, you might fetch this from Azure Search
        try:
            available_indexes = [default_index]  # Placeholder - would be populated from API
        except:
            available_indexes = [default_index]
        
        # Use columns for better layout
        col1, col2 = st.columns(2)
        
        with col1:
            st.session_state.ingestion_settings["index_name"] = st.selectbox(
                "Index Name", 
                options=available_indexes,
                index=0,
                key="ingestion_index_name"
            )
            
            st.session_state.ingestion_settings["analyze_images"] = st.checkbox(
                "Analyze Images", 
                value=st.session_state.ingestion_settings.get("analyze_images", False),  # Default to False
                key="ingestion_analyze_images"
            )
            
            st.session_state.ingestion_settings["overlapping_chunks"] = st.checkbox(
                "Overlapping Chunks", 
                value=st.session_state.ingestion_settings.get("overlapping_chunks", True),
                key="ingestion_overlapping_chunks"
            )
            
        with col2:
            st.session_state.ingestion_settings["chunk_size"] = st.number_input(
                "Chunk Size", 
                value=st.session_state.ingestion_settings.get("chunk_size", 600), 
                min_value=100, 
                max_value=2000,
                key="ingestion_chunk_size"
            )
            
            st.session_state.ingestion_settings["overlap"] = st.number_input(
                "Overlap", 
                value=st.session_state.ingestion_settings.get("overlap", 200), 
                min_value=0, 
                max_value=st.session_state.ingestion_settings.get("chunk_size", 600)-100,
                key="ingestion_overlap"
            )
            
            embedding_models = ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"]
            embedding_model_index = 0
            if st.session_state.ingestion_settings.get("embedding_model") in embedding_models:
                embedding_model_index = embedding_models.index(st.session_state.ingestion_settings.get("embedding_model"))
                
            st.session_state.ingestion_settings["embedding_model"] = st.selectbox(
                "Embedding Model", 
                options=embedding_models, 
                index=embedding_model_index,
                key="ingestion_embedding_model"
            )
        
        # Additional options
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.ingestion_settings["automatically_delete"] = st.checkbox(
                "Auto-delete Source", 
                value=st.session_state.ingestion_settings.get("automatically_delete", False),
                key="ingestion_auto_delete"
            )
        with col2:
            st.session_state.ingestion_settings["cosmos_logging"] = st.checkbox(
                "Cosmos Logging", 
                value=st.session_state.ingestion_settings.get("cosmos_logging", False),
                key="ingestion_cosmos_logging"
            )
        
        # Button to apply settings
        if st.button("Apply Settings", key="apply_ingestion_settings"):
            st.success("Ingestion settings applied!")
        
        # Return the current ingestion settings
        return st.session_state.ingestion_settings

def check_ingestion_status(status_query_uri: str) -> dict:
    """
    Check the status of an ingestion process using the Durable Functions status URL.
    
    Args:
        status_query_uri: The URI to query for status updates (from the durable function response)
        
    Returns:
        A dictionary containing the status information or error details
    """
    try:
        # Make a GET request to the status URL
        response = requests.get(status_query_uri)
        
        # Check if the request was successful
        if response.status_code == 200:
            status_data = response.json()
            
            # Extract relevant status information
            result = {
                "success": True,
                "orchestrator_name": status_data.get("name", "Unknown"),
                "instance_id": status_data.get("instanceId", "Unknown"),
                "runtime_status": status_data.get("runtimeStatus", "Unknown"),
                "custom_status": status_data.get("customStatus", ""),
                "created_time": status_data.get("createdTime", ""),
                "last_updated_time": status_data.get("lastUpdatedTime", ""),
                "raw_data": status_data  # Include the full raw response for debugging
            }
            
            # If the orchestration has failed or completed, include the output/error
            if status_data.get("runtimeStatus") in ["Failed", "Completed"]:
                result["output"] = status_data.get("output", "")
            
            return result
        else:
            return {
                "success": False,
                "error": f"Error {response.status_code}: {response.text}",
                "status_code": response.status_code
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Exception occurred when checking status: {str(e)}"
        }
