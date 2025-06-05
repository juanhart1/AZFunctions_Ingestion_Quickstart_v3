import os
import json
import requests
import time
import logging

def _call_azure_openai(prompt, content):
    """Helper function to make Azure OpenAI API calls"""
    api_base = os.environ['AOAI_ENDPOINT']
    api_key = os.environ['AOAI_KEY']
    deployment_name = os.environ['AOAI_GPT_VISION_MODEL']

    base_url = f"{api_base}openai/deployments/{deployment_name}"
    headers = {
        "Content-Type": "application/json",
        "api-key": api_key
    }
    endpoint = f"{base_url}/chat/completions?api-version=2023-12-01-preview"
    
    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": content}
    ]
    
    data = {
        "messages": messages,
        "temperature": 0.0,
        "top_p": 0.95,
        "max_tokens": 800,
        "response_format": {"type": "json_object"}
    }

    processed = False
    while not processed:
        try:
            response = requests.post(endpoint, headers=headers, data=json.dumps(data))
            if response.status_code == 429:
                time.sleep(5)
                continue
            result = response.json()['choices'][0]['message']['content']
            processed = True
            return json.loads(result)
        except Exception as e:
            if 'exceeded token rate' in str(e).lower():
                time.sleep(5)
            else:
                logging.error(f"Error calling Azure OpenAI: {str(e)}")
                raise e

def check_spelling(text: str) -> list:
    """Check text for spelling errors using Azure OpenAI."""
    prompt = """You are a professional proofreader. Analyze the following text for spelling errors.
    Return a JSON array of objects, where each object contains:
    - "error": the misspelled word or phrase
    - "context": the surrounding text for context
    - "suggestions": an array of suggested corrections
    - "message": explanation of the error
    Return an empty array if no spelling errors are found."""
    
    return _call_azure_openai(prompt, text).get("suggestions", [])

def check_grammar(text: str) -> list:
    """Check text for grammar errors using Azure OpenAI."""
    prompt = """You are a professional proofreader. Analyze the following text for grammar and punctuation errors.
    Return a JSON object with a "suggestions" array, where each object contains:
    - "error": the grammatically incorrect text
    - "context": the surrounding text for context
    - "suggestions": an array of suggested corrections
    - "message": explanation of the error
    Return an empty array if no grammar errors are found."""
    
    return _call_azure_openai(prompt, text).get("suggestions", [])

def check_clarity(text: str) -> list:
    """Check text for clarity issues using Azure OpenAI."""
    prompt = """You are a professional editor. Analyze the following text for clarity and readability issues.
    Return a JSON object with a "suggestions" array, where each object contains:
    - "type": either "readability", "sentence_length", or "structure"
    - "message": detailed explanation of the clarity issue
    - "text": the problematic text
    - "improvement": suggested improvement
    Focus on:
    - Complex or confusing sentences
    - Overly long sentences
    - Unclear structure or flow
    Return an empty array if no clarity issues are found."""
    
    return _call_azure_openai(prompt, text).get("suggestions", [])

def check_style(text: str) -> list:
    """Check text for style issues using Azure OpenAI."""
    prompt = """You are a professional editor. Analyze the following text for style issues.
    Return a JSON object with a "suggestions" array, where each object contains:
    - "type": either "passive_voice", "weak_word", "redundancy", or "tone"
    - "message": detailed explanation of the style issue
    - "text": the problematic text
    - "improvement": suggested improvement
    Focus on:
    - Passive voice usage
    - Weak or unnecessary words
    - Redundant expressions
    - Inconsistent tone
    Return an empty array if no style issues are found."""
    
    return _call_azure_openai(prompt, text).get("suggestions", [])