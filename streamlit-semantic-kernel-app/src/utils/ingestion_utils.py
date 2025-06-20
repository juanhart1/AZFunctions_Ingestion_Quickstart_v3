import os
import json
import requests
import streamlit as st

def trigger_ingestion_workflow(
    document_path: str,
    source_container: str = "rtx-transcripts",
    extract_container: str = "rtx-transcripts-extract",
    index_name: str = None,
    automatically_delete: bool = False,
    analyze_images: bool = True,
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
            return {
                "success": True,
                "data": response.json() if response.text else {"message": "Ingestion process started"},
                "status_code": response.status_code
            }
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
    with st.expander("Advanced Ingestion Settings", expanded=False):
        with st.form("ingestion_params"):
            # Get available indexes or use a default
            default_index = os.environ.get("DEFAULT_INDEX_NAME", "test-index-20250603184251")
            
            # Try to get a list of indexes (this would be implemented based on your system)
            # In a real implementation, you might fetch this from Azure Search
            try:
                available_indexes = [default_index]  # Placeholder - would be populated from API
            except:
                available_indexes = [default_index]
                
            col1, col2 = st.columns(2)
            
            with col1:
                index_name = st.selectbox(
                    "Index Name", 
                    options=available_indexes,
                    index=0
                )
                
                analyze_images = st.checkbox("Analyze Images", value=True)
                overlapping_chunks = st.checkbox("Overlapping Chunks", value=True)
                
            with col2:
                chunk_size = st.number_input("Chunk Size", value=600, min_value=100, max_value=2000)
                overlap = st.number_input("Overlap", value=200, min_value=0, max_value=chunk_size-100)
                
                embedding_models = ["text-embedding-3-large", "text-embedding-3-small", "text-embedding-ada-002"]
                embedding_model = st.selectbox("Embedding Model", options=embedding_models, index=0)
            
            # Additional options
            col1, col2 = st.columns(2)
            with col1:
                automatically_delete = st.checkbox("Auto-delete Source", value=False)
            with col2:
                cosmos_logging = st.checkbox("Cosmos Logging", value=False)
                
            submitted = st.form_submit_button("Save Settings")
            
            if submitted:
                ingestion_params = {
                    "index_name": index_name,
                    "automatically_delete": automatically_delete,
                    "analyze_images": analyze_images,
                    "overlapping_chunks": overlapping_chunks,
                    "chunk_size": chunk_size,
                    "overlap": overlap,
                    "embedding_model": embedding_model,
                    "cosmos_logging": cosmos_logging
                }
                
                # Save to session state for persistence
                st.session_state["ingestion_params"] = ingestion_params
                st.success("Ingestion settings saved!")
                return ingestion_params
                
            # Return current parameters if they exist, otherwise None
            return st.session_state.get("ingestion_params", None)
