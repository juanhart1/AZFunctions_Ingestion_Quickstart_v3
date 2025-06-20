from azure.storage.blob import BlobServiceClient
import os
import json

class SummarizationSkill:
    def __init__(self):
        # Get Azure Blob Storage credentials from environment variables
        self.storage_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.summary_container = os.environ.get("SUMMARY_CONTAINER")
        
        # Print debug information
        print(f"DEBUG: Summary container name: '{self.summary_container}'")
        if not self.storage_connection_string:
            print("WARNING: AZURE_STORAGE_CONNECTION_STRING not set")
        if not self.summary_container:
            print("WARNING: SUMMARY_CONTAINER not set, using default 'summaries'")
            self.summary_container = "summaries"  # Set a default value
        
        # Initialize blob service client if credentials are available
        if self.storage_connection_string and self.summary_container:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
                self.container_client = self.blob_service_client.get_container_client(self.summary_container)
                
                # Check if container exists
                try:
                    container_properties = self.container_client.get_container_properties()
                    print(f"DEBUG: Successfully connected to container '{self.summary_container}'")
                except Exception as container_error:
                    print(f"WARNING: Container '{self.summary_container}' may not exist: {str(container_error)}")
                    
            except Exception as e:
                print(f"ERROR initializing blob service: {str(e)}")
                self.blob_service_client = None
                self.container_client = None
        else:
            self.blob_service_client = None
            self.container_client = None
            print("Warning: Azure Blob Storage credentials not found. Summarization Skill will not function.")
    
    def get_summary(self, document_id: str = None) -> str:
        """
        Retrieve the summary for a document from Azure Blob Storage.
        
        Files are stored with document_id as a prefix: "{document_id}_summary.json"
        Legacy format support is maintained for: "{document_id}/summary.json"
        
        Args:
            document_id: The ID of the document to summarize
            
        Returns:
            The summary of the document
        """
        if not self.container_client:
            return {"error": "Error: Azure Blob Storage client not initialized."}
        
        if not document_id:
            return {"error": "Error: No document ID provided."}
        
        try:
            # Construct the expected blob path (new format: document_id_summary.json)
            blob_path = f"{document_id}_summary.json"
            
            # Get the summary blob client
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Check if the blob exists before attempting to download
            if not blob_client.exists():
                print(f"DEBUG: Summary blob not found at path: {blob_path}")
                
                # Try alternative paths - support both new and legacy formats
                alternative_paths = [
                    # New format
                    f"{document_id}_summary.json",
                    # Legacy formats
                    f"{document_id}/summary.json",
                    document_id,
                    f"summary_{document_id}.json",  
                    f"{document_id.replace(' ', '_')}/summary.json",  
                    f"{document_id}.json"  
                ]
                
                blob_found = False
                for alt_path in alternative_paths:
                    alt_blob_client = self.container_client.get_blob_client(alt_path)
                    print(f"DEBUG: Checking alternative path: {alt_path}")
                    if alt_blob_client.exists():
                        print(f"DEBUG: Found blob at alternative path: {alt_path}")
                        blob_client = alt_blob_client
                        blob_found = True
                        break
                
                if not blob_found:
                    # List blobs in the container to help with debugging
                    print(f"DEBUG: Listing all blobs in container '{self.summary_container}' for debugging:")
                    try:
                        blobs = list(self.container_client.list_blobs(name_starts_with=document_id))
                        if blobs:
                            print(f"DEBUG: Found {len(blobs)} blobs starting with '{document_id}':")
                            for blob in blobs:
                                print(f"DEBUG: - {blob.name}")
                        else:
                            print(f"DEBUG: No blobs found starting with '{document_id}'")
                    except Exception as list_error:
                        print(f"DEBUG: Error listing blobs: {str(list_error)}")
                    
                    return {"error": f"No summary found for document '{document_id}'. The summary file does not exist in the blob container '{self.summary_container}'."}
            
            # Download the summary
            download_stream = blob_client.download_blob()
            summary_content = download_stream.readall().decode("utf-8")
            
            try:
                summary_data = json.loads(summary_content)
                print(f"DEBUG: Successfully parsed JSON from blob. Keys: {list(summary_data.keys())}")
                
                # Handle the specific structure format provided in the example
                if "summary" in summary_data and isinstance(summary_data["summary"], dict):
                    summary_section = summary_data["summary"]
                    
                    # Check for the specific format with Executive Summary, Detailed Summary, etc.
                    if "Executive Summary" in summary_section and "Detailed Summary" in summary_section:
                        return {
                            "executive": summary_section.get("Executive Summary", "No executive summary available."),
                            "detailed": summary_section.get("Detailed Summary", "No detailed summary available."),
                            "topics": summary_section.get("Key Topics/Themes", []),
                            "conclusions": summary_section.get("Main Conclusions/Takeaways", []),
                            "source_file": summary_data.get("sourcefile", ""),
                            "generated_date": summary_data.get("generated_date", "")
                        }
                    # Handle the previous expected format
                    elif "executive_summary" in summary_section and "detailed_summary" in summary_section:
                        return {
                            "executive": summary_section.get("executive_summary", "No executive summary available."),
                            "detailed": summary_section.get("detailed_summary", "No detailed summary available.")
                        }
                    else:
                        # Return what we have in the summary section
                        return {"summary": summary_section}
                elif "executive_summary" in summary_data and "detailed_summary" in summary_data:
                    # The summary might be at the root level
                    return {
                        "executive": summary_data.get("executive_summary", "No executive summary available."),
                        "detailed": summary_data.get("detailed_summary", "No detailed summary available.")
                    }
                else:
                    # If we can't find specific summary fields, return the whole content
                    return {"summary": f"Summary structure unclear. Raw content: {summary_content[:500]}..."}
            except json.JSONDecodeError as json_error:
                print(f"ERROR: Failed to parse JSON: {str(json_error)}")
                print(f"ERROR: Content: {summary_content[:500]}...")
                return {"error": f"Failed to parse summary file. It's not valid JSON: {str(json_error)}"}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR retrieving summary: {type(e).__name__} - {str(e)}")
            print(f"ERROR details: {error_details}")
            
            # Provide a more user-friendly error message
            if "BlobNotFound" in str(e):
                return {"error": f"The summary for '{document_id}' could not be found. The document may exist, but no summary has been generated for it yet."}
            elif "container" in str(e).lower() and "not" in str(e).lower() and "exist" in str(e).lower():
                return {"error": f"The summary container '{self.summary_container}' does not exist. Please check your environment configuration."}
            else:
                return {"error": f"Error retrieving summary: {str(e)}"}
