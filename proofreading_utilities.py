import os
import json
import requests
import time
import logging

def _call_azure_openai(prompt, content):
    """Helper function to make Azure OpenAI API calls"""
    base_endpoint = os.environ["AOAI_ENDPOINT"].rstrip('/')
    key = os.environ["AOAI_KEY"]
    model = os.environ.get("AOAI_GPT_MODEL", "gpt-4o")  # Default to gpt-4o if not specified
    deployment_name = os.environ.get("AOAI_DEPLOYMENT_NAME", model)  # Use explicit deployment name if available
    api_version = os.environ.get("AOAI_API_VERSION", "2023-05-15")  # Use API version from env or default
    max_retries = 5
    retry_delay = 5
    
    # Log model and deployment information for debugging
    logging.info(f"Using model: {model}, deployment: {deployment_name}, API version: {api_version}")
    
    # Construct the full endpoint URL
    endpoint = f"{base_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version={api_version}"
    
    headers = {
        "Content-Type": "application/json",
        "api-key": key
    }
    
    # Build request payload without response_format for compatibility with older API versions
    data = {
        "messages": [
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": content
            }
        ],
        "temperature": 0.1,
        "max_tokens": 4000  # Reduced max tokens to avoid potential limits
    }
    
    # Only add response_format for newer API versions that support it
    if api_version.startswith("2024"):
        data["response_format"] = {"type": "json_object"}
    
    for attempt in range(max_retries):
        try:
            logging.info(f"Making Azure OpenAI request, attempt {attempt + 1}/{max_retries}")
            response = requests.post(endpoint, headers=headers, json=data)
            
            # More detailed error logging
            if response.status_code != 200:
                error_detail = response.text if response.text else "No error details available"
                logging.error(f"Azure OpenAI API error: HTTP {response.status_code}: {error_detail}")
                
                # Handle content filtering errors specifically
                content_filtered = False
                if response.status_code == 400:
                    try:
                        error_json = response.json()
                        error_message = error_json.get('error', {}).get('message', '')
                        if 'content management policy' in error_message or 'content filter' in error_message.lower():
                            content_filtered = True
                            logging.warning("Content filtered by Azure OpenAI safety system")
                    except Exception:
                        pass  # Continue with normal error handling if we can't parse the response
                
                # If we get a 400 error related to the model or content filtering, try a fallback approach
                if (response.status_code == 400 or response.status_code == 404) and attempt == 0:
                    # Define fallback models in order of preference
                    fallback_models = []
                    
                    # Primary fallback model is gpt-4 if we're not already using it
                    if deployment_name != "gpt-4":
                        fallback_models.append("gpt-4")
                    
                    # Secondary fallback is gpt-35-turbo
                    if deployment_name != "gpt-35-turbo":
                        fallback_models.append("gpt-35-turbo")
                    
                    # Try each fallback model
                    for fallback_model in fallback_models:
                        try:
                            fallback_endpoint = f"{base_endpoint}/openai/deployments/{fallback_model}/chat/completions?api-version=2023-05-15"
                            logging.warning(f"Trying fallback model: {fallback_model}")
                            
                            # Use simplified prompt for fallback to reduce chances of content filtering
                            if content_filtered:
                                # Simplify the system prompt to avoid content filtering
                                fallback_data = {
                                    "messages": [
                                        {
                                            "role": "system", 
                                            "content": "You are a helpful assistant. Analyze the text and respond in JSON format."
                                        },
                                        {
                                            "role": "user",
                                            "content": f"Analyze this text and provide suggestions in JSON format: {content[:1000]}..."
                                        }
                                    ],
                                    "temperature": 0.1,
                                    "max_tokens": 2000
                                }
                            else:
                                # Use original prompt if not content filtered
                                fallback_data = {
                                    "messages": data["messages"],
                                    "temperature": 0.1,
                                    "max_tokens": 2000
                                }
                            
                            fallback_response = requests.post(fallback_endpoint, headers=headers, json=fallback_data)
                            
                            if fallback_response.status_code == 200:
                                logging.info(f"Fallback to {fallback_model} succeeded")
                                response = fallback_response
                                break
                            else:
                                fallback_error = fallback_response.text if fallback_response.text else f"HTTP {fallback_response.status_code}"
                                logging.error(f"Fallback to {fallback_model} failed: {fallback_error}")
                        except Exception as fallback_error:
                            logging.error(f"Fallback to {fallback_model} failed: {str(fallback_error)}")
                    
                    # If we reached here and still have an error status, all fallbacks failed
                    if response.status_code != 200:
                        logging.error("All fallback attempts failed")
            
            # Check if we have a successful response after all attempts
            if response.status_code != 200:
                if attempt == max_retries - 1:
                    logging.warning("All attempts failed, returning empty suggestions array")
                    return {"suggestions": []}
                continue  # Try again if we have retries left
            
            result = response.json()
            
            # Defensive check for choices
            if 'choices' not in result or not result['choices']:
                logging.error(f"No choices in API response: {json.dumps(result)}")
                if attempt < max_retries - 1:
                    continue  # Try again
                return {"suggestions": []}
            
            content = result['choices'][0]['message']['content']
            logging.debug(f"Azure OpenAI raw response: {content}")
            
            # If content is already a dict/list, return it directly
            if isinstance(content, (dict, list)):
                logging.info(f"Response already in correct format, found {len(content.get('suggestions', []))} suggestions")
                return content
            
            # Clean the response string
            content = content.strip()
            if content.startswith('```json'):
                content = content[7:]  # Remove ```json prefix
            if content.endswith('```'):
                content = content[:-3]  # Remove ``` suffix
            content = content.strip()
            
            # Try to parse the cleaned JSON
            try:
                parsed = json.loads(content)
                logging.info(f"Successfully parsed JSON response, found {len(parsed.get('suggestions', []))} suggestions")
                return parsed
            except json.JSONDecodeError as je:
                logging.error(f"Initial JSON parse failed at position {je.pos}: {je.msg}")
                logging.error(f"Problematic content: {content[max(0, je.pos-50):min(len(content), je.pos+50)]}")
                
                # Try to extract valid JSON from the response
                if '"suggestions":' in content:
                    try:
                        # Find the suggestions array
                        suggestions_start = content.find('"suggestions":') + len('"suggestions":')
                        suggestions_text = content[suggestions_start:].strip()
                        
                        # Extract the array portion
                        if suggestions_text.startswith('['):
                            bracket_count = 1
                            end_pos = -1
                            for i, char in enumerate(suggestions_text[1:], 1):
                                if char == '[':
                                    bracket_count += 1
                                elif char == ']':
                                    bracket_count -= 1
                                    if bracket_count == 0:
                                        end_pos = i + 1
                                        break
                                        
                            if end_pos > 0:
                                suggestions = json.loads(suggestions_text[:end_pos])
                                logging.info(f"Successfully extracted suggestions array with {len(suggestions)} items")
                                return {"suggestions": suggestions}
                    except Exception as e:
                        logging.error(f"Failed to extract suggestions array: {str(e)}")
                        logging.error(f"Content that failed to parse: {suggestions_text[:200]}...")
                
                logging.warning("Returning empty suggestions array after all JSON parsing attempts failed")
                return {"suggestions": []}
                
        except requests.exceptions.RequestException as e:
            logging.error(f"Error calling Azure OpenAI: {str(e)}")
            if 'exceeded token rate' in str(e).lower() or (hasattr(response, 'status_code') and response.status_code == 429):
                if attempt < max_retries - 1:
                    retry_time = retry_delay * (attempt + 1)
                    logging.warning(f"Rate limit exceeded. Retrying in {retry_time} seconds...")
                    time.sleep(retry_time)
                    continue
            
            # For the last attempt, don't raise the error, just return empty results
            if attempt == max_retries - 1:
                logging.warning("All retries failed, returning empty suggestions array")
                return {"suggestions": []}
                
        except Exception as e:
            logging.error(f"Error processing Azure OpenAI response: {str(e)}")
            
            # For the last attempt, don't raise the error, just return empty results
            if attempt == max_retries - 1:
                logging.warning("All retries failed due to processing errors, returning empty suggestions array")
                return {"suggestions": []}
    
    # This should never be reached due to the return in the exception handler above
    return {"suggestions": []}

