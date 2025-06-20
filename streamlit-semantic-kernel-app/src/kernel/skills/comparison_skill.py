from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os
import json
import requests
from typing import List, Dict, Any
from azure.storage.blob import BlobServiceClient

class ComparisonSkill:
    def __init__(self):
        # Get Azure OpenAI credentials
        self.aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AOAI_ENDPOINT")
        self.aoai_key = os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AOAI_KEY")
        self.aoai_deployment = os.environ.get("AZURE_OPENAI_COMPLETION_DEPLOYMENT") or os.environ.get("AOAI_GPT_MODEL")
        
        # Get Azure Storage credentials
        self.storage_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        # Use the correct container name
        self.summary_container = os.environ.get("SUMMARY_CONTAINER", "rtx-transcripts-summaries")
        
        # Initialize Blob Storage client
        if self.storage_connection_string:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
        else:
            self.blob_service_client = None
            print("Warning: Azure Storage connection string not found. ComparisonSkill will not function properly.")
    def compare_documents(self, document_ids: List[str]) -> str:
        """
        Compare multiple documents using their processed summaries stored in Azure Blob Storage.
        
        Args:
            document_ids: List of document IDs to compare
            
        Returns:
            A detailed comparison of the documents
        """
        if not self.aoai_endpoint or not self.aoai_key or not self.aoai_deployment:
            return "Error: Azure OpenAI credentials not configured."
        
        if not self.blob_service_client:
            return "Error: Azure Storage client not initialized."
        
        if len(document_ids) < 2:
            return "Error: At least two documents are required for comparison."
        
        try:
            print(f"Starting document comparison for {len(document_ids)} documents")
            print(f"Using container: {self.summary_container}")
            print(f"Document IDs: {document_ids}")
            
            # Step 1: Retrieve processed summaries for all documents from Blob Storage
            document_summaries = {}
            for doc_id in document_ids:
                print(f"Retrieving summary for document: {doc_id}")
                # Extract base document ID without extension for better matching
                base_doc_id = doc_id.split('.')[0] if '.' in doc_id else doc_id
                print(f"Base document ID (without extension): {base_doc_id}")
                
                summary = self._get_document_summary(doc_id)
                if summary:
                    # Store with the original doc_id for reference in the UI
                    document_summaries[doc_id] = summary
                    print(f"Successfully retrieved summary for {doc_id} ({len(summary)} chars)")
                else:
                    error_msg = (
                        f"Error: Summary for document '{doc_id}' not found. "
                        f"Make sure you've processed the document first and it exists in the '{self.summary_container}' container. "
                        f"Expected filename format: '{base_doc_id}_document_summary.json' "
                        f"(not '{doc_id}_document_summary.json' which includes the file extension)"
                    )
                    print(error_msg)
                    return error_msg
            
            # Step 2: Prepare the prompt for the LLM
            print("Creating comparison prompt...")
            prompt = self._create_comparison_prompt(document_summaries)
            
            # Step 3: Send to Azure OpenAI for comparison
            print("Generating comparison...")
            comparison = self._generate_comparison(prompt)
            
            print("Comparison generated successfully")
            return comparison
                
        except Exception as e:
            error_msg = f"Error comparing documents: {str(e)}"
            print(error_msg)
            return error_msg
    
    def _get_document_summary(self, document_id: str) -> str:
        """
        Retrieve the processed summary for a document from Azure Blob Storage.
        
        Args:
            document_id: The ID of the document
            
        Returns:
            The summary text or None if not found
        """
        try:
            # Connect to the summaries container
            container_client = self.blob_service_client.get_container_client(self.summary_container)
            
            # Remove any file extension from the document_id if present
            # This handles cases where document_id might include ".pdf" or other extensions
            base_document_id = document_id.split('.')[0] if '.' in document_id else document_id
            
            # Try different filename patterns based on the document ID with the _document_summary.json pattern
            potential_blob_names = [
                f"{base_document_id}_document_summary.json",  # Correct format: RTX Q1'25 Final Transcript_document_summary.json
                f"{document_id}_document_summary.json",       # Try with full ID including extension
                f"{base_document_id}/document_summary.json",  # Alternative with directory
                f"{document_id}.json"                         # Simple format
            ]
            
            print(f"Looking for summary for document ID: {document_id}")
            print(f"Using base document ID (without extension): {base_document_id}")
            
            # Try each potential blob name
            for blob_name in potential_blob_names:
                try:
                    print(f"Trying blob name: {blob_name}")
                    blob_client = container_client.get_blob_client(blob_name)
                    
                    # Check if blob exists before downloading
                    if blob_client.exists():
                        print(f"Blob exists: {blob_name}")
                        download_stream = blob_client.download_blob()
                        content = download_stream.readall().decode("utf-8")
                        
                        # Try to parse as JSON
                        try:
                            summary_data = json.loads(content)
                            print(f"Found blob: {blob_name}, parsing JSON...")
                            
                            # Look for the summary field in the JSON
                            if "summary" in summary_data:
                                print(f"Found 'summary' field in {blob_name}")
                                return summary_data["summary"]
                            elif "text" in summary_data:
                                print(f"Found 'text' field in {blob_name}")
                                return summary_data["text"]
                            elif "content" in summary_data:
                                print(f"Found 'content' field in {blob_name}")
                                return summary_data["content"]
                            # Check for nested structures
                            elif "document" in summary_data and isinstance(summary_data["document"], dict):
                                if "summary" in summary_data["document"]:
                                    print(f"Found 'document.summary' field in {blob_name}")
                                    return summary_data["document"]["summary"]
                                elif "content" in summary_data["document"]:
                                    print(f"Found 'document.content' field in {blob_name}")
                                    return summary_data["document"]["content"]
                            elif "metadata" in summary_data and isinstance(summary_data["metadata"], dict):
                                if "summary" in summary_data["metadata"]:
                                    print(f"Found 'metadata.summary' field in {blob_name}")
                                    return summary_data["metadata"]["summary"]
                            else:
                                # If no specific field is found, use the first string value over 100 chars
                                for key, value in summary_data.items():
                                    if isinstance(value, str) and len(value) > 100:
                                        print(f"Using field '{key}' as summary from {blob_name}")
                                        return value
                                
                                # If all else fails, print the structure and return the entire JSON as text
                                print(f"Could not find summary field in {blob_name}. JSON structure: {list(summary_data.keys())}")
                                return json.dumps(summary_data, indent=2)
                                
                        except json.JSONDecodeError as e:
                            # If it's not valid JSON, but it's a reasonably long string, use it as the summary
                            if len(content) > 100:
                                print(f"Blob {blob_name} is not JSON but contains text. Using as summary.")
                                return content
                            else:
                                print(f"Blob {blob_name} is not valid JSON and too short: {e}")
                    else:
                        print(f"Blob {blob_name} does not exist")
                        
                except Exception as e:
                    print(f"Error accessing blob {blob_name}: {str(e)}")
                    # Continue to the next potential blob name
                    continue
            
            # If no direct match is found, try a more flexible search
            print(f"No exact match found. Searching for all blobs to find matches for {base_document_id}")
            
            # List all blobs in the container
            all_blobs = list(container_client.list_blobs())
            print(f"Found {len(all_blobs)} total blobs in container")
            
            # Look for blobs that might match our document, checking various patterns:
            # 1. Filename_document_summary.json pattern (without .pdf in the middle)
            # 2. Any blob containing the document name and ending with _document_summary.json
            matching_blobs = []
            
            for blob in all_blobs:
                blob_name = blob.name
                print(f"Checking blob: {blob_name}")
                
                # Check if the blob matches the expected pattern without the file extension
                if base_document_id in blob_name and "_document_summary.json" in blob_name:
                    matching_blobs.append(blob)
                    print(f"Found potential match: {blob_name}")
            
            if matching_blobs:
                print(f"Found {len(matching_blobs)} potential matching blobs")
                # Sort blobs by last modified to get the most recent one
                matching_blobs.sort(key=lambda b: b.last_modified, reverse=True)
                
                target_blob = matching_blobs[0]
                print(f"Using blob: {target_blob.name}")
                
                blob_client = container_client.get_blob_client(target_blob.name)
                download_stream = blob_client.download_blob()
                content = download_stream.readall().decode("utf-8")
                
                try:
                    summary_data = json.loads(content)
                    
                    # Same logic as above to extract the summary
                    if "summary" in summary_data:
                        return summary_data["summary"]
                    elif "text" in summary_data:
                        return summary_data["text"]
                    elif "content" in summary_data:
                        return summary_data["content"]
                    # Check for nested structures
                    elif "document" in summary_data and isinstance(summary_data["document"], dict):
                        if "summary" in summary_data["document"]:
                            return summary_data["document"]["summary"]
                        elif "content" in summary_data["document"]:
                            return summary_data["document"]["content"]
                    elif "metadata" in summary_data and isinstance(summary_data["metadata"], dict):
                        if "summary" in summary_data["metadata"]:
                            return summary_data["metadata"]["summary"]
                    else:
                        for key, value in summary_data.items():
                            if isinstance(value, str) and len(value) > 100:
                                return value
                        return json.dumps(summary_data, indent=2)
                except json.JSONDecodeError:
                    # If it's not valid JSON but contains text, use it as is
                    if len(content) > 100:
                        return content
            else:
                print(f"No blobs found matching the pattern for document ID {document_id}")
                
                # If no matches found, print all available blobs to help with debugging
                print("Available blobs in container:")
                for i, blob in enumerate(all_blobs[:10]):  # Show first 10 for brevity
                    print(f"  {i+1}. {blob.name}")
                if len(all_blobs) > 10:
                    print(f"  ... and {len(all_blobs) - 10} more")
            
            # If we get here, no summary was found
            print(f"No summary found for document {document_id}")
            return None
            
        except Exception as e:
            print(f"Error retrieving summary for document {document_id}: {str(e)}")
            return None
    
    def _create_comparison_prompt(self, document_summaries: Dict[str, str]) -> str:
        """
        Create a prompt for the LLM to compare documents.
        """
        prompt = "Please compare the following documents based on their summaries:\n\n"
        
        for doc_id, summary in document_summaries.items():
            # Clean up the document ID for display - remove path information if present
            clean_doc_id = doc_id.split("/")[-1] if "/" in doc_id else doc_id
            prompt += f"Document: {clean_doc_id}\n"
            prompt += f"Summary: {summary}\n\n"
        
        prompt += """
        In your comparison, please include:
        1. Key similarities between the documents
        2. Important differences between the documents
        3. Unique insights or information found in each document
        4. Overall comparative analysis including recommendations
        
        Structure your response in a clear, organized manner with headings for each section.
        Use bullet points where appropriate to highlight key points.
        Make your comparison specific and detailed, referencing concrete examples from the document summaries.
        """
        
        return prompt
    
    def _generate_comparison(self, prompt: str) -> str:
        """
        Generate a comparison of documents using Azure OpenAI.
        """
        try:
            headers = {
                "Content-Type": "application/json",
                "api-key": self.aoai_key
            }
            
            payload = {
                "messages": [
                    {"role": "system", "content": "You are an expert document analyst who compares documents and provides detailed insights about their similarities, differences, and unique aspects. Format your response with clear headings and organized structure to make it easy to read."},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
                "top_p": 0.95,
                "frequency_penalty": 0,
                "presence_penalty": 0
            }
            
            # Make the API call to Azure OpenAI
            api_url = f"{self.aoai_endpoint}/openai/deployments/{self.aoai_deployment}/chat/completions?api-version=2023-05-15"
            print(f"Sending request to Azure OpenAI at {api_url}")
            response = requests.post(api_url, headers=headers, json=payload)
            
            if response.status_code == 200:
                result = response.json()
                comparison = result["choices"][0]["message"]["content"]
                print("Received comparison from Azure OpenAI")
                return comparison
            else:
                error_message = f"Azure OpenAI API call failed with status code {response.status_code}"
                try:
                    error_details = response.json()
                    error_message += f": {error_details.get('error', {}).get('message', 'Unknown error')}"
                except:
                    error_message += f": {response.text}"
                
                print(error_message)
                return f"Error generating comparison: {error_message}"
                
        except Exception as e:
            error_message = f"Error calling Azure OpenAI API: {str(e)}"
            print(error_message)
            return error_message
