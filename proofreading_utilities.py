import os
import json
import requests
import time
import logging

def _call_azure_openai(prompt, content):
    """Helper function to make Azure OpenAI API calls"""
    endpoint = os.environ["AZURE_OPENAI_ENDPOINT"]
    key = os.environ["AZURE_OPENAI_KEY"]
    model = os.environ.get("AZURE_OPENAI_MODEL", "gpt-4")
    max_retries = 5
    retry_delay = 5
    
    headers = {
        "Content-Type": "application/json",
        "api-key": key
    }
    
    data = {
        "model": model,
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
        "max_tokens": 2000
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.post(endpoint, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()
            return json.loads(result['choices'][0]['message']['content'])
        except requests.exceptions.RequestException as e:
            if 'exceeded token rate' in str(e).lower() or response.status_code == 429:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                    continue
            logging.error(f"Error calling Azure OpenAI: {str(e)}")
            raise
        except Exception as e:
            logging.error(f"Error processing Azure OpenAI response: {str(e)}")
            raise

def check_spelling(text: str) -> list:
    """Check text for spelling errors using Azure OpenAI."""
    prompt = """You are a professional proofreader. Analyze the following text for spelling errors.
    Return only a JSON array of objects, where each object has:
    - 'error': the misspelled word
    - 'suggestion': the correct spelling
    - 'context': the sentence or phrase containing the error
    If no errors are found, return an empty array."""
    
    try:
        result = _call_azure_openai(prompt, text)
        return result.get('suggestions', [])
    except Exception as e:
        logging.error(f"Error in check_spelling: {str(e)}")
        return []

def check_grammar(text: str) -> list:
    """Check text for grammar errors using Azure OpenAI."""
    prompt = """You are a professional proofreader. Analyze the following text for grammar errors.
    Return only a JSON array of objects, where each object has:
    - 'error': the grammatical error
    - 'suggestion': the correct grammar
    - 'context': the sentence or phrase containing the error
    - 'explanation': brief explanation of the grammar rule
    If no errors are found, return an empty array."""
    
    try:
        result = _call_azure_openai(prompt, text)
        return result.get('suggestions', [])
    except Exception as e:
        logging.error(f"Error in check_grammar: {str(e)}")
        return []

def check_clarity(text: str) -> list:
    """Check text for clarity issues using Azure OpenAI."""
    prompt = """You are a professional editor. Analyze the following text for clarity and readability issues.
    Return only a JSON array of objects, where each object has:
    - 'issue': description of the clarity issue
    - 'suggestion': recommended improvement
    - 'context': the unclear passage
    - 'impact': how the issue affects readability
    If no issues are found, return an empty array."""
    
    try:
        result = _call_azure_openai(prompt, text)
        return result.get('suggestions', [])
    except Exception as e:
        logging.error(f"Error in check_clarity: {str(e)}")
        return []

def check_style(text: str) -> list:
    """Check text for style consistency using Azure OpenAI."""
    prompt = """You are a professional editor. Analyze the following text for style consistency issues.
    Return only a JSON array of objects, where each object has:
    - 'issue': description of the style issue
    - 'suggestion': recommended improvement
    - 'context': the relevant passage
    - 'category': type of style issue (e.g., 'tone', 'formality', 'consistency')
    If no issues are found, return an empty array."""
    
    try:
        result = _call_azure_openai(prompt, text)
        return result.get('suggestions', [])
    except Exception as e:
        logging.error(f"Error in check_style: {str(e)}")
        return []