from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os
import json
import requests
from typing import List, Dict, Any

class QASkill:
    def __init__(self):
        # Get Azure AI Search credentials from environment variables
        self.search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT") or os.environ.get("SEARCH_ENDPOINT")
        self.search_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY") or os.environ.get("SEARCH_KEY") 
        self.search_index = os.environ.get("AZURE_SEARCH_INDEX") or os.environ.get("SEARCH_INDEX_NAME")
        
        # Get Azure OpenAI credentials
        self.aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT") or os.environ.get("AOAI_ENDPOINT")
        self.aoai_key = os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("AOAI_KEY")
        self.aoai_deployment = os.environ.get("AZURE_OPENAI_COMPLETION_DEPLOYMENT") or os.environ.get("AOAI_GPT_MODEL")
        
        # Initialize search client if credentials are available
        if self.search_endpoint and self.search_key and self.search_index:
            self.search_client = SearchClient(
                endpoint=self.search_endpoint,
                index_name=self.search_index,
                credential=AzureKeyCredential(self.search_key)
            )
        else:
            self.search_client = None
            print("Warning: Azure AI Search credentials not found. QA Skill will not function.")
    
    def answer_question(self, query: str, document_id: str = None) -> str:
        """
        Answer a question using RAG with Azure AI Search and Azure OpenAI.
        
        Args:
            query: The question to answer
            document_id: Optional document ID to restrict the search to
            
        Returns:
            The answer to the question
        """
        if not self.search_client:
            return "Error: Azure AI Search client not initialized."
        
        try:
            # Step 1: Retrieve relevant content from Azure AI Search
            retrieved_docs = self._retrieve_documents(query, document_id)
            
            if not retrieved_docs:
                print(f"DEBUG: No results found for query: '{query}' and document_id: '{document_id}'")
                # Try a more permissive search if we got no results with a filter
                if document_id and query:
                    print(f"DEBUG: Trying without document_id filter")
                    retrieved_docs = self._retrieve_documents(query, None)
                    
                # If still no results, try with just a wildcard search
                if not retrieved_docs:
                    print(f"DEBUG: Trying wildcard search")
                    retrieved_docs = self._retrieve_documents("*", document_id)
            
            if not retrieved_docs:
                return "I couldn't find relevant information to answer that question."
            
            # Step 2: Synthesize an answer using Azure OpenAI
            answer = self._generate_answer(query, retrieved_docs)
            
            return answer
                
        except Exception as e:
            return f"Error answering question: {str(e)}"

    def _retrieve_documents(self, query: str, document_id: str = None) -> List[Dict[str, Any]]:
        """
        Retrieve relevant documents from Azure AI Search.
        """
        # Prepare search filters if document_id is provided
        if document_id:
            # Escape single quotes in document_id by replacing ' with ''
            escaped_document_id = document_id.replace("'", "''")
            filter_expr = f"sourcefile eq '{escaped_document_id}'"
        else:
            filter_expr = None
        
        # Add debugging
        print(f"DEBUG: Searching with query: '{query}' and filter: '{filter_expr}'")
        print(f"DEBUG: Search index: {self.search_index}")
        
        try:
            # First attempt standard search to ensure we get results
            # without relying on semantic search configurations
            
            # For empty or very short queries, use a wildcard search to return all docs
            search_text = query
            if not query or len(query.strip()) < 3:
                search_text = "*"
                print(f"DEBUG: Using wildcard search for short query: '{query}'")
            else:
                # Print out the actual terms being searched
                print(f"DEBUG: Search terms: {[term for term in query.split()]}")
                
            # Try to handle possible name searches better
            if "who is" in query.lower() or "who was" in query.lower():
                print(f"DEBUG: This appears to be a name search: '{query}'")
                # Ensure we don't filter too aggressively
                
            results = self.search_client.search(
                search_text=search_text,
                filter=filter_expr,
                query_type="semantic",  # Change to semantic query type
                semantic_configuration_name="default",  # Use your semantic config name here
                query_caption="extractive",  # Generate captions
                query_answer="extractive",   # Generate answers
                include_total_count=True,
                highlight_fields="content",
                top=5
            )
            
            # Print total count
            print(f"DEBUG: Total matching documents: {results.get_count()}")
            
            # Collect the results
            search_results = []
            for result in results:
                # Debug: print available fields for first result
                if len(search_results) == 0:
                    print("DEBUG: Available fields in search result:")
                    for field_name in result.keys():
                        print(f"  - {field_name}: {type(result[field_name])}")
                
                # Try to find the content field - it might have a different name
                content_field = "content"
                if "content" not in result:
                    # Look for likely content field names
                    possible_content_fields = ["text", "chunk", "document_content", "body", "document_text"]
                    for field in possible_content_fields:
                        if field in result:
                            content_field = field
                            print(f"DEBUG: Using {field} as content field")
                            break
                
                # Get the content and check if it's relevant to the query
                content = result.get(content_field, "")
                
                search_results.append({
                    "content": content,
                    "document_id": result.get("sourcefileref", result.get("id", "")),
                    "page_number": result.get("page_number", 0),
                    "score": result["@search.score"],
                    "reranker_score": result.get("@search.reranker_score"),
                    "captions": result.get("@search.captions", []),
                    "answers": result.get("@search.answers", [])
                })
            
            # Add more debugging
            print(f"DEBUG: Search returned {len(search_results)} results")
            if len(search_results) > 0:
                print(f"DEBUG: First result score: {search_results[0]['score']}")
                if search_results[0].get('reranker_score'):
                    print(f"DEBUG: First result reranker score: {search_results[0]['reranker_score']}")
                print(f"DEBUG: First result content starts with: {search_results[0]['content'][:100] if search_results[0]['content'] else 'No content'}")
                
                # Print semantic captions if available
                if search_results[0].get('captions'):
                    print(f"DEBUG: First result caption: {search_results[0]['captions'][0].text if search_results[0]['captions'] else 'No caption'}")
                
                # Print semantic answers if available
                if search_results[0].get('answers'):
                    print(f"DEBUG: First result answer: {search_results[0]['answers'][0].text if search_results[0]['answers'] else 'No answer'}")
                
                # Check for query term presence in the results
                query_terms = set(query.lower().split())
                # Filter out common words
                stopwords = {"who", "what", "when", "where", "why", "how", "the", "and", "for", "that", "with", "this", "from", "are", "was", "were", "did", "does", "is", "am", "be", "been", "have", "has", "had"}
                query_terms = [term for term in query_terms if term not in stopwords]
                
                # Print the query terms we're looking for
                if query_terms:
                    print(f"DEBUG: Looking for query terms in results: {query_terms}")
                    
                    # Don't filter out results completely - just log if terms aren't found
                    found_relevant = False
                    for result in search_results:
                        # Check if any term is found (case insensitive)
                        found_terms = [term for term in query_terms if term.lower() in result["content"].lower()]
                        if found_terms:
                            found_relevant = True
                            print(f"DEBUG: Found terms in result: {found_terms}")
                            break
                    
                    if not found_relevant and query_terms:
                        print(f"WARNING: No results contain any of the query terms: {query_terms}")
                        print(f"WARNING: This might indicate a relevance issue, but returning results anyway")
                        # No longer returning an empty list - let the LLM decide relevance
                        # We don't want to filter results if Azure Search found them
            
            return search_results
            
        except Exception as e:
            print(f"ERROR performing search: {type(e).__name__} - {str(e)}")
            import traceback
            print(traceback.format_exc())
            return []

    def _generate_answer(self, query: str, documents: List[Dict[str, Any]]) -> str:
        """
        Generate an answer using Azure OpenAI based on retrieved documents.
        """
        print(f"DEBUG: Generating answer for query: '{query}' with {len(documents)} documents")
        
        if not self.aoai_endpoint or not self.aoai_key or not self.aoai_deployment:
            print("DEBUG: No Azure OpenAI configuration found, falling back to document content")
            # If Azure OpenAI is not configured, return the content of the top result
            # Or use the semantic answers if available
            if documents and documents[0].get("answers") and len(documents[0]["answers"]) > 0:
                print("DEBUG: Using semantic answers from search results")
                return f"Here's the answer I found: {documents[0]['answers'][0]['text']}"
            elif documents and documents[0].get("captions") and len(documents[0]["captions"]) > 0:
                print("DEBUG: Using semantic captions from search results")
                return f"Here's what I found in the documents: {documents[0]['captions'][0]['text']}"
            elif documents:
                # No longer doing relevance checking here since it may be too strict
                # Just return the top result from Azure Search - it found something
                return f"Here's what I found in the documents about your query:\n\n{documents[0]['content']}"
            return "I couldn't find any information about that in the documents."
        
        # Prepare the context from retrieved documents
        context = ""
        for i, doc in enumerate(documents, 1):
            context += f"\nDocument {i}:\n{doc['content']}\nSource: {doc['document_id']}"
            if doc.get("page_number"):
                context += f", Page: {doc['page_number']}"
            context += "\n"
        
        # Prepare the prompt for the LLM
        system_message = """You are a helpful AI assistant. Answer the user's question based on the provided document excerpts.
        If the information to answer the question is not contained in the documents, say "I don't have enough information to answer that question."
        Include citations to the source documents where appropriate using the format [Source: document_id, Page: page_number].
        Provide a concise and accurate answer."""
        
        user_message = f"Question: {query}\n\nRelevant documents:\n{context}"
        
        # Call Azure OpenAI API
        try:
            # Determine the correct API version and URL format
            api_version = "2023-05-15"
            
            # Check if aoai_deployment is a full URL or just a model name
            if self.aoai_deployment and "http" in self.aoai_deployment:
                # It's a full URL - extract the model name and use the URL directly
                url_parts = self.aoai_deployment.split("/")
                model_index = url_parts.index("deployments") + 1 if "deployments" in url_parts else -1
                if model_index >= 0 and model_index < len(url_parts):
                    # Use the deployment name from the URL
                    self.aoai_deployment = url_parts[model_index]
                # Use the URL as is but add api-key to headers
                url = f"{self.aoai_endpoint}/openai/deployments/{self.aoai_deployment}/chat/completions?api-version={api_version}"
            else:
                # It's just a model name, construct the URL
                url = f"{self.aoai_endpoint}/openai/deployments/{self.aoai_deployment}/chat/completions?api-version={api_version}"
            
            headers = {
                "Content-Type": "application/json",
                "api-key": self.aoai_key
            }
            payload = {
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ],
                "temperature": 0.3,
                "max_tokens": 800
            }
            
            response = requests.post(url, headers=headers, json=payload)
            response.raise_for_status()
            
            result = response.json()
            answer = result["choices"][0]["message"]["content"]
            
            return answer
        
        except Exception as e:
            # Fall back to returning top result if OpenAI call fails
            print(f"ERROR calling Azure OpenAI: {type(e).__name__} - {str(e)}")
            import traceback
            print(traceback.format_exc())
            
            # Return most relevant document content as fallback
            if documents and documents[0].get("answers") and len(documents[0]["answers"]) > 0:
                return f"Error calling AI model, but I found this in the documents: {documents[0]['answers'][0]['text']}"
            elif documents:
                return f"Error calling AI model, but I found this in the documents: {documents[0]['content']}"
            return "No answer found and there was an error calling the AI model."
