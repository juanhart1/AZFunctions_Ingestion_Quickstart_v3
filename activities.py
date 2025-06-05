import azure.functions as func
import logging
import json
import os
from azure.storage.blob import BlobServiceClient
from aoai_utilities import generate_hierarchical_summary

async def generate_document_summary(activitypayload: str) -> str:
    """
    Generate a hierarchical summary for a document and save it in a summary container.
    
    Args:
        activitypayload (str): JSON string containing:
            - doc_intel_formatted_results_container: container name with document intelligence results
            - summary_container: container name for storing summaries
            - file: name of the file to summarize
            
    Returns:
        str: Name of the generated summary file
    """
    try:
        # Parse input data
        input_data = json.loads(activitypayload)
        doc_intel_formatted_results_container = input_data['doc_intel_formatted_results_container']
        summary_container = input_data['summary_container']
        file_name = input_data['file']
        
        # Initialize blob service client
        blob_service_client = BlobServiceClient.from_connection_string(os.environ["STORAGE_CONN_STR"])
        
        # Ensure summary container exists
        summary_container_client = blob_service_client.get_container_client(summary_container)
        if not summary_container_client.exists():
            summary_container_client.create_container()
        
        # Get the source document blob
        source_container_client = blob_service_client.get_container_client(doc_intel_formatted_results_container)
        source_blob_client = source_container_client.get_blob_client(file_name)
        
        # Download and read the source content
        source_content = json.loads(source_blob_client.download_blob().readall().decode())
        
        # Generate hierarchical summary
        summary = generate_hierarchical_summary(source_content['text'])
        
        # Create summary file name
        summary_file_name = file_name.replace('.json', '_summary.json')
        
        # Upload the summary
        summary_blob = summary_container_client.get_blob_client(summary_file_name)
        summary_blob.upload_blob(json.dumps(summary), overwrite=True)
        
        return summary_file_name
        
    except Exception as e:
        logging.error(f"Error in generate_document_summary: {str(e)}")
        raise