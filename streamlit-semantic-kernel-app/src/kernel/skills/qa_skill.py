from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os
import json
import requests
from typing import List, Dict, Any

class QASkill:
    def __init__(self):
        # Get Azure AI Search credentials from environment variables
        self.search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY")
        self.search_index = os.environ.get("AZURE_SEARCH_INDEX")
        
        # Get Azure OpenAI credentials
        self.aoai_endpoint = os.environ.get("AOAI_ENDPOINT")
        self.aoai_key = os.environ.get("AOAI_KEY")
        self.aoai_deployment = os.environ.get("AOAI_DEPLOYMENT")
        
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
        filter_expr = f"sourcefileref eq '{document_id}'" if document_id else None
        
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
                
            results = self.search_client.search(
                search_text=search_text,
                filter=filter_expr,
                top=5
            )
            
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
                
                search_results.append({
                    "content": result.get(content_field, ""),
                    "document_id": result.get("sourcefileref", result.get("id", "")),
                    "page_number": result.get("page_number", 0),
                    "score": result["@search.score"],
                    "captions": result.get("@search.captions", []),
                    "answers": result.get("@search.answers", [])
                })
            
            # Add more debugging
            print(f"DEBUG: Search returned {len(search_results)} results")
            if len(search_results) > 0:
                print(f"DEBUG: First result score: {search_results[0]['score']}")
                print(f"DEBUG: First result content starts with: {search_results[0]['content'][:100] if search_results[0]['content'] else 'No content'}")
            
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
                return documents[0]["answers"][0]["text"]
            elif documents:
                return documents[0]["content"]
            return "No answer found."
        
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
            url = f"{self.aoai_endpoint}/openai/deployments/{self.aoai_deployment}/chat/completions?api-version=2023-05-15"
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
            if documents[0].get("answers") and len(documents[0]["answers"]) > 0:
                return f"Error generating answer: {str(e)}\n\nHere's the most relevant information I found:\n\n{documents[0]['answers'][0]['text']}"
            else:
                return f"Error generating answer: {str(e)}\n\nHere's the most relevant information I found:\n\n{documents[0]['content']}"
