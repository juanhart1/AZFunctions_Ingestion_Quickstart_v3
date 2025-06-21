from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents import SearchClient
from azure.search.documents.indexes.models import (
    SearchFieldDataType,
    SearchIndex,
    SimpleField,
    SearchableField,
    SearchField,
    VectorSearch,
    SearchField
)
import os
from datetime import datetime
import requests
import json

import logging, sys
logging.basicConfig(stream=sys.stdout, level="DEBUG")
logging.getLogger("azure").setLevel("DEBUG")

API_VER = "2024-03-01-preview"
    
def get_current_index(index_name_or_stem):
    """
    Retrieves an Azure AI search index and its fields. Can handle both:
    1. A full index name
    2. An index stem name, in which case it returns the most recent timestamped version

    Args:
    index_name_or_stem (str): Either a full index name or the stem of an index name
    """
    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']
        
    # Connect to Azure Cognitive Search resource using the provided key and endpoint
    credential = AzureKeyCredential(search_key)
    client = SearchIndexClient(
        api_version=API_VER,
        credential=credential,
        endpoint=search_endpoint, 
    )
    
    # First try to get the index directly - it might be a full index name
    try:
        index = client.get_index(index_name_or_stem)
        return index_name_or_stem, [f.name for f in index.fields]
    except Exception as e:
        # If direct lookup fails, treat it as a stem and look for timestamped versions
        print(f"Index {index_name_or_stem} not found directly, searching for timestamped versions...")
    
    # List all indexes in the search service
    indexes = client.list_index_names()
    
    # Find all indexes starting with the given stem name
    matching_indexes = [i for i in indexes if i.startswith(index_name_or_stem)]
    print(f"Found matching indexes: {matching_indexes}")

    if not matching_indexes:
        raise Exception(f"No index found matching name or stem: {index_name_or_stem}")

    # Parse the timestamp from each index name and store in a dictionary
    timestamp_to_index_dict = {}
    for index_name in matching_indexes:
        try:
            parts = index_name.split('-')
            timestamp = parts[-1]
            parsed_timestamp = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
            timestamp_to_index_dict[parsed_timestamp] = index_name
        except ValueError:
            # If we can't parse the timestamp, just continue
            continue

    if not timestamp_to_index_dict:
        # If we found indexes but none had valid timestamps, just use the first one
        index_name = matching_indexes[0]
    else:
        # Sort timestamps from oldest to newest and get the newest
        timestamps = sorted(timestamp_to_index_dict.keys())
        index_name = timestamp_to_index_dict[timestamps[-1]]
    
    # Get the index details
    index = client.get_index(index_name)
    fields = [f.name for f in index.fields]

    return index_name, fields

    # Get the index details
    index = client.get_index(newest_index)
    fields = [f.name for f in index.fields]

    return newest_index, fields

def get_index_fields(index_name):
    """
    Retrieves existing Azure AI search indexes (based on a provided prefix) and returns the 
    most recently created index to the user by name.

    Args:
    index_name (str): The name of the index to retrieve matching fields for.
    """
    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']
    
    # Connect to Azure Cognitive Search resource using the provided key and endpoint
    credential = AzureKeyCredential(search_key)
    client = SearchIndexClient(endpoint=search_endpoint, credential=credential, api_version=API_VER)
    

    # Get the index details
    index = client.get_index(index_name)
    fields = [f.name for f in index.fields]

    return fields


