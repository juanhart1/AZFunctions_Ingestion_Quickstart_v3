import datetime
from pathlib import Path
import time
import json
import openai
import os
from openai import AzureOpenAI
import requests
import re
import logging


def generate_embeddings(text, model_name=None):
    """
    Generates embeddings for the given text using the specified embeddings model provided by OpenAI.

    Args:
        text (str): The text to generate embeddings for.

    Returns:
        embeddings (list): The embeddings generated for the given text.
    """

    # Configure OpenAI with Azure settings
    openai.api_type = "azure"
    openai.api_base = os.environ['AOAI_ENDPOINT']
    openai.api_version = "2023-03-15-preview"
    openai.api_key = os.environ['AOAI_KEY']

    client = AzureOpenAI(
        azure_endpoint=os.environ['AOAI_ENDPOINT'], api_key=os.environ['AOAI_KEY'], api_version="2024-05-01-preview"
    )

    embedding_model = os.environ['AOAI_EMBEDDINGS_MODEL']
    if model_name is not None:
        embedding_model = model_name

    # Initialize variable to track if the embeddings have been processed
    processed = False
    # Attempt to generate embeddings, retrying on failure
    while not processed:
        try:
            # Make API call to OpenAI to generate embeddings
            response = client.embeddings.create(input=text, model=embedding_model)
            processed = True
        except Exception as e:  # Catch any exceptions and retry after a delay
            logging.error(e)
            print(e)

            # Added to handle exception where passed context exceeds embedding model's context window
            if 'maximum context length' in str(e):
                text = text[:int(len(text)*0.95)]

            time.sleep(5)

    # Extract embeddings from the response
    embeddings = response.data[0].embedding
    return embeddings

def get_transcription(filename):
    """
    Transcribes the given audio file using the specified transcription model provided by OpenAI.

    Args:
        filename (str): The path to the audio file to transcribe.

    Returns:
        transcript (str): The transcription of the audio file.
    """

    # Configure OpenAI with Azure settings
    openai.api_type = "azure"
    openai.api_base = os.environ['AOAI_WHISPER_ENDPOINT']
    openai.api_key = os.environ['AOAI_WHISPER_KEY']
    openai.api_version = "2023-09-01-preview"

    # Specify the model and deployment ID for the transcription
    model_name = os.environ['AOAI_WHISPER_MODEL_TYPE'] # "whisper-1"
    deployment_id =  os.environ['AOAI_WHISPER_MODEL']

    # Specify the language of the audio
    audio_language="en"

    # Initialize an empty string to store the transcript
    transcript = ''

    # Initialize variable to track if the audio has been transcribed
    transcribed = False

    client = AzureOpenAI(
        api_key=os.environ['AOAI_WHISPER_KEY'], azure_endpoint=os.environ['AOAI_WHISPER_ENDPOINT'], api_version="2024-02-01"
    )


    # Attempt to transcribe the audio, retrying on failure
    while not transcribed:
        try:
            result = client.audio.transcriptions.create(
                file=open(filename, "rb"),            
                model=deployment_id
            )
            transcript = result.text
            transcribed = True
        except Exception as e:  # Catch any exceptions and retry after a delay
            if 'Maximum content size limit' in str(e):
                raise e
            logging.error(e)
            time.sleep(10)
            pass

    # If a transcript was generated, return it
    if len(transcript)>0:
        return transcript

    # If no transcript was generated, raise an exception
    raise Exception("No transcript generated")

def classify_image(b64_image_bytes):
    classification_msg = """
    You review images of individual document pages and determine if there is non-textual 
    visual content such as charts, graphs, diagrams, infographics, reference photographs, 
    screenshots, 3D models, or flowcharts.

    Return only TRUE or FALSE for the provided image.
    """

    user_content = {
        "role": "user",
        "content": [
            {
            "type": "image_url",
            "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_image_bytes}"
                     , "detail": "high"
                }
            }  
        ]
    }

    messages = [ 
            { "role": "system", "content": classification_msg }, 
            user_content
    ]

    api_base = os.environ['AOAI_ENDPOINT']
    api_key = os.environ['AOAI_KEY']
    deployment_name = os.environ['AOAI_GPT_VISION_MODEL']

    base_url = f"{api_base}openai/deployments/{deployment_name}" 
    headers = {   
        "Content-Type": "application/json",   
        "api-key": api_key 
    } 
    endpoint = f"{base_url}/chat/completions?api-version=2023-12-01-preview" 
    data = { 
        "messages": messages, 
        "temperature": 0.0,
        "top_p": 0.95,
        "max_tokens": 50
    }   

    # Make the API call   
    processed = False
    out_str = ''

    while not processed:
        try:
            response = requests.post(endpoint, headers=headers, data=json.dumps(data)) 
            if response.status_code == 429:
                time.sleep(5)
                continue 
            resp_str = response.json()['choices'][0]['message']['content']
            out_str = resp_str
            processed = True
        except Exception as e:
            if 'exceeded token rate' in str(e).lower():
                time.sleep(5)
            else:
                processed = True
                
    if 'true' in out_str.lower():
        return True
    else:
        return False
    

