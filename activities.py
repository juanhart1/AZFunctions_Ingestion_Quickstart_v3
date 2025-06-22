import azure.functions as func
import logging
import json
import os
import hashlib
import asyncio
import concurrent.futures
from datetime import datetime
from azure.storage.blob import BlobServiceClient
from aoai_utilities import generate_hierarchical_summary
from proofreading_utilities import check_spelling, check_grammar, check_clarity, check_style

# Create a thread pool executor for running blocking functions
thread_pool = concurrent.futures.ThreadPoolExecutor(max_workers=8)

async def run_in_threadpool(func, *args, **kwargs):
    """Run a blocking function in a thread pool to avoid blocking the event loop."""
    return await asyncio.get_event_loop().run_in_executor(
        thread_pool, 
        lambda: func(*args, **kwargs)
    )

# Async wrappers for proofreading utility functions
async def async_check_spelling(text):
    return await run_in_threadpool(check_spelling, text)

async def async_check_grammar(text):
    return await run_in_threadpool(check_grammar, text)

async def async_check_clarity(text):
    return await run_in_threadpool(check_clarity, text)

async def async_check_style(text):
    return await run_in_threadpool(check_style, text)

async def generate_document_summary(activitypayload: str) -> str:
    """
    Generate a hierarchical summary for a document and save it in a summary container.
    
    Args:
        activitypayload (str): JSON string containing:
            - doc_intel_formatted_results_container: container name with document intelligence results
            - summary_container: container name for storing summaries
            - file: name of the file to summarize
            
    Returns:
        str: Name of the generated summary file
    """
    try:
        # Parse input data
        input_data = json.loads(activitypayload)
        doc_intel_formatted_results_container = input_data['doc_intel_formatted_results_container']
        summary_container = input_data['summary_container']
        file_name = input_data['file']
        
        # Initialize blob service client
        blob_service_client = BlobServiceClient.from_connection_string(os.environ["STORAGE_CONN_STR"])
        
        # Ensure summary container exists
        summary_container_client = blob_service_client.get_container_client(summary_container)
        if not summary_container_client.exists():
            summary_container_client.create_container()
        
        # Get the source document blob
        source_container_client = blob_service_client.get_container_client(doc_intel_formatted_results_container)
        source_blob_client = source_container_client.get_blob_client(file_name)
        
        # Download and read the source content
        source_content = json.loads(source_blob_client.download_blob().readall().decode())
        
        # Validate content field exists
        if 'content' not in source_content or not source_content['content']:
            logging.warning(f"Empty or missing content in source file {file_name}")
            # Create a placeholder summary
            summary = {
                "executive_summary": "No content available for summarization.",
                "detailed_summary": "The source document did not contain any content to summarize.",
                "key_topics": ["No content"],
                "takeaways": ["No content available"]
            }
        else:
            try:
                # Generate hierarchical summary using 'content' instead of 'text'
                logging.info(f"Generating summary for {file_name} with content length: {len(source_content['content'])}")
                summary = generate_hierarchical_summary(source_content['content'])
                
                # Validate the summary has all expected fields
                expected_fields = ["executive_summary", "detailed_summary", "key_topics", "takeaways"]
                missing_fields = [field for field in expected_fields if field not in summary]
                
                if missing_fields:
                    logging.warning(f"Summary is missing expected fields: {missing_fields}")
                    # Add placeholder values for missing fields
                    for field in missing_fields:
                        if field in ["executive_summary", "detailed_summary"]:
                            summary[field] = "Summary generation was incomplete."
                        else:  # key_topics and takeaways are lists
                            summary[field] = ["Summary generation was incomplete"]
                
                logging.info(f"Successfully generated summary for {file_name}")
            except Exception as e:
                logging.error(f"Error generating summary for {file_name}: {str(e)}")
                # Return a fallback summary
                summary = {
                    "executive_summary": "Summary generation encountered an error.",
                    "detailed_summary": f"We were unable to generate a summary due to: {str(e)}",
                    "key_topics": ["Error during processing"],
                    "takeaways": ["Please review the original document"]
                }
        
        # Create summary record with metadata
        summary_record = {
            'id': source_content.get('id', hashlib.sha256(file_name.encode()).hexdigest()),
            'sourcefile': source_content.get('sourcefile', file_name),
            'sourcepage': source_content.get('sourcepage', ''),
            'summary': summary,
            'generated_date': datetime.now().isoformat()
        }
        
        # Create summary file name
        summary_file_name = file_name.replace('.json', '_summary.json')
        
        # Upload the summary
        summary_blob = summary_container_client.get_blob_client(summary_file_name)
        summary_blob.upload_blob(json.dumps(summary_record), overwrite=True)
        
        return summary_file_name
        
    except Exception as e:
        logging.error(f"Error in generate_document_summary: {str(e)}")
        raise