def check_spelling(text: str) -> list:
    """Check text for spelling errors using Azure OpenAI."""
    if not text or not isinstance(text, str):
        logging.warning("Invalid input to check_spelling: empty or non-string input")
        return []
        
    logging.info(f"Starting spelling check on text of length {len(text)}")
    prompt = """You are a professional proofreader focusing on spelling errors.

    RESPONSE FORMAT:
    You must respond with a valid JSON object using this exact schema:
    {
        "suggestions": [
            {
                "error": "misspelled word",
                "suggestion": "correct spelling",
                "context": "sentence containing the error"
            }
        ]
    }

    If no errors are found, respond with exactly: {"suggestions": []}

    INSTRUCTIONS:
    1. Check every word carefully for spelling errors
    2. Consider context to distinguish between errors and specialized terms
    3. DO NOT include any explanations or text outside the JSON structure
    4. Include surrounding context to show word usage
    5. Use standard English spelling

    Analyze the text for spelling errors and respond only with the JSON object."""
    
    try:
        result = _call_azure_openai(prompt, text)
        suggestions = result.get('suggestions', [])
        logging.info(f"Spelling check completed, found {len(suggestions)} potential issues")
        for suggestion in suggestions:
            logging.debug(f"Spelling issue found: {suggestion.get('error')} -> {suggestion.get('suggestion')}")
        return suggestions
    except Exception as e:
        logging.error(f"Error in check_spelling: {str(e)}", exc_info=True)
        return []

