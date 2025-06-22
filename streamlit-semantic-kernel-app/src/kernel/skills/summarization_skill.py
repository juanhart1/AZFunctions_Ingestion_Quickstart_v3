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
            
            # Pre-process the raw summary content to handle specific raw JSON patterns
            # This handles the pattern from the screenshot: ```json { "executive_summary": "..." }
            import re
            if "```json" in summary_content:
                pattern = r'```json\s*(\{.*?\})\s*```'
                match = re.search(pattern, summary_content, re.DOTALL)
                if match:
                    try:
                        json_obj = json.loads(match.group(1))
                        if "executive_summary" in json_obj and "detailed_summary" in json_obj:
                            # We have a direct match to the format we need
                            return {
                                "executive": json_obj.get("executive_summary", ""),
                                "detailed": json_obj.get("detailed_summary", ""),
                                "topics": json_obj.get("key_topics", []),
                                "conclusions": json_obj.get("takeaways", []),
                                "source_file": document_id,
                                "generated_date": ""
                            }
                    except json.JSONDecodeError:
                        # Just continue with regular processing if this fails
                        pass
            
            # Also check the specific format with ```json { at the beginning
            if summary_content.strip().startswith("```json {"):
                try:
                    # Extract the JSON part
                    json_part = summary_content.strip().replace("```json", "").strip()
                    # Find the closing backticks
                    end_index = json_part.rfind("```")
                    if end_index > 0:
                        json_part = json_part[:end_index].strip()
                    
                    # Try to parse it
                    json_obj = json.loads(json_part)
                    if isinstance(json_obj, dict) and "executive_summary" in json_obj:
                        return {
                            "executive": json_obj.get("executive_summary", ""),
                            "detailed": json_obj.get("detailed_summary", ""),
                            "topics": json_obj.get("key_topics", []),
                            "conclusions": json_obj.get("takeaways", []),
                            "source_file": document_id,
                            "generated_date": ""
                        }
                except:
                    # Just continue with regular processing if this fails
                    pass
            
            try:
                # Check if the content contains code blocks with JSON inside
                if "```json" in summary_content:
                    import re
                    # Extract JSON from markdown code blocks
                    json_match = re.search(r'```json\s*(.*?)\s*```', summary_content, re.DOTALL)
                    if json_match:
                        cleaned_json = json_match.group(1)
                        try:
                            summary_data = json.loads(cleaned_json)
                            print(f"DEBUG: Successfully parsed JSON from code block. Keys: {list(summary_data.keys())}")
                        except:
                            # Fall back to original parsing
                            summary_data = json.loads(summary_content)
                    else:
                        # Fall back to original parsing
                        summary_data = json.loads(summary_content)
                else:
                    # Standard JSON parsing
                    summary_data = json.loads(summary_content)
                
                print(f"DEBUG: Successfully parsed JSON from blob. Keys: {list(summary_data.keys())}")
                
                # First try to find executive_summary and detailed_summary directly in the JSON
                executive_summary = None
                detailed_summary = None
                key_topics = []
                takeaways = []
                
                # Try to extract data from different possible structures
                
                # Case 1: Check for nested structure in summary field
                if "summary" in summary_data and isinstance(summary_data["summary"], dict):
                    summary_section = summary_data["summary"]
                    
                    # Check for camelCase format
                    if "executive_summary" in summary_section:
                        executive_summary = summary_section["executive_summary"]
                    # Check for Title Case format
                    elif "Executive Summary" in summary_section:
                        executive_summary = summary_section["Executive Summary"]
                        
                    # Check for camelCase detailed summary
                    if "detailed_summary" in summary_section:
                        detailed_summary = summary_section["detailed_summary"]
                    # Check for Title Case detailed summary
                    elif "Detailed Summary" in summary_section:
                        detailed_summary = summary_section["Detailed Summary"]
                        
                    # Check for topics/themes
                    if "key_topics" in summary_section:
                        key_topics = summary_section["key_topics"]
                    elif "Key Topics/Themes" in summary_section:
                        key_topics = summary_section["Key Topics/Themes"]
                        
                    # Check for takeaways/conclusions
                    if "takeaways" in summary_section:
                        takeaways = summary_section["takeaways"]
                    elif "Main Conclusions/Takeaways" in summary_section:
                        takeaways = summary_section["Main Conclusions/Takeaways"]
                
                # Case 2: Check for fields at root level
                if executive_summary is None:
                    if "executive_summary" in summary_data:
                        executive_summary = summary_data["executive_summary"]
                    elif "Executive Summary" in summary_data:
                        executive_summary = summary_data["Executive Summary"]
                
                if detailed_summary is None:
                    if "detailed_summary" in summary_data:
                        detailed_summary = summary_data["detailed_summary"]
                    elif "Detailed Summary" in summary_data:
                        detailed_summary = summary_data["Detailed Summary"]
                
                # Enhanced topics extraction with more patterns
                if not key_topics:
                    # Try multiple potential field names for topics
                    for field_name in ["key_topics", "Key Topics/Themes", "topics", "Topics", "key_themes", 
                                      "Key Themes", "themes", "Themes", "main_topics", "Main Topics",
                                      "keyTopics", "KeyTopics", "KeyThemes", "mainTopics", "MainTopics"]:
                        if field_name in summary_data:
                            key_topics = summary_data[field_name]
                            break
                    
                    # If still not found, check nested objects
                    if not key_topics:
                        for key, value in summary_data.items():
                            if isinstance(value, dict):
                                for field_name in ["key_topics", "Key Topics/Themes", "topics", "Topics", 
                                                 "key_themes", "Key Themes", "themes", "Themes", 
                                                 "main_topics", "Main Topics", "keyTopics", "KeyTopics", 
                                                 "KeyThemes", "mainTopics", "MainTopics"]:
                                    if field_name in value:
                                        key_topics = value[field_name]
                                        break
                                if key_topics:
                                    break
                    
                    # If still not found, check in summary field
                    if not key_topics and "summary" in summary_data and isinstance(summary_data["summary"], str):
                        # Try to extract topics from the summary string using regex
                        try:
                            import re
                            # Look for patterns like "Topics:" or "Key Topics:" followed by content
                            topics_match = re.search(r'(?:Key\s*Topics|Topics|Themes):\s*(.*?)(?:\n\n|\n[A-Z]|$)', 
                                                   summary_data["summary"], re.IGNORECASE | re.DOTALL)
                            if topics_match:
                                topics_text = topics_match.group(1).strip()
                                # Convert bulleted list to array
                                if '-' in topics_text or '•' in topics_text or '*' in topics_text:
                                    # Split by bullet markers
                                    topics_items = re.split(r'\s*[-•*]\s*', topics_text)
                                    # Remove empty items and clean up
                                    key_topics = [item.strip() for item in topics_items if item.strip()]
                                else:
                                    # Just use as single topic
                                    key_topics = [topics_text]
                        except:
                            pass
                    
                    # If we found topics in a string format, convert to list
                    if isinstance(key_topics, str):
                        # Check if it's a JSON string
                        if key_topics.strip().startswith('[') and key_topics.strip().endswith(']'):
                            try:
                                key_topics = json.loads(key_topics)
                            except:
                                pass  # Continue with other parsing methods
                        
                        # Check if it has bullet points or newlines
                        if isinstance(key_topics, str) and ('-' in key_topics or '•' in key_topics or '*' in key_topics or '\n' in key_topics):
                            # Split by bullet markers or newlines
                            import re
                            topics_items = re.split(r'\s*[-•*]\s*|\n', key_topics)
                            # Remove empty items and clean up
                            key_topics = [item.strip() for item in topics_items if item.strip()]
                        elif isinstance(key_topics, str) and (',' in key_topics or ';' in key_topics):
                            # Split by commas or semicolons
                            topics_items = re.split(r'\s*[,;]\s*', key_topics)
                            key_topics = [item.strip() for item in topics_items if item.strip()]
                        elif isinstance(key_topics, str):
                            # Just use as a single topic
                            key_topics = [key_topics]
                
                # Enhanced conclusions/takeaways extraction with more patterns
                if not takeaways:
                    # Try multiple potential field names for conclusions
                    for field_name in ["takeaways", "Main Conclusions/Takeaways", "conclusions", "Conclusions",
                                      "main_conclusions", "Main Conclusions", "key_takeaways", "Key Takeaways",
                                      "mainConclusions", "main_takeaways", "MainConclusions", "MainTakeaways"]:
                        if field_name in summary_data:
                            takeaways = summary_data[field_name]
                            break
                    
                    # If still not found, check nested objects
                    if not takeaways:
                        for key, value in summary_data.items():
                            if isinstance(value, dict):
                                for field_name in ["takeaways", "Main Conclusions/Takeaways", "conclusions", 
                                                  "Conclusions", "main_conclusions", "Main Conclusions", 
                                                  "key_takeaways", "Key Takeaways", "mainConclusions", 
                                                  "main_takeaways", "MainConclusions", "MainTakeaways"]:
                                    if field_name in value:
                                        takeaways = value[field_name]
                                        break
                                if takeaways:
                                    break
                    
                    # If still not found, check in summary field
                    if not takeaways and "summary" in summary_data and isinstance(summary_data["summary"], str):
                        # Try to extract conclusions from the summary string using regex
                        try:
                            import re
                            # Look for patterns like "Conclusions:" or "Takeaways:" followed by content
                            concl_match = re.search(r'(?:Conclusions|Takeaways|Key\s*Findings):\s*(.*?)(?:\n\n|\n[A-Z]|$)', 
                                                   summary_data["summary"], re.IGNORECASE | re.DOTALL)
                            if concl_match:
                                concl_text = concl_match.group(1).strip()
                                # Convert bulleted list to array
                                if '-' in concl_text or '•' in concl_text or '*' in concl_text:
                                    # Split by bullet markers
                                    concl_items = re.split(r'\s*[-•*]\s*', concl_text)
                                    # Remove empty items and clean up
                                    takeaways = [item.strip() for item in concl_items if item.strip()]
                                else:
                                    # Just use as single conclusion
                                    takeaways = [concl_text]
                        except:
                            pass
                    
                    # Convert takeaways from string to list if needed
                    if isinstance(takeaways, str):
                        # Check if it's a JSON string
                        if takeaways.strip().startswith('[') and takeaways.strip().endswith(']'):
                            try:
                                takeaways = json.loads(takeaways)
                            except:
                                pass  # Continue with other parsing methods
                        
                        # Check if it has bullet points or newlines
                        if isinstance(takeaways, str) and ('-' in takeaways or '•' in takeaways or '*' in takeaways or '\n' in takeaways):
                            # Split by bullet markers or newlines
                            import re
                            concl_items = re.split(r'\s*[-•*]\s*|\n', takeaways)
                            # Remove empty items and clean up
                            takeaways = [item.strip() for item in concl_items if item.strip()]
                        elif isinstance(takeaways, str) and (',' in takeaways or ';' in takeaways):
                            # Split by commas or semicolons
                            concl_items = re.split(r'\s*[,;]\s*', takeaways)
                            takeaways = [item.strip() for item in concl_items if item.strip()]
                        elif isinstance(takeaways, str):
                            # Just use as a single conclusion
                            takeaways = [takeaways]
                
                # Process the executive_summary if it's a string that looks like JSON
                if isinstance(executive_summary, str):
                    # Check if it starts with triple backticks or looks like JSON
                    if executive_summary.strip().startswith("```") or executive_summary.strip().startswith("{"):
                        try:
                            # Try to extract from code blocks first
                            import re
                            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', executive_summary, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(1)
                                try:
                                    parsed = json.loads(json_str)
                                    # Check for multiple possible field names
                                    if isinstance(parsed, dict):
                                        for field_name in ["executive_summary", "Executive Summary", "executiveSummary", "summary", "Summary"]:
                                            if field_name in parsed:
                                                executive_summary = parsed[field_name]
                                                break
                                except:
                                    print(f"DEBUG: Failed to parse executive summary JSON from code block: {json_str[:100]}...")
                                    pass
                            
                            # If that didn't work, try parsing the whole thing as JSON
                            elif executive_summary.strip().startswith("{"):
                                try:
                                    parsed = json.loads(executive_summary)
                                    # Check for multiple possible field names
                                    if isinstance(parsed, dict):
                                        for field_name in ["executive_summary", "Executive Summary", "executiveSummary", "summary", "Summary"]:
                                            if field_name in parsed:
                                                executive_summary = parsed[field_name]
                                                break
                                except:
                                    print(f"DEBUG: Failed to parse executive summary as JSON: {executive_summary[:100]}...")
                                    pass
                        except Exception as e:
                            # Just keep the original if parsing fails
                            print(f"DEBUG: Error processing executive summary: {str(e)}")
                            pass
                    
                    # Remove any triple backticks and json markers
                    executive_summary = re.sub(r'^```json\s*|\s*```$', '', executive_summary)
                    
                    # Remove any triple quotes that might be in the content
                    executive_summary = executive_summary.replace('"""', '').replace("'''", "")
                
                # Apply the same processing to detailed_summary
                if isinstance(detailed_summary, str):
                    # Check if it starts with triple backticks or looks like JSON
                    if detailed_summary.strip().startswith("```") or detailed_summary.strip().startswith("{"):
                        try:
                            # Try to extract from code blocks first
                            import re
                            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', detailed_summary, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(1)
                                try:
                                    parsed = json.loads(json_str)
                                    # Check for multiple possible field names
                                    if isinstance(parsed, dict):
                                        for field_name in ["detailed_summary", "Detailed Summary", "detailedSummary", "summary", "Summary"]:
                                            if field_name in parsed:
                                                detailed_summary = parsed[field_name]
                                                break
                                except:
                                    print(f"DEBUG: Failed to parse detailed summary JSON from code block: {json_str[:100]}...")
                                    pass
                            
                            # If that didn't work, try parsing the whole thing as JSON
                            elif detailed_summary.strip().startswith("{"):
                                try:
                                    parsed = json.loads(detailed_summary)
                                    # Check for multiple possible field names
                                    if isinstance(parsed, dict):
                                        for field_name in ["detailed_summary", "Detailed Summary", "detailedSummary", "summary", "Summary"]:
                                            if field_name in parsed:
                                                detailed_summary = parsed[field_name]
                                                break
                                except:
                                    print(f"DEBUG: Failed to parse detailed summary as JSON: {detailed_summary[:100]}...")
                                    pass
                        except Exception as e:
                            # Just keep the original if parsing fails
                            print(f"DEBUG: Error processing detailed summary: {str(e)}")
                            pass
                            import re
                            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', detailed_summary, re.DOTALL)
                            if json_match:
                                json_str = json_match.group(1)
                                try:
                                    parsed = json.loads(json_str)
                                    if isinstance(parsed, dict) and "detailed_summary" in parsed:
                                        detailed_summary = parsed["detailed_summary"]
                                except:
                                    pass
                            
                            # If that didn't work, try parsing the whole thing as JSON
                            if detailed_summary.strip().startswith("{"):
                                try:
                                    parsed = json.loads(detailed_summary)
                                    if isinstance(parsed, dict) and "detailed_summary" in parsed:
                                        detailed_summary = parsed["detailed_summary"]
                                except:
                                    pass
                        except:
                            # Just keep the original if parsing fails
                            pass
                    
                    # Remove any triple backticks and json markers
                    detailed_summary = re.sub(r'^```json\s*|\s*```$', '', detailed_summary)
                    
                    # Remove any triple quotes that might be in the content
                    detailed_summary = detailed_summary.replace('"""', '').replace("'''", "")
                
                # If we found the key components, return them in our standard format
                if executive_summary is not None or detailed_summary is not None:
                    # Print debugging info for topics and conclusions
                    print(f"DEBUG: Topics before return: {key_topics}, type: {type(key_topics)}")
                    print(f"DEBUG: Conclusions before return: {takeaways}, type: {type(takeaways)}")
                    
                    # Ensure we always have lists for topics and conclusions
                    if key_topics is None:
                        key_topics = []
                    if takeaways is None:
                        takeaways = []
                        
                    # Final conversion to list if they're still strings
                    if isinstance(key_topics, str):
                        key_topics = [key_topics]
                    if isinstance(takeaways, str):
                        takeaways = [takeaways]
                        
                    return {
                        "executive": executive_summary or "No executive summary available.",
                        "detailed": detailed_summary or "No detailed summary available.",
                        "topics": key_topics or [],
                        "conclusions": takeaways or [],
                        "source_file": summary_data.get("sourcefile", ""),
                        "generated_date": summary_data.get("generated_date", "")
                    }
                else:
                    # Fallback: If we can't find specific summary fields, return the whole content as structured data
                    return {"summary": summary_data}
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