def analyze_image(b64_image_bytes):
    classification_msg = """
    You review images of individual document pages and describe non-textual visual content such as charts, 
    graphs, diagrams, infographics, reference photographs, screenshots, 3D models, or flowcharts.

    Your response should be a JSON object describing the essential non-textual visual content on the page. 
    The key should refer to the object and the value should be a detailed description.
    """

    user_content = {
        "role": "user",
        "content": [
            {
            "type": "image_url",
            "image_url": {
                    "url": f"data:image/jpeg;base64,{b64_image_bytes}"
                     , "detail": "high"
                }
            }  
        ]
    }

    messages = [ 
            { "role": "system", "content": classification_msg }, 
            user_content
    ]

    api_base = os.environ['AOAI_ENDPOINT']
    api_key = os.environ['AOAI_KEY']
    deployment_name = os.environ['AOAI_GPT_VISION_MODEL']

    base_url = f"{api_base}openai/deployments/{deployment_name}" 
    headers = {   
        "Content-Type": "application/json",   
        "api-key": api_key 
    } 
    endpoint = f"{base_url}/chat/completions?api-version=2023-12-01-preview" 
    data = { 
        "messages": messages, 
        "temperature": 0.0,
        "top_p": 0.95,
        "max_tokens": 800
    }   

    # Make the API call   
    processed = False
    out_str = ''

    while not processed:
        try:
            response = requests.post(endpoint, headers=headers, data=json.dumps(data)) 
            if response.status_code == 429:
                time.sleep(5)
                continue
            resp_str = response.json()['choices'][0]['message']['content']
            out_str = resp_str
            processed = True
        except Exception as e:
            if 'exceeded token rate' in str(e).lower():
                time.sleep(5)
            else:
                processed = True
                break

    # Regex pattern to match the outer-most JSON object
    pattern = re.compile(r'\{.*\}', re.DOTALL)
    # Search for the JSON object
    match = pattern.search(out_str)

    # Extract and print the JSON object if found
    if match:
        out_str = match.group(0)

    return out_str
        

def generate_qna_pair_helper(content):
    sys_msg = """You are a helpful AI assistant who reviews snippets of documents and generates a question and answer pair that can be UNIQUELY answered by the content within the provided document. 
    The question-answer pair you generate should be specific to the underlying information in the provided documents, rather than a question about the document itself. 
    To the extent possible, these questions should cover broader ideas.
    Ideally, these questions should be answerable without an individual having the document directly in front of them.
    For instance, ask 'What are the emerging trends in AI in 2024?' rather than 'What are the key AI trends listed in the document?' 

    Your output format should be a JSON object with the following structure:

    {
        'question': '',
        'answer':''
    }
    """
    user_msg = f"""Generate a question/answer pair based on the following content.

    ## CONTENT: {content}
    """
    
    messages = [ 
            { "role": "system", "content": sys_msg }, 
            {"role": "user", "content": user_msg}
    ]

    api_base = os.environ['AOAI_ENDPOINT']
    api_key = os.environ['AOAI_KEY']
    deployment_name = os.environ['AOAI_GPT_VISION_MODEL']

    base_url = f"{api_base}openai/deployments/{deployment_name}" 
    headers = {   
        "Content-Type": "application/json",   
        "api-key": api_key 
    } 
    endpoint = f"{base_url}/chat/completions?api-version=2023-12-01-preview" 
    data = { 
        "messages": messages, 
        "temperature": 0.0,
        "top_p": 0.95,
        "max_tokens": 500,
        "response_format": {"type": "json_object"}
    }   

    # Make the API call   
    processed = False
    out_str = ''

    while not processed:
        try:
            response = requests.post(endpoint, headers=headers, data=json.dumps(data)) 
            if response.status_code == 429:
                time.sleep(5)
                continue
            resp_str = response.json()['choices'][0]['message']['content']
            out_str = resp_str
            processed = True
        except Exception as e:
            if 'exceeded token rate' in str(e).lower():
                time.sleep(5)
            else:
                processed = True
                
    return json.loads(out_str)