def check_grammar(text: str) -> list:
    """Check text for grammar errors using Azure OpenAI."""
    if not text or not isinstance(text, str):
        logging.warning("Invalid input to check_grammar: empty or non-string input")
        return []
        
    logging.info(f"Starting grammar check on text of length {len(text)}")
    prompt = """You are a professional proofreader specializing in grammar.

    RESPONSE FORMAT:
    You must respond with a valid JSON object using this exact schema:
    {
        "suggestions": [
            {
                "error": "grammatical error phrase",
                "suggestion": "corrected phrase",
                "context": "complete sentence containing the error",
                "explanation": "brief explanation of the grammar rule"
            }
        ]
    }

    If no errors are found, respond with exactly: {"suggestions": []}

    INSTRUCTIONS:
    1. Check sentence structure, verb tense agreement, punctuation
    2. Include the full problematic phrase, not just single words
    3. Provide the complete corrected phrase
    4. DO NOT include any text outside the JSON structure
    5. Focus on clear grammatical errors, not style preferences

    Analyze the text for grammar errors and respond only with the JSON object."""
    
    try:
        result = _call_azure_openai(prompt, text)
        suggestions = result.get('suggestions', [])
        logging.info(f"Grammar check completed, found {len(suggestions)} potential issues")
        for suggestion in suggestions:
            logging.debug(f"Grammar issue found: {suggestion.get('error')} -> {suggestion.get('suggestion')} ({suggestion.get('explanation')})")
        return suggestions
    except Exception as e:
        logging.error(f"Error in check_grammar: {str(e)}", exc_info=True)
        return []

