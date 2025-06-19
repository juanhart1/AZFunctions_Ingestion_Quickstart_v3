from azure.storage.blob import BlobServiceClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import os
import json
import logging
import requests

class ProofreadingSkill:
    def __init__(self):
        # Get Azure Blob Storage credentials from environment variables
        self.storage_connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        self.proofreading_container = os.environ.get("PROOFREADING_CONTAINER")
        
        # Print debug information
        print(f"DEBUG: Proofreading container name: '{self.proofreading_container}'")
        if not self.storage_connection_string:
            print("WARNING: AZURE_STORAGE_CONNECTION_STRING not set")
        if not self.proofreading_container:
            print("WARNING: PROOFREADING_CONTAINER not set, using default 'proofreading'")
            self.proofreading_container = "proofreading"  # Set a default value
        
        # Initialize blob service client if credentials are available
        if self.storage_connection_string and self.proofreading_container:
            try:
                self.blob_service_client = BlobServiceClient.from_connection_string(self.storage_connection_string)
                self.container_client = self.blob_service_client.get_container_client(self.proofreading_container)
                
                # Check if container exists
                try:
                    container_properties = self.container_client.get_container_properties()
                    print(f"DEBUG: Successfully connected to container '{self.proofreading_container}'")
                except Exception as container_error:
                    print(f"WARNING: Container '{self.proofreading_container}' may not exist: {str(container_error)}")
                    
            except Exception as e:
                print(f"ERROR initializing blob service: {str(e)}")
                self.blob_service_client = None
                self.container_client = None
        else:
            self.blob_service_client = None
            self.container_client = None
            print("Warning: Azure Blob Storage credentials not found. Proofreading Skill will not function.")
    
    def get_proofread(self, document_id: str = None) -> dict:
        """
        Retrieve the proofreading results for a document from Azure Blob Storage.
        
        Args:
            document_id: The ID of the document to proofread
            
        Returns:
            A dictionary containing the proofreading results
        """
        if not self.container_client:
            return {"error": "Error: Azure Blob Storage client not initialized."}
        
        if not document_id:
            return {"error": "Error: No document ID provided."}
        
        try:
            # Construct the expected blob path
            blob_path = f"{document_id}/proofread.json"
            
            # Get the proofreading blob client
            blob_client = self.container_client.get_blob_client(blob_path)
            
            # Check if the blob exists before attempting to download
            if not blob_client.exists():
                print(f"DEBUG: Proofreading blob not found at path: {blob_path}")
                
                # Try alternative paths
                alternative_paths = [
                    document_id,  # The document_id itself is the blob name
                    f"proofread_{document_id}.json",  
                    f"{document_id.replace(' ', '_')}/proofread.json",  
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
                    print(f"DEBUG: Listing all blobs in container '{self.proofreading_container}' for debugging:")
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
                    
                    return {"error": f"No proofreading results found for document '{document_id}'. The results file does not exist in the blob container '{self.proofreading_container}'."}
            
            # Download the proofreading results
            download_stream = blob_client.download_blob()
            proofreading_content = download_stream.readall().decode("utf-8")
            
            try:
                proofreading_data = json.loads(proofreading_content)
                print(f"DEBUG: Successfully parsed JSON from blob. Keys: {list(proofreading_data.keys())}")
                
                # Handle the specific structure format provided in the example
                if "id" in proofreading_data and "results" in proofreading_data:
                    results_section = proofreading_data["results"]
                    
                    # Initialize categories for different issue types
                    grammar_issues = []
                    spelling_issues = []
                    clarity_issues = [] 
                    style_issues = []
                    
                    # Process spelling issues
                    if "spelling" in results_section:
                        for issue in results_section["spelling"]:
                            spelling_issues.append({
                                "original": issue.get("error", ""),
                                "suggestion": issue.get("suggestion", ""),
                                "context": issue.get("context", ""),
                                "explanation": "Spelling error"
                            })
                    
                    # Process grammar issues
                    if "grammar" in results_section:
                        for issue in results_section["grammar"]:
                            grammar_issues.append({
                                "original": issue.get("error", ""),
                                "suggestion": issue.get("suggestion", ""),
                                "context": issue.get("context", ""),
                                "explanation": issue.get("explanation", "Grammar error")
                            })
                    
                    # Process clarity issues
                    if "clarity" in results_section:
                        for issue in results_section["clarity"]:
                            clarity_issues.append({
                                "original": issue.get("issue", issue.get("error", "")),
                                "suggestion": issue.get("suggestion", ""),
                                "context": issue.get("context", ""),
                                "explanation": issue.get("explanation", issue.get("impact", "Clarity issue"))
                            })
                    
                    # Process style issues
                    if "style" in results_section:
                        for issue in results_section["style"]:
                            style_issues.append({
                                "original": issue.get("issue", issue.get("error", "")),
                                "suggestion": issue.get("suggestion", ""),
                                "context": issue.get("context", ""),
                                "explanation": issue.get("explanation", issue.get("category", "Style issue"))
                            })
                    
                    # Calculate total issues
                    total_issues = len(spelling_issues) + len(grammar_issues) + len(clarity_issues) + len(style_issues)
                    
                    # Return structured result
                    return {
                        "document_id": proofreading_data.get("id", document_id),
                        "grammar_issues": grammar_issues,
                        "spelling_issues": spelling_issues,
                        "clarity_issues": clarity_issues,
                        "style_issues": style_issues,
                        "other_issues": [],
                        "total_issues": total_issues,
                        "source_file": proofreading_data.get("sourcefile", "")
                    }
                
                # Handle the suggestions format (previous implementation)
                elif "suggestions" in proofreading_data:
                    # Return categorized suggestions if present
                    grammar_issues = []
                    spelling_issues = []
                    clarity_issues = [] 
                    style_issues = []
                    other_issues = []
                    
                    # Format and categorize all suggestions
                    for suggestion in proofreading_data["suggestions"]:
                        suggestion_type = suggestion.get("type", "").lower()
                        
                        # Create formatted item
                        formatted_item = {
                            "original": suggestion.get("original", suggestion.get("error", "")),
                            "suggestion": suggestion.get("suggestion", ""),
                            "context": suggestion.get("context", ""),
                            "explanation": suggestion.get("explanation", "")
                        }
                        
                        # Categorize by type
                        if "grammar" in suggestion_type:
                            grammar_issues.append(formatted_item)
                        elif "spell" in suggestion_type:
                            spelling_issues.append(formatted_item)
                        elif "clarity" in suggestion_type or "readability" in suggestion_type:
                            clarity_issues.append(formatted_item)
                        elif "style" in suggestion_type or "consistency" in suggestion_type:
                            style_issues.append(formatted_item)
                        else:
                            other_issues.append(formatted_item)
                    
                    # Return structured result
                    return {
                        "document_id": document_id,
                        "grammar_issues": grammar_issues,
                        "spelling_issues": spelling_issues,
                        "clarity_issues": clarity_issues,
                        "style_issues": style_issues,
                        "other_issues": other_issues,
                        "total_issues": len(proofreading_data["suggestions"]),
                        "source_file": proofreading_data.get("sourcefile", "")
                    }
                else:
                    # If we can't find specific fields, return the whole content
                    return {"error": f"Proofreading structure unclear. Raw content: {proofreading_content[:500]}..."}
                    
            except json.JSONDecodeError as json_error:
                print(f"ERROR: Failed to parse JSON: {str(json_error)}")
                print(f"ERROR: Content: {proofreading_content[:500]}...")
                return {"error": f"Failed to parse proofreading file. It's not valid JSON: {str(json_error)}"}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR retrieving proofreading results: {type(e).__name__} - {str(e)}")
            print(f"ERROR details: {error_details}")
            
            # Provide a more user-friendly error message
            if "BlobNotFound" in str(e):
                return {"error": f"The proofreading results for '{document_id}' could not be found. The document may exist, but no proofreading has been generated for it yet."}
            elif "container" in str(e).lower() and "not" in str(e).lower() and "exist" in str(e).lower():
                return {"error": f"The proofreading container '{self.proofreading_container}' does not exist. Please check your environment configuration."}
            else:
                return {"error": f"Error retrieving proofreading results: {str(e)}"}

    def synthesize_proofreading_results(self, document_id: str = None) -> dict:
        """
        If proofreading results don't exist, we can synthesize them by:
        1. Getting the document content from Azure Search
        2. Sending that content to Azure OpenAI for proofreading
        3. Processing and returning the results in a format that matches the expected JSON structure
        """
        try:
            # Get the document content from Azure Search
            # Set up Azure Search client
            search_service = os.environ.get("AZURE_SEARCH_SERVICE")
            search_index = os.environ.get("AZURE_SEARCH_INDEX")
            search_key = os.environ.get("AZURE_SEARCH_KEY")
            
            if not search_service or not search_index or not search_key:
                return {"error": "Azure Search credentials not found in environment variables."}
            
            try:
                # Create search client
                search_endpoint = f"https://{search_service}.search.windows.net/"
                search_client = SearchClient(
                    endpoint=search_endpoint,
                    index_name=search_index,
                    credential=AzureKeyCredential(search_key)
                )
                
                # Search for the document using the document_id
                # We use search filter to be more precise
                clean_id = document_id.replace("'", "''")  # Escape single quotes for OData
                results = list(search_client.search(
                    search_text="", 
                    filter=f"id eq '{clean_id}' or filename eq '{clean_id}'",
                    include_total_count=True,
                    select=["id", "content", "filepath", "filename", "title"]
                ))
                
                # Check if document was found
                if len(results) == 0:
                    return {"error": f"Document '{document_id}' not found in Azure Search index."}
                
                # Get the document content
                document = results[0]
                content = document.get("content", "")
                
                if not content:
                    return {"error": "Document found but contains no content to proofread."}
                
                print(f"DEBUG: Retrieved document content, length: {len(content)}")
                
            except Exception as search_error:
                print(f"ERROR searching for document: {str(search_error)}")
                return {"error": f"Error retrieving document from Azure Search: {str(search_error)}"}
            
            # Call Azure OpenAI for proofreading
            try:
                from azure.core.credentials import AzureKeyCredential
                from azure.search.documents import SearchClient
                import requests
                import json
                
                # Load environment variables
                base_endpoint = os.environ.get("AOAI_ENDPOINT", "").rstrip('/')
                key = os.environ.get("AOAI_KEY")
                model = os.environ.get("AOAI_GPT_MODEL", "gpt-4o")
                deployment_name = os.environ.get("AOAI_DEPLOYMENT", model)
                
                if not base_endpoint or not key:
                    return {"error": "Azure OpenAI credentials not found in environment variables."}
                
                # Prepare for API call
                api_version = "2024-02-15-preview"
                endpoint = f"{base_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"
                
                headers = {
                    "Content-Type": "application/json",
                    "api-key": key
                }
                
                # Prepare the prompt
                system_prompt = """You are a professional proofreader and editor. Analyze the document text for grammar, spelling, clarity, and style issues.
                
                Respond with a valid JSON object using this exact schema:
                {
                    "id": "document-identifier",
                    "sourcefile": "source-filename",
                    "proofread_type": "document",
                    "results": {
                        "spelling": [
                            {
                                "error": "the misspelled text",
                                "suggestion": "the corrected spelling",
                                "context": "surrounding text that includes the error"
                            }
                        ],
                        "grammar": [
                            {
                                "error": "the grammatically incorrect text",
                                "suggestion": "the grammatically correct text",
                                "context": "surrounding text that includes the error",
                                "explanation": "brief explanation of the grammatical issue"
                            }
                        ],
                        "clarity": [
                            {
                                "issue": "the unclear text or concept",
                                "suggestion": "the clearer alternative",
                                "context": "surrounding text that includes the issue",
                                "impact": "how this impacts readability or comprehension"
                            }
                        ],
                        "style": [
                            {
                                "issue": "the problematic style element",
                                "suggestion": "the recommended style alternative",
                                "context": "example of the style issue",
                                "category": "tone consistency|terminology consistency|formatting consistency|etc."
                            }
                        ]
                    }
                }
                
                Do not include more than 25 total issues across all categories, focusing on the most important problems.
                If there are no issues in a category, include an empty array for that category.
                Only include actual errors, not style preferences unless they impact readability.
                """
                
                # Truncate content if too long
                max_content_length = 6000  # Adjust based on token limits
                if len(content) > max_content_length:
                    content = content[:max_content_length] + "..."
                    print(f"DEBUG: Content truncated to {max_content_length} characters")
                
                data = {
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": content}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 4000,
                    "response_format": {"type": "json_object"}
                }
                
                # Make the API call
                print("DEBUG: Calling Azure OpenAI for proofreading")
                response = requests.post(endpoint, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                
                # Extract and parse the response content
                ai_response_content = result['choices'][0]['message']['content']
                proofreading_data = json.loads(ai_response_content)
                
                # Initialize categories for different issue types
                grammar_issues = []
                spelling_issues = []
                clarity_issues = [] 
                style_issues = []
                other_issues = []
                
                # Check if we got the expected structure
                if "results" in proofreading_data:
                    results = proofreading_data["results"]
                    print(f"DEBUG: Received proofreading results with {len(results.get('spelling', []))} spelling, {len(results.get('grammar', []))} grammar, {len(results.get('clarity', []))} clarity, and {len(results.get('style', []))} style issues")
                    
                    # Process spelling issues
                    for issue in results.get("spelling", []):
                        spelling_issues.append({
                            "original": issue.get("error", ""),
                            "suggestion": issue.get("suggestion", ""),
                            "context": issue.get("context", ""),
                            "explanation": "Spelling error"
                        })
                    
                    # Process grammar issues
                    for issue in results.get("grammar", []):
                        grammar_issues.append({
                            "original": issue.get("error", ""),
                            "suggestion": issue.get("suggestion", ""),
                            "context": issue.get("context", ""),
                            "explanation": issue.get("explanation", "Grammar error")
                        })
                    
                    # Process clarity issues
                    for issue in results.get("clarity", []):
                        clarity_issues.append({
                            "original": issue.get("issue", ""),
                            "suggestion": issue.get("suggestion", ""),
                            "context": issue.get("context", ""),
                            "explanation": issue.get("impact", "Clarity issue")
                        })
                    
                    # Process style issues
                    for issue in results.get("style", []):
                        style_issues.append({
                            "original": issue.get("issue", ""),
                            "suggestion": issue.get("suggestion", ""),
                            "context": issue.get("context", ""),
                            "explanation": issue.get("category", "Style issue")
                        })
                
                # Fallback to old format if needed
                elif "suggestions" in proofreading_data:
                    print(f"DEBUG: Received legacy format with {len(proofreading_data.get('suggestions', []))} suggestions")
                    
                    # Process all suggestions
                    for suggestion in proofreading_data.get("suggestions", []):
                        suggestion_type = suggestion.get("type", "").lower()
                        
                        # Create formatted item
                        formatted_item = {
                            "original": suggestion.get("original", ""),
                            "suggestion": suggestion.get("suggestion", ""),
                            "context": suggestion.get("context", ""),
                            "explanation": suggestion.get("explanation", "")
                        }
                        
                        # Categorize by type
                        if "grammar" in suggestion_type:
                            grammar_issues.append(formatted_item)
                        elif "spell" in suggestion_type:
                            spelling_issues.append(formatted_item)
                        elif "clarity" in suggestion_type or "readability" in suggestion_type:
                            clarity_issues.append(formatted_item)
                        elif "style" in suggestion_type or "consistency" in suggestion_type:
                            style_issues.append(formatted_item)
                        else:
                            other_issues.append(formatted_item)
                
                # Return structured result
                total_issues = len(spelling_issues) + len(grammar_issues) + len(clarity_issues) + len(style_issues) + len(other_issues)
                return {
                    "document_id": document_id,
                    "grammar_issues": grammar_issues,
                    "spelling_issues": spelling_issues,
                    "clarity_issues": clarity_issues,
                    "style_issues": style_issues,
                    "other_issues": other_issues,
                    "total_issues": total_issues,
                    "source_file": document.get("filename", "") or document.get("filepath", "") or document.get("title", "") or document_id
                }
                
            except Exception as openai_error:
                print(f"ERROR generating proofreading suggestions: {str(openai_error)}")
                return {"error": f"Error generating proofreading suggestions: {str(openai_error)}"}
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            print(f"ERROR synthesizing proofreading results: {type(e).__name__} - {str(e)}")
            print(f"ERROR details: {error_details}")
            
            # Fallback to sample data if errors occur
            return {
                "document_id": document_id,
                "grammar_issues": [
                    {
                        "original": "The data show that",
                        "suggestion": "The data shows that",
                        "context": "The data show that our approach is effective.",
                        "explanation": "The word 'data' is plural but commonly treated as singular in modern usage."
                    }
                ],
                "spelling_issues": [
                    {
                        "original": "definately",
                        "suggestion": "definitely",
                        "context": "This will definately improve our results.",
                        "explanation": "Common misspelling"
                    }
                ],
                "clarity_issues": [
                    {
                        "original": "It is what it is",
                        "suggestion": "The situation cannot be changed",
                        "context": "Regarding the budget constraints, it is what it is.",
                        "explanation": "This phrase is vague and can be replaced with more specific language."
                    }
                ],
                "style_issues": [],
                "other_issues": [],
                "total_issues": 3,
                "source_file": document_id,
                "note": "Sample data provided due to error in synthesis"
            }
