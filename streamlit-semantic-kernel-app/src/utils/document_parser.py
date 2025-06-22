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
            
        # Parse the "detailed" field which contains the nested JSON string
        try:
            detailed_string = json_data.get("detailed", "{}")
            print(f"DEBUG: Parsing detailed string: {detailed_string[:100]}...")
            detailed_json = json.loads(detailed_string)
        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract data using regex
            detailed_string = json_data.get("detailed", "{}")
            detailed_json = {}
            print(f"DEBUG: JSON parse failed, using regex on: {detailed_string[:100]}...")
            
            # Extract executive summary
            exec_summary_match = re.search(r'"executive_summary"\s*:\s*"([^"]+)"', detailed_string)
            if exec_summary_match:
                detailed_json["executive_summary"] = exec_summary_match.group(1)
            
            # Extract detailed summary
            detailed_summary_match = re.search(r'"detailed_summary"\s*:\s*"([^"]+)"', detailed_string)
            if detailed_summary_match:
                detailed_json["detailed_summary"] = detailed_summary_match.group(1)
            
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
        
        # Extract the required fields
        executive_summary = detailed_json.get("executive_summary", "")
        detailed_summary = detailed_json.get("detailed_summary", "")
        key_topics_themes = detailed_json.get("key_topics_themes", [])
        main_conclusions_takeaways = detailed_json.get("main_conclusions_takeaways", [])
        
        # Get metadata
        source_file = json_data.get("source_file", "")
        generated_date = json_data.get("generated_date", "")
        
        # Debug the values
        print(f"DEBUG: Topics before return: {key_topics_themes}, type: {type(key_topics_themes)}")
        print(f"DEBUG: Conclusions before return: {main_conclusions_takeaways}, type: {type(main_conclusions_takeaways)}")
        
        # Create the result dictionary with all possible field names needed by the UI
        result = {
            "executive_summary": executive_summary,
            "detailed_summary": detailed_summary,
            "key_topics_themes": key_topics_themes,
            "main_conclusions_takeaways": main_conclusions_takeaways,
            # Add the field names expected by the display_result function
            "topics": key_topics_themes,
            "conclusions": main_conclusions_takeaways,
            "source_file": source_file,
            "generated_date": generated_date
        }
        
        print(f"DEBUG: Final result keys: {list(result.keys())}")
        print(f"DEBUG: Final topics in 'topics': {result['topics']}")
        print(f"DEBUG: Final conclusions in 'conclusions': {result['conclusions']}")
        
        # If we couldn't extract topics or conclusions from the detailed field but they exist in the original, use them as a fallback
        if (not result["topics"] or len(result["topics"]) == 0) and json_data.get("topics"):
            result["topics"] = json_data.get("topics")
            # Also update the key_topics_themes for consistency
            result["key_topics_themes"] = result["topics"]
            print(f"DEBUG: Using fallback topics: {result['topics']}")
        
        if (not result["conclusions"] or len(result["conclusions"]) == 0) and json_data.get("conclusions"):
            result["conclusions"] = json_data.get("conclusions")
            # Also update the main_conclusions_takeaways for consistency
            result["main_conclusions_takeaways"] = result["conclusions"]
            print(f"DEBUG: Using fallback conclusions: {result['conclusions']}")
        
        # Return the parsed data with all required UI fields
        return result
    except json.JSONDecodeError as e:
        return {
            "executive_summary": f"Error parsing document summary: {str(e)}",
            "detailed_summary": f"Error parsing document summary: {str(e)}",
            "topics": [],
            "conclusions": [],
            "key_topics_themes": [],
            "main_conclusions_takeaways": [],
            "source_file": "Unknown",
            "generated_date": "Unknown"
        }
    except Exception as e:
        return {
            "executive_summary": f"An unexpected error occurred: {str(e)}",
            "detailed_summary": f"An unexpected error occurred: {str(e)}",
            "topics": [],
            "conclusions": [],
            "key_topics_themes": [],
            "main_conclusions_takeaways": [],
            "source_file": "Unknown",
            "generated_date": "Unknown"
        }
