from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential
import os
import json

class QASkill:
    def __init__(self):
        # Get Azure AI Search credentials from environment variables
        self.search_endpoint = os.environ.get("AZURE_SEARCH_ENDPOINT")
        self.search_key = os.environ.get("AZURE_SEARCH_ADMIN_KEY")
        self.search_index = os.environ.get("AZURE_SEARCH_INDEX")
        
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
        Answer a question using RAG with Azure AI Search.
        
        Args:
            query: The question to answer
            document_id: Optional document ID to restrict the search to
            
        Returns:
            The answer to the question
        """
        if not self.search_client:
            return "Error: Azure AI Search client not initialized."
        
        try:
            # Prepare search filters if document_id is provided
            filter_expr = f"document_id eq '{document_id}'" if document_id else None
            
            # Perform a semantic search
            results = self.search_client.search(
                search_text=query,
                filter=filter_expr,
                query_type="semantic",
                semantic_configuration_name="default",
                query_caption="extractive",
                query_answer="extractive",
                top=5
            )
            
            # Collect the results
            search_results = []
            for result in results:
                search_results.append({
                    "content": result["content"],
                    "document_id": result.get("document_id", ""),
                    "page_number": result.get("page_number", 0),
                    "score": result["@search.score"],
                    "captions": result.get("@search.captions", []),
                    "answers": result.get("@search.answers", [])
                })
            
            # Format the results
            if len(search_results) > 0:
                # If there's a semantic answer, return it
                if search_results[0].get("answers") and len(search_results[0]["answers"]) > 0:
                    return search_results[0]["answers"][0]["text"]
                
                # Otherwise, return the first result's content
                return search_results[0]["content"]
            else:
                return "I couldn't find an answer to that question."
                
        except Exception as e:
            return f"Error performing search: {str(e)}"