def check_clarity(text: str) -> list:
    """Check text for clarity issues using Azure OpenAI."""
    if not text or not isinstance(text, str):
        logging.warning("Invalid input to check_clarity: empty or non-string input")
        return []
        
    logging.info(f"Starting clarity check on text of length {len(text)}")
    prompt = """You are a professional editor specializing in clarity and readability.

    RESPONSE FORMAT:
    You must respond with a valid JSON object using this exact schema:
    {
        "suggestions": [
            {
                "issue": "description of clarity issue",
                "suggestion": "recommended improvement",
                "context": "unclear passage",
                "impact": "how this affects readability"
            }
        ]
    }

    If no issues are found, respond with exactly: {"suggestions": []}

    INSTRUCTIONS:
    1. Focus on readability and comprehension issues
    2. Identify complex or confusing passages
    3. Suggest clearer alternatives
    4. DO NOT include any text outside the JSON structure
    5. Consider audience comprehension level

    Analyze the text for clarity issues and respond only with the JSON object."""
    
    try:
        result = _call_azure_openai(prompt, text)
        suggestions = result.get('suggestions', [])
        logging.info(f"Clarity check completed, found {len(suggestions)} potential issues")
        for suggestion in suggestions:
            logging.debug(f"Clarity issue found: {suggestion.get('issue')} -> {suggestion.get('suggestion')}")
        return suggestions
    except Exception as e:
        logging.error(f"Error in check_clarity: {str(e)}", exc_info=True)
        return []

def check_style(text: str) -> list:
    """Check text for style consistency using Azure OpenAI."""
    if not text or not isinstance(text, str):
        logging.warning("Invalid input to check_style: empty or non-string input")
        return []
        
    logging.info(f"Starting style check on text of length {len(text)}")
    prompt = """You are a professional editor specializing in style consistency.

    RESPONSE FORMAT:
    You must respond with a valid JSON object using this exact schema:
    {
        "suggestions": [
            {
                "issue": "description of style issue",
                "suggestion": "recommended improvement",
                "context": "relevant passage",
                "category": "type of style issue"
            }
        ]
    }

    If no issues are found, respond with exactly: {"suggestions": []}

    INSTRUCTIONS:
    1. Check for consistency in tone, formality, and terminology
    2. Identify style shifts or inconsistencies
    3. Suggest consistent alternatives
    4. DO NOT include any text outside the JSON structure
    5. Focus on document-level consistency

    Analyze the text for style issues and respond only with the JSON object."""
    
    try:
        result = _call_azure_openai(prompt, text)
        suggestions = result.get('suggestions', [])
        logging.info(f"Style check completed, found {len(suggestions)} potential issues")
        for suggestion in suggestions:
            logging.debug(f"Style issue found: {suggestion.get('issue')} -> {suggestion.get('suggestion')} ({suggestion.get('category')})")
        return suggestions
    except Exception as e:
        logging.error(f"Error in check_style: {str(e)}", exc_info=True)
        return []

def check_document_grammar(content):
    """Check document for grammar issues"""
    prompt = """You are a professional proofreader. Analyze the following text for grammar, syntax, and spelling errors.
    Return your response in the following JSON format:
    {
        "suggestions": [
            {
                "type": "grammar"|"spelling"|"syntax",
                "original": "the problematic text",
                "suggestion": "the suggested correction",
                "explanation": "brief explanation of the issue"
            }
        ]
    }
    Only include actual errors, not style suggestions. If there are no issues, return an empty suggestions array."""

    try:
        logging.info("Starting grammar check")
        result = _call_azure_openai(prompt, content)
        
        if not isinstance(result, dict):
            logging.error(f"Unexpected response format from grammar check: {type(result)}")
            return {"suggestions": []}
            
        suggestions = result.get("suggestions", [])
        if not isinstance(suggestions, list):
            logging.error(f"Invalid suggestions format: {type(suggestions)}")
            return {"suggestions": []}
            
        logging.info(f"Grammar check completed successfully with {len(suggestions)} suggestions")
        return {"suggestions": suggestions}
        
    except Exception as e:
        logging.error(f"Error in grammar check: {str(e)}")
        return {"suggestions": []}