def delete_indexes(index_stem_name, age_in_minutes=60):
    """
    Retrieves indexes (by matching stem name) and deletes those which are older than
    the user-provided age_in_minutes argument. Used for index cleanup operations.

    Args:
    index_stem_name (str): The stem of the index name to filter out relevant indexes.
    age_in_minutes (int): The age (in minutes) at which indexes should be deleted.
    """
    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']
    
    # Connect to Azure Cognitive Search resource using the provided key and endpoint
    credential = AzureKeyCredential(search_key)
    client = SearchIndexClient(endpoint=search_endpoint, credential=credential, api_version=API_VER,)
    
    # List all indexes in the search service
    indexes = client.list_index_names()

    # Find all indexes starting with the given stem name
    matching_indexes = [i for i in indexes if i.startswith(index_stem_name)]
    print(matching_indexes)

    # Parse the timestamp from each index name and store in a dictionary
    indexes_to_delete = []
    for index_name in matching_indexes:
        parts = index_name.split('-')
        timestamp = parts[-1]
        parsed_timestamp = datetime.strptime(timestamp, "%Y%m%d%H%M%S")
        timedelta = datetime.now() - parsed_timestamp
        if timedelta.total_seconds() > age_in_minutes * 60:
            indexes_to_delete.append(index_name)

    # Delete the indexes that are older than the specified age
    for index_name in indexes_to_delete:
        client.delete_index(index_name)

    return indexes_to_delete
   

def insert_documents_vector(documents, index_name):
    """
    Inserts a document vector into the specified search index on Azure Cognitive Search.

    Args:
    documents (list): The list of documents to insert.
    index_name (str): The name of the search index.
    """
    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']

    # Create a SearchClient object
    credential = AzureKeyCredential(search_key)
    client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)

    # Upload the document to the search index
    result = client.upload_documents(documents=documents)

    return result

def delete_documents_vector(documents, index_name):
    """
    Inserts a document vector into the specified search index on Azure Cognitive Search.

    Args:
    documents (list): The list of documents to insert.
    index_name (str): The name of the search index.
    """
    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']

    # Create a SearchClient object
    credential = AzureKeyCredential(search_key)
    client = SearchClient(endpoint=search_endpoint, index_name=index_name, credential=credential)

    deleted_records = []
    retrieved_doc = None
    for document in documents:
        try:
            retrieved_doc = client.get_document(document['id'])
        except Exception as e:
            pass
        if retrieved_doc:
            client.delete_documents(retrieved_doc)
            try:
                del retrieved_doc['embeddings']
                deleted_records.append(retrieved_doc)
            except Exception as e:
                print(e)

    return deleted_records