async def generate_page_proofread(activitypayload: str) -> str:
    """Generate proofreading results for a page and save them in a proofreading container."""
    try:
        # Validate input
        if not activitypayload:
            raise ValueError("Activity payload cannot be empty")
            
        input_data = json.loads(activitypayload)
        
        required_fields = ['doc_intel_formatted_results_container', 'proofreading_container', 'file']
        missing_fields = [field for field in required_fields if field not in input_data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        doc_intel_formatted_results_container = input_data['doc_intel_formatted_results_container']
        proofreading_container = input_data['proofreading_container']
        file_name = input_data['file']
        
        # Initialize blob service client
        try:
            blob_service_client = BlobServiceClient.from_connection_string(os.environ["STORAGE_CONN_STR"])
        except KeyError:
            raise EnvironmentError("STORAGE_CONN_STR environment variable not set")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize blob service client: {str(e)}")
        
        # Ensure proofreading container exists
        try:
            proofread_container_client = blob_service_client.get_container_client(proofreading_container)
            if not proofread_container_client.exists():
                proofread_container_client.create_container()
        except Exception as e:
            raise RuntimeError(f"Failed to initialize or create proofreading container: {str(e)}")
        
        # Get the source document blob
        try:
            source_container_client = blob_service_client.get_container_client(doc_intel_formatted_results_container)
            source_blob_client = source_container_client.get_blob_client(file_name)
            source_content = json.loads(source_blob_client.download_blob().readall().decode())
        except Exception as e:
            raise RuntimeError(f"Failed to read source document {file_name}: {str(e)}")
            
        # Validate source content
        if not isinstance(source_content, dict) or 'content' not in source_content:
            raise ValueError(f"Invalid source content format in {file_name}")
            
        # Validate and prepare content
        content = source_content.get('content', '')
        if not content:
            logging.warning(f"Empty or missing content in source file {file_name}")
            content = ""
        elif not isinstance(content, str):
            logging.warning(f"Non-string content in source file {file_name}, converting to string")
            content = str(content)
            
        logging.info(f"Starting proofreading analysis for {file_name} (content length: {len(content)})")
        
        # Generate proofreading results with retries
        max_retries = 3
        retry_delay = 1  # seconds
        last_error = None
        proofread_results = {'spelling': [], 'grammar': [], 'clarity': [], 'style': []}
        
        for attempt in range(max_retries):
            try:
                # Define check functions to run in parallel
                check_tasks = {
                    'spelling': async_check_spelling(content),
                    'grammar': async_check_grammar(content),
                    'clarity': async_check_clarity(content),
                    'style': async_check_style(content)
                }
                
                # Execute all checks in parallel using asyncio.gather
                logging.info(f"Running all proofread checks in parallel (attempt {attempt + 1}/{max_retries})")
                results = await asyncio.gather(
                    *check_tasks.values(),
                    return_exceptions=True  # This ensures one failed check doesn't cancel the others
                )
                
                # Process results for each check
                for (check_type, _), result in zip(check_tasks.items(), results):
                    # If the check succeeded, store the results
                    if not isinstance(result, Exception):
                        proofread_results[check_type] = result
                        logging.info(f"Completed {check_type} check, found {len(result)} issues")
                    # If the check failed, log the error and leave empty results
                    else:
                        logging.error(f"Error in {check_type} check: {str(result)}", exc_info=True)
                        proofread_results[check_type] = []
                
                # If we got here, we have at least partial results
                if any(len(results) > 0 for results in proofread_results.values()):
                    logging.info("Successfully generated some proofreading results")
                    break
                else:
                    logging.warning("No issues found in any category, this might indicate a problem")
                    
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logging.warning(f"Retry {attempt + 1} for proofread generation: {str(e)}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"Failed to generate proofread results after {max_retries} attempts: {str(last_error)}")
        
        # Create proofread results record
        proofread_record = {
            'id': source_content.get('id', hashlib.sha256(file_name.encode()).hexdigest()),
            'sourcefile': source_content.get('sourcefile', file_name),
            'sourcepage': source_content.get('sourcepage', ''),
            'results': proofread_results,
            'generated_date': datetime.now().isoformat()
        }
        
        # Create proofread file name
        proofread_file_name = file_name.replace('.json', '_proofread.json')
        
        # Upload the proofread results
        try:
            proofread_blob = proofread_container_client.get_blob_client(proofread_file_name)
            proofread_blob.upload_blob(json.dumps(proofread_record), overwrite=True)
        except Exception as e:
            raise RuntimeError(f"Failed to upload proofread results for {file_name}: {str(e)}")
        
        logging.info(f"Successfully generated and uploaded proofread results for {file_name}")
        return proofread_file_name
        
    except json.JSONDecodeError as je:
        error_msg = f"Invalid JSON in activity payload or document content: {str(je)}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    except ValueError as ve:
        logging.error(str(ve))
        raise
    except Exception as e:
        logging.error(f"Error in generate_page_proofread: {str(e)}")
        raise

async def generate_document_proofread(activitypayload: str) -> str:
    """Generate document-level proofreading results by aggregating page results."""
    try:
        # Validate input
        if not activitypayload:
            raise ValueError("Activity payload cannot be empty")
            
        data = json.loads(activitypayload)
        
        required_fields = ['source_container', 'proofreading_container', 'parent_file']
        missing_fields = [field for field in required_fields if field not in data]
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
            
        source_container = data["source_container"]
        proofreading_container = data["proofreading_container"]
        parent_file = data["parent_file"]
        
        # Generate filename for document-level proofread
        doc_proofread_filename = f"{os.path.splitext(parent_file)[0]}_document_proofread.json"
        
        # Initialize blob service client
        try:
            blob_service_client = BlobServiceClient.from_connection_string(os.environ["STORAGE_CONN_STR"])
        except KeyError:
            raise EnvironmentError("STORAGE_CONN_STR environment variable not set")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize blob service client: {str(e)}")
        
        # Get proofreading container
        try:
            proofread_container_client = blob_service_client.get_container_client(proofreading_container)
            if not proofread_container_client.exists():
                raise ValueError(f"Proofreading container {proofreading_container} does not exist")
        except Exception as e:
            raise RuntimeError(f"Failed to access proofreading container: {str(e)}")
        
        # Collect all page proofreads
        page_proofreads = []
        base_name = os.path.splitext(parent_file)[0]
        try:
            for blob in proofread_container_client.list_blobs(name_starts_with=base_name):
                if "_document_proofread" not in blob.name:  # Skip document proofread if it exists
                    blob_client = proofread_container_client.get_blob_client(blob.name)
                    proofread_data = json.loads(blob_client.download_blob().readall().decode())
                    if 'results' not in proofread_data:
                        logging.warning(f"Missing results in proofread data for {blob.name}")
                        continue
                    page_proofreads.append(proofread_data['results'])
        except Exception as e:
            raise RuntimeError(f"Failed to collect page proofreads: {str(e)}")
            
        if not page_proofreads:
            raise ValueError(f"No valid page proofread results found for {parent_file}")
        
        # Aggregate all proofreading results
        document_proofread = {
            'spelling': [],
            'grammar': [],
            'clarity': [],
            'style': []
        }
        
        # Combine all suggestions from all pages with deduplication
        seen_suggestions = {category: set() for category in document_proofread.keys()}
        for page_result in page_proofreads:
            for category in document_proofread.keys():
                if category not in page_result:
                    continue
                for suggestion in page_result[category]:
                    # Create a hash of the suggestion for deduplication
                    suggestion_str = json.dumps(suggestion, sort_keys=True)
                    if suggestion_str not in seen_suggestions[category]:
                        document_proofread[category].append(suggestion)
                        seen_suggestions[category].add(suggestion_str)
        
        # Create document-level proofread record
        proofread_record = {
            'id': hashlib.sha256(parent_file.encode()).hexdigest(),
            'sourcefile': parent_file,
            'proofread_type': 'document',
            'results': document_proofread,
            'page_count': len(page_proofreads),
            'generated_date': datetime.now().isoformat()
        }
        
        # Upload document proofread with retry
        max_retries = 3
        retry_delay = 1  # seconds
        last_error = None
        
        for attempt in range(max_retries):
            try:
                doc_proofread_blob = proofread_container_client.get_blob_client(doc_proofread_filename)
                doc_proofread_blob.upload_blob(json.dumps(proofread_record), overwrite=True)
                break
            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logging.warning(f"Retry {attempt + 1} for document proofread upload: {str(e)}")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                else:
                    raise RuntimeError(f"Failed to upload document proofread after {max_retries} attempts: {str(last_error)}")
        
        logging.info(f"Successfully generated and uploaded document-level proofread for {parent_file}")
        return doc_proofread_filename
        
    except json.JSONDecodeError as je:
        error_msg = f"Invalid JSON in activity payload or proofread data: {str(je)}"
        logging.error(error_msg)
        raise ValueError(error_msg)
    except ValueError as ve:
        logging.error(str(ve))
        raise
    except Exception as e:
        logging.error(f"Error in generate_document_proofread: {str(e)}")
        raise