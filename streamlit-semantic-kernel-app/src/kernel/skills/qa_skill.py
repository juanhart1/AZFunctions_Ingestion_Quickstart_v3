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
        filter_expr = f"document_id eq '{document_id}'" if document_id else None
        
        # Perform a semantic search if available, fall back to vector search
        try:
            results = self.search_client.search(
                search_text=query,
                filter=filter_expr,
                query_type="semantic",
                semantic_configuration_name="default",
                query_caption="extractive",
                query_answer="extractive",
                top=5
            )
        except Exception as e:
            # Fall back to regular search if semantic search is not available
            results = self.search_client.search(
                search_text=query,
                filter=filter_expr,
                top=5
            )
        
        # Collect the results
        search_results = []
        for result in results:
            search_results.append({
                "content": result.get("content", ""),
                "document_id": result.get("document_id", ""),
                "page_number": result.get("page_number", 0),
                "score": result["@search.score"],
                "captions": result.get("@search.captions", []),
                "answers": result.get("@search.answers", [])
            })
        
        return search_results

    def _generate_answer(self, query: str, documents: List[Dict[str, Any]]) -> str:
        """
        Generate an answer using Azure OpenAI based on retrieved documents.
        """
        if not self.aoai_endpoint or not self.aoai_key or not self.aoai_deployment:
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