def create_vector_index(stem_name, user_fields, omit_timestamp=False, dimensions=1536):
    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']

    # Get the current time and format it as a string
    now =  datetime.now()
    timestamp  = datetime.strftime(now, "%Y%m%d%H%M%S")

    # Create the index name by appending the timestamp to the stem name
    index_name  = f'{stem_name}-{timestamp}'

    if omit_timestamp:
        index_name = stem_name

    # Create a SearchIndexClient object
    credential = AzureKeyCredential(search_key)
    client = SearchIndexClient(endpoint=search_endpoint, credential=credential, api_version=API_VER,)

    # Define the fields for the index
    fields = [SimpleField(name="id", type=SearchFieldDataType.String, key=True), SimpleField(name="sourcefileref", type=SearchFieldDataType.String,searchable=False, filterable=True)]
    
    # Add user-defined fields to the index
    for field, field_type in user_fields.items():
        if field_type == 'string':
            fields.append(SearchableField(name=field, type=SearchFieldDataType.String, searchable=True,  filterable=True))
        elif field_type == 'int':
            fields.append(SimpleField(name=field, type=SearchFieldDataType.Int32, searchable=False, filterable=True))
        elif field_type == 'datetime':
            fields.append(SimpleField(name=field, type=SearchFieldDataType.DateTimeOffset, searchable=False, filterable=True, sortable=True))
        elif field_type == 'double':
            fields.append(SimpleField(name=field, type=SearchFieldDataType.Double, searchable=False, filterable=True))
        elif field_type == 'bool':
            fields.append(SimpleField(name=field, type=SearchFieldDataType.Boolean, searchable=False, filterable=True))

    if dimensions!= None:
        vector_dimensions = dimensions
    else:
        vector_dimensions = os.environ.get('AOAI_EMBEDDINGS_DIMENSIONS')

    # Define vector profile and algorithm names
    vector_algorithm_name = "vector-config"
    vector_profile_name = "vector-profile"

    # Import necessary models for vector search
    from azure.search.documents.indexes.models import (
        HnswVectorSearchAlgorithmConfiguration,
        VectorSearch
    )

    # Create vector search configuration for hybrid search with semantic reranking
    vector_search = VectorSearch(
        algorithm_configurations=[
            HnswVectorSearchAlgorithmConfiguration(
                name=vector_algorithm_name,
                kind="hnsw",
                parameters={
                    "m": 4,
                    "efConstruction": 400,
                    "efSearch": 500,
                    "metric": "cosine"
                }
            )
        ],
        profiles=[
            {
                "name": vector_profile_name,
                "algorithm": vector_algorithm_name,
                "vectorizer": None
            }
        ],
        semantic_search={
            "configurations": [
                {
                    "name": "semantic-config",
                    "prioritized_fields": {
                        "title_field": None,
                        "content_fields": [
                            {"field_name": "content"}
                        ],
                        "keyword_fields": []
                    }
                }
            ]
        }
    )

    # Add vector embeddings field with correct Collection type and dimensions
    vector_field = SearchField(
        name="embeddings",
        type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
        vector_search_dimensions=dimensions,
        vector_search_profile_name=vector_profile_name,
        searchable=True,
        filterable=False,
        sortable=False,
        facetable=False
    )
    fields.append(vector_field)

    # Create the search index with the specified fields
    index = SearchIndex(
        name=index_name,
        fields=fields,
        vector_search=vector_search
    )
    
    try:
        # Add detailed logging to help debug
        logging.info(f"Creating index '{index_name}' with {len(fields)} fields and vector search configuration")
        logging.info(f"Vector search config: {vector_search.semantic_search}")
        result = client.create_or_update_index(index)
        logging.info(f"Successfully created index: {result.name}")
        return result.name
    except Exception as e:
        # Capture and log the detailed error
        error_detail = str(e)
        logging.error(f"Error creating index: {error_detail}")
        
        # Try to determine if it's a semantic search capability issue
        if "semantic" in error_detail.lower() and ("not enabled" in error_detail.lower() or "not supported" in error_detail.lower()):
            logging.warning("It appears semantic search is not enabled on your search service tier.")
            logging.warning("Attempting to create index without semantic search...")
            
            # Try again without semantic search if that's the issue
            try:
                # Remove semantic_search from vector_search
                vector_search.semantic_search = None
                index.vector_search = vector_search
                result = client.create_or_update_index(index)
                logging.info(f"Successfully created index without semantic search: {result.name}")
                return result.name
            except Exception as fallback_error:
                logging.error(f"Error creating index without semantic search: {str(fallback_error)}")
                raise Exception(f"Failed to create index with or without semantic search: {error_detail}")
        else:
            # If it's not related to semantic search, re-raise the original error
            raise


def create_update_index_alias(alias_name, target_index):
    """
    Creates or updates an alias for a given Azure Cognitive Search index.

    Args:
    search_service_name (str): The name of the Azure Cognitive Search service.
    search_key (str): The admin key of the Azure Cognitive Search service.
    alias_name (str): The name of the alias to create or update.
    target_index (str): The name of the index that the alias should point to.
    """

    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']

    # Construct the URI for alias creation
    uri = f'https://{search_service_name}.search.windows.net/aliases?api-version=2023-07-01-Preview'
    headers = {'Content-Type': 'application/json', 'api-key': search_key}
    payload = {
        "name": alias_name,
        "indexes": [target_index]
    }
    
    try:
        # Attempt to create the alias
        response = requests.post(uri, headers=headers, data=json.dumps(payload))
        # If alias creation fails with a 400 error, update the existing alias
        if response.status_code == 400:
            uri = f'https://{search_service_name}.search.windows.net/aliases/{alias_name}?api-version=2023-07-01-Preview'
            response = requests.put(uri, headers=headers, data=json.dumps(payload))
    except Exception as e:
        print(e)