def generate_hierarchical_summary(content):
    """
    Generates a hierarchical summary of document content using Azure OpenAI.
    
    Args:
        content (str): The document content to summarize
        
    Returns:
        dict: A hierarchical summary with high-level, detailed, and section-specific summaries
    """
    sys_msg = """You are an expert at creating hierarchical document summaries. Given document content, create a structured summary with:
    1. An executive summary (2-3 sentences)
    2. A detailed summary (2-3 paragraphs)
    3. Key topics/themes
    4. Main conclusions or takeaways
    
    Return the summary as a JSON object with these sections."""

    user_msg = f"""Generate a hierarchical summary of this document content:

    {content}"""

    messages = [
        {"role": "system", "content": sys_msg},
        {"role": "user", "content": user_msg}
    ]

    api_base = os.environ['AOAI_ENDPOINT']
    api_key = os.environ['AOAI_KEY']
    deployment_name = os.environ['AOAI_GPT_MODEL']

    base_url = f"{api_base}openai/deployments/{deployment_name}"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    endpoint = f"{base_url}/chat/completions?api-version=2025-01-01-preview"
    data = {
        "messages": messages,
        "temperature": 0.3,
        "top_p": 0.95,
        "max_tokens": 1000
    }
    
    # Only add response_format for newer API versions
    if "2024" in os.environ.get("AOAI_API_VERSION", "2023-05-15"):
        data["response_format"] = {"type": "json_object"}

    processed = False
    max_retries = 5
    retry_count = 0
    last_error = None
    
    while not processed and retry_count < max_retries:
        try:
            logging.info(f"Making hierarchical summary API request, attempt {retry_count + 1}/{max_retries}")
            response = requests.post(endpoint, headers=headers, data=json.dumps(data))
            
            # Log response status and info for debugging
            logging.info(f"Summary API response status: {response.status_code}")
            
            if response.status_code != 200:
                error_detail = response.text if response.text else "No error details available"
                logging.error(f"Azure OpenAI API error: HTTP {response.status_code}: {error_detail}")
                
                # If we get a 400 error, try a fallback approach on first retry
                if response.status_code == 400 and retry_count == 0:
                    fallback_model = "gpt-4" if deployment_name != "gpt-4" else "gpt-35-turbo"
                    fallback_endpoint = f"{api_base}openai/deployments/{fallback_model}/chat/completions?api-version=2023-05-15"
                    logging.warning(f"Trying fallback model: {fallback_model}")
                    
                    # Simplify the request for the fallback
                    fallback_data = {
                        "messages": messages,
                        "temperature": 0.3,
                        "max_tokens": 800
                    }
                    
                    try:
                        fallback_response = requests.post(fallback_endpoint, headers=headers, json=fallback_data)
                        if fallback_response.status_code == 200:
                            response = fallback_response
                        else:
                            logging.error(f"Fallback request failed with status {fallback_response.status_code}")
                    except Exception as fallback_error:
                        logging.error(f"Fallback request failed: {str(fallback_error)}")
                
            # Process successful response
            if response.status_code == 200:
                resp_json = response.json()
                
                # Defensive programming - check if 'choices' exists in the response
                if 'choices' in resp_json and len(resp_json['choices']) > 0:
                    message = resp_json['choices'][0].get('message', {})
                    content = message.get('content', '')
                    
                    if content:
                        # Try to parse as JSON first
                        try:
                            return json.loads(content)
                        except json.JSONDecodeError:
                            # If not valid JSON, return a basic structure with the content
                            logging.warning("Response was not valid JSON, returning basic structure")
                            return {
                                "executive_summary": content[:200] + "...",
                                "detailed_summary": content,
                                "key_topics": ["Unable to parse topics"],
                                "takeaways": ["See detailed summary"]
                            }
                    else:
                        raise ValueError("Empty content in response")
                else:
                    # Log the actual response for debugging
                    logging.error(f"Unexpected response structure: {json.dumps(resp_json)}")
                    raise KeyError("Response missing 'choices' field")
            
            processed = True
            
        except (KeyError, ValueError) as e:
            last_error = e
            retry_count += 1
            if retry_count < max_retries:
                sleep_time = 2 * retry_count
                logging.warning(f"Retry {retry_count} for summary generation: {str(e)}. Retrying in {sleep_time}s")
                time.sleep(sleep_time)
            else:
                logging.error(f"Failed to generate summary after {max_retries} attempts: {str(e)}")
                # Return a fallback summary instead of raising an error
                return {
                    "executive_summary": "Summary generation failed. Please see the document for details.",
                    "detailed_summary": "We were unable to generate a summary for this content due to technical issues.",
                    "key_topics": ["Error during processing"],
                    "takeaways": ["Please review the original document"]
                }
        except Exception as e:
            last_error = e
            retry_count += 1
            if retry_count < max_retries:
                sleep_time = 2 * retry_count
                logging.warning(f"Retry {retry_count} for summary generation: {str(e)}. Retrying in {sleep_time}s")
                time.sleep(sleep_time)
            else:
                logging.error(f"Failed to generate summary after {max_retries} attempts: {str(e)}")
                # Return a fallback summary instead of raising an error
                return {
                    "executive_summary": "Summary generation failed. Please see the document for details.",
                    "detailed_summary": "We were unable to generate a summary for this content due to technical issues.",
                    "key_topics": ["Error during processing"],
                    "takeaways": ["Please review the original document"]
                }
    
    # This should never be reached due to the returns above, but just in case
    if not processed:
        logging.error("Summary generation did not complete successfully")
        return {
            "executive_summary": "Summary generation did not complete.",
            "detailed_summary": "The summary process did not complete successfully.",
            "key_topics": ["Processing incomplete"],
            "takeaways": ["Please review the original document"]
        }
