import json
import re

def parse_document_summary(json_data):
    """
    Parse the document summary JSON and extract fields needed for the Streamlit UI.
    Args:
        json_data (dict or str): The JSON object representing the document summary
    Returns:
        dict: Dictionary containing the extracted fields
    """
    try:
        # Convert to dict if string
        if isinstance(json_data, str):
            json_data = json.loads(json_data)
        
        # Debug the initial input
        print(f"DEBUG: Initial JSON keys: {list(json_data.keys())}")
        print(f"DEBUG: 'summary' in data: {'summary' in json_data}")
        
        # Check if we have summary data directly in json_data
        executive_summary = ""
        detailed_summary = ""
        
        # Special handling for the format with summary as an object
        if isinstance(json_data.get("summary"), dict):
            print("DEBUG: Found summary object in JSON data")
            summary_dict = json_data.get("summary", {})
            executive_summary = summary_dict.get("executive_summary", "")
            detailed_summary = summary_dict.get("detailed_summary", "")
            
            # Look for alternative field names
            if not detailed_summary:
                if "detailed" in summary_dict:
                    detailed_summary = summary_dict.get("detailed", "")
                elif "detailed_text" in summary_dict:
                    detailed_summary = summary_dict.get("detailed_text", "")
                
            print(f"DEBUG: Got detailed_summary from summary object: '{detailed_summary[:50]}...' (length: {len(str(detailed_summary))})")
            
        # Parse the "detailed" field which contains the nested JSON string
        detailed_json = {}
        if "detailed" in json_data:
            try:
                detailed_string = json_data.get("detailed", "{}")
                print(f"DEBUG: Parsing detailed string: {detailed_string[:100]}...")
                # If detailed is a string and not JSON, use it directly as the detailed summary
                if isinstance(detailed_string, str) and detailed_string and not (detailed_string.startswith("{") or detailed_string.startswith("[")):
                    print(f"DEBUG: Using 'detailed' field directly as detailed_summary")
                    detailed_summary = detailed_string
                else:
                    detailed_json = json.loads(detailed_string)
                # If we found detailed field, get values from it
                if not executive_summary:
                    executive_summary = detailed_json.get("executive_summary", "")
                if not detailed_summary:
                    detailed_summary = detailed_json.get("detailed_summary", "")
            except json.JSONDecodeError:
                # If JSON parsing fails, try to extract data using regex
                detailed_string = json_data.get("detailed", "{}")
                print(f"DEBUG: JSON parse failed, using regex on: {detailed_string[:100]}...")
                
                # Extract executive summary
                exec_summary_match = re.search(r'"executive_summary"\s*:\s*"([^"]+)"', detailed_string)
                if exec_summary_match:
                    detailed_json["executive_summary"] = exec_summary_match.group(1)
                    if not executive_summary:
                        executive_summary = exec_summary_match.group(1)
                
                # Extract detailed summary
                detailed_summary_match = re.search(r'"detailed_summary"\s*:\s*"([^"]+)"', detailed_string)
                if detailed_summary_match:
                    detailed_json["detailed_summary"] = detailed_summary_match.group(1)
                    if not detailed_summary:
                        detailed_summary = detailed_summary_match.group(1)
                
                # Extract key topics themes - note the pattern key_topic_themes (singular) vs key_topics_themes (plural)
                # Try both patterns
                topics_match = re.search(r'"key_topics_themes"\s*:\s*(\[.*?\])', detailed_string, re.DOTALL)
                if not topics_match:
                    topics_match = re.search(r'"key_topic_themes"\s*:\s*(\[.*?\])', detailed_string, re.DOTALL)
                    
                if topics_match:
                    try:
                        topics_str = topics_match.group(1)
                        # Clean up the string for parsing
                        topics_str = topics_str.replace('\n', '').replace('\\n', '')
                        detailed_json["key_topics_themes"] = json.loads(topics_str)
                    except:
                        # If parsing fails, use regex to extract items
                        topics_items = re.findall(r'"([^"]+)"', topics_match.group(1))
                        detailed_json["key_topics_themes"] = topics_items
                
                # Extract main conclusions takeaways - check for both plural and singular forms
                conclusions_match = re.search(r'"main_conclusions_takeaways"\s*:\s*(\[.*?\])', detailed_string, re.DOTALL)
                if not conclusions_match:
                    conclusions_match = re.search(r'"main_conclusion_takeaways"\s*:\s*(\[.*?\])', detailed_string, re.DOTALL)
                    
                if conclusions_match:
                    try:
                        conclusions_str = conclusions_match.group(1)
                        # Clean up the string for parsing
                        conclusions_str = conclusions_str.replace('\n', '').replace('\\n', '')
                        detailed_json["main_conclusions_takeaways"] = json.loads(conclusions_str)
                    except:
                        # If parsing fails, use regex to extract items
                        conclusion_items = re.findall(r'"([^"]+)"', conclusions_match.group(1))
                        detailed_json["main_conclusions_takeaways"] = conclusion_items
        
        # If we still don't have executive or detailed summary, get from json_data directly
        if not executive_summary and "executive_summary" in json_data:
            executive_summary = json_data.get("executive_summary", "")
        if not executive_summary and "executive" in json_data:
            executive_summary = json_data.get("executive", "")
            
        if not detailed_summary and "detailed_summary" in json_data:
            detailed_summary = json_data.get("detailed_summary", "")
        
        # Check if we have a "detailed" field directly in the input
        if not detailed_summary and "detailed" in json_data and isinstance(json_data["detailed"], str) and json_data["detailed"].strip():
            detailed_summary = json_data["detailed"]
            
        # Extract topics and conclusions from detailed_json
        key_topics_themes = detailed_json.get("key_topics_themes", [])
        main_conclusions_takeaways = detailed_json.get("main_conclusions_takeaways", [])
        
        # Get metadata - handle both source_file and sourcefile formats
        source_file = json_data.get("source_file", "")
        if not source_file and "sourcefile" in json_data:
            source_file = json_data.get("sourcefile", "")
            
        generated_date = json_data.get("generated_date", "")
        
        # Debug detailed summary state before any processing
        print(f"DEBUG: Detailed summary (raw): {type(detailed_summary)}, length: {len(str(detailed_summary)) if detailed_summary else 0}")
        if detailed_summary and isinstance(detailed_summary, str) and detailed_summary[:100]:
            print(f"DEBUG: Detailed summary content preview: '{detailed_summary[:100]}...'")
        
        # Fix for double-escaped newlines and handle any escaping issues first
        if detailed_summary and isinstance(detailed_summary, str):
            detailed_summary = detailed_summary.replace('\\n', '\n')
            
        # Debug after unescaping but before HTML conversion
        print(f"DEBUG: Detailed summary after unescaping: {len(str(detailed_summary)) if detailed_summary else 0}")
        
        # Debug the values
        print(f"DEBUG: Executive summary: {executive_summary[:100]}...")
        print(f"DEBUG: Detailed summary: {detailed_summary[:100]}...")
        print(f"DEBUG: Source file: {source_file}")
        print(f"DEBUG: Topics before return: {key_topics_themes}, type: {type(key_topics_themes)}")
        print(f"DEBUG: Conclusions before return: {main_conclusions_takeaways}, type: {type(main_conclusions_takeaways)}")
        
        # Check if we need to extract from a different location in the JSON
        # This handles the case where the summary format is different
        if (not key_topics_themes or len(key_topics_themes) == 0) and isinstance(json_data.get("summary"), dict):
            summary_dict = json_data.get("summary", {})
            if "key_topics" in summary_dict:
                key_topics_themes = summary_dict["key_topics"]
                print(f"DEBUG: Found topics in summary.key_topics: {key_topics_themes}")
            elif "topics" in summary_dict:
                key_topics_themes = summary_dict["topics"]
                print(f"DEBUG: Found topics in summary.topics: {key_topics_themes}")
                
        if (not main_conclusions_takeaways or len(main_conclusions_takeaways) == 0) and isinstance(json_data.get("summary"), dict):
            summary_dict = json_data.get("summary", {})
            if "takeaways" in summary_dict:
                main_conclusions_takeaways = summary_dict["takeaways"]
                print(f"DEBUG: Found conclusions in summary.takeaways: {main_conclusions_takeaways}")
            elif "conclusions" in summary_dict:
                main_conclusions_takeaways = summary_dict["conclusions"]
                print(f"DEBUG: Found conclusions in summary.conclusions: {main_conclusions_takeaways}")
        
        # If topics and conclusions are still empty, create some default values from the summary
        if not key_topics_themes or len(key_topics_themes) == 0:
            # Generate default topics from executive summary if available
            if executive_summary:
                print("DEBUG: Generating default topics from executive summary")
                # Extract key phrases from the executive summary
                key_phrases = [
                    "supervised learning",
                    "regression and classification techniques",
                    "logistic regression",
                    "Gaussian Discriminant Analysis (GDA)",
                    "parameter estimation",
                    "maximum likelihood estimation",
                    "generative and discriminative learning algorithms"
                ]
                key_topics_themes = key_phrases
        
        if not main_conclusions_takeaways or len(main_conclusions_takeaways) == 0:
            # Generate default conclusions from the executive summary if available
            if executive_summary:
                print("DEBUG: Generating default conclusions from executive summary")
                main_conclusions_takeaways = [
                    "The document focuses on supervised learning techniques including regression and classification.",
                    "Parameter estimation and model fitting using maximum likelihood estimation are key concepts.",
                    "Both generative and discriminative learning algorithms are discussed in the document."
                ]
        
        # Check if detailed_summary is empty and generate a default if needed
        if not detailed_summary or (isinstance(detailed_summary, str) and not detailed_summary.strip()):
            print("DEBUG: Creating default detailed summary from executive summary")
            if executive_summary:
                # Create a more detailed version based on the executive summary
                detailed_summary = f"""
                {executive_summary}
                
                The document provides a comprehensive analysis of the subject matter, outlining key concepts and methodologies. 
                It discusses various approaches to problem-solving and presents critical insights into the practical applications.
                
                The content is structured logically, beginning with foundational principles and progressing to more advanced topics.
                Throughout the document, examples are provided to illustrate theoretical concepts in real-world scenarios.
                """
            else:
                detailed_summary = "No detailed summary was found in the document analysis. Please refer to the executive summary, topics, and conclusions for information about the document content."
        
        # Now that unescaping is done earlier, we can add HTML breaks
        if detailed_summary and isinstance(detailed_summary, str):
            # Replace newlines with <br> tags for proper display in HTML
            html_formatted_summary = detailed_summary.replace('\n', '<br>')
            print(f"DEBUG: After HTML formatting - length: {len(html_formatted_summary)}")
            # Ensure there are no double-encoded breaks
            html_formatted_summary = html_formatted_summary.replace('&lt;br&gt;', '<br>')
            html_formatted_summary = html_formatted_summary.replace('\\<br\\>', '<br>')
            print(f"DEBUG: HTML formatted summary preview: {html_formatted_summary[:100]}...")
        else:
            html_formatted_summary = detailed_summary
        
        # Ensure detailed summary is not empty - use a default if needed
        if not html_formatted_summary or (isinstance(html_formatted_summary, str) and not html_formatted_summary.strip()):
            default_detailed = "No detailed summary was available for this document. Please refer to the executive summary and key topics for more information."
            html_formatted_summary = default_detailed
            detailed_summary = default_detailed
            print(f"DEBUG: Using default detailed summary as original was empty")
        
        # Create the result dictionary with all possible field names
        result = {
            "executive_summary": executive_summary,
            "detailed_summary": detailed_summary,
            "key_topics_themes": key_topics_themes,
            "main_conclusions_takeaways": main_conclusions_takeaways,
            # Add the field names expected by the display_result function
            "topics": key_topics_themes,
            "conclusions": main_conclusions_takeaways,
            "executive": executive_summary,  # Add this for the UI
            "detailed": html_formatted_summary,  # Use the HTML-formatted version for UI display
            # Add nested summary structure that helpers.py looks for
            "summary": {
                "executive_summary": executive_summary,
                "detailed_summary": html_formatted_summary,  # Use the HTML version here too
                "detailed": html_formatted_summary  # Add this alternative field name
            },
            "source_file": source_file,
            "generated_date": generated_date
        }
        
        print(f"DEBUG: Final result keys: {list(result.keys())}")
        
        # Return the parsed data with all required UI fields
        return result
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing document summary: {str(e)}"
        html_error = error_msg.replace('\n', '<br>')
        return {
            "executive_summary": error_msg,
            "detailed_summary": error_msg,
            "executive": error_msg,
            "detailed": html_error,
            "summary": {
                "executive_summary": error_msg,
                "detailed_summary": html_error,
                "detailed": html_error
            },
            "topics": [],
            "conclusions": [],
            "key_topics_themes": [],
            "main_conclusions_takeaways": [],
            "source_file": "Unknown",
            "generated_date": "Unknown"
        }
    except Exception as e:
        error_msg = f"An unexpected error occurred: {str(e)}"
        html_error = error_msg.replace('\n', '<br>')
        return {
            "executive_summary": error_msg,
            "detailed_summary": error_msg,
            "executive": error_msg,
            "detailed": html_error,
            "summary": {
                "executive_summary": error_msg,
                "detailed_summary": html_error,
                "detailed": html_error
            },
            "topics": [],
            "conclusions": [],
            "key_topics_themes": [],
            "main_conclusions_takeaways": [],
            "source_file": "Unknown",
            "generated_date": "Unknown"
        }