def get_ids_from_all_docs(target_index):
    """
    Creates or updates an alias for a given Azure Cognitive Search index.

    Args:
    search_service_name (str): The name of the Azure Cognitive Search service.
    search_key (str): The admin key of the Azure Cognitive Search service.
    alias_name (str): The name of the alias to create or update.
    target_index (str): The name of the index that the alias should point to.
    """

    # Get the search key, endpoint, and service name from environment variables
    search_key = os.environ['SEARCH_KEY']
    search_endpoint = os.environ['SEARCH_ENDPOINT']
    search_service_name = os.environ['SEARCH_SERVICE_NAME']

    # Create a SearchIndexClient object
    credential = AzureKeyCredential(search_key)
    client = SearchClient(endpoint=search_endpoint, index_name=target_index, credential=credential)

    results = client.search(search_text="*", select="id", include_total_count=True, top=1)

    total_records = results.get_count()

    captured_results = []

    while True:
        results =  client.search(search_text='*',  select="id", top=1000, skip=len(captured_results))
        captured_results.extend([result['id'] for result in results])
        if len(captured_results) >= total_records:
            break
    return captured_results

def check_search_service_capabilities():
    """
    Checks the capabilities of the Azure AI Search service to determine
    which features are supported (e.g., semanticSearch).
    
    Returns:
        dict: A dictionary of service capabilities
    """
    try:
        # Get the search key, endpoint, and service name from environment variables
        search_key = os.environ['SEARCH_KEY']
        search_endpoint = os.environ['SEARCH_ENDPOINT']
        search_service_name = os.environ['SEARCH_SERVICE_NAME']
        
        # Construct the URI for service stats
        uri = f'{search_endpoint}/servicestats?api-version={API_VER}'
        headers = {'Content-Type': 'application/json', 'api-key': search_key}
        
        # Make the request
        response = requests.get(uri, headers=headers)
        if response.status_code == 200:
            service_stats = response.json()
            return {
                "service_name": search_service_name,
                "endpoint": search_endpoint,
                "capabilities": service_stats.get("serviceCapabilities", {}),
                "counters": service_stats.get("counters", {})
            }
        else:
            return {
                "error": f"Failed to get service capabilities: {response.status_code}",
                "message": response.text
            }
    except Exception as e:
        return {"error": f"Exception checking service capabilities: {str(e)}"}

def verify_index_creation(index_name):
    """
    Verifies that an index was successfully created and reports any issues.
    
    Args:
        index_name (str): The name of the index to verify
        
    Returns:
        dict: Status information about the index
    """
    try:
        # Get the search key, endpoint, and service name from environment variables
        search_key = os.environ['SEARCH_KEY']
        search_endpoint = os.environ['SEARCH_ENDPOINT']
        
        # Connect to Azure Cognitive Search resource
        credential = AzureKeyCredential(search_key)
        client = SearchIndexClient(
            api_version=API_VER,
            credential=credential,
            endpoint=search_endpoint
        )
        
        # Try to get the index
        try:
            index = client.get_index(index_name)
            fields = [{"name": f.name, "type": str(f.type)} for f in index.fields]
            return {
                "status": "success",
                "index_name": index_name,
                "fields": fields,
                "has_vector_search": hasattr(index, "vector_search") and index.vector_search is not None,
                "has_semantic_search": (hasattr(index, "vector_search") and 
                                       index.vector_search is not None and 
                                       hasattr(index.vector_search, "semantic_search") and 
                                       index.vector_search.semantic_search is not None)
            }
        except Exception as e:
            return {
                "status": "error",
                "index_name": index_name,
                "message": f"Index not found or other error: {str(e)}"
            }
    except Exception as e:
        return {"status": "error", "message": f"Exception verifying index: {str(e)}"}
