import os
import json
from typing import Optional, Any

class LLMRouterSkill:
    def __init__(self, kernel_adapter=None):
        self.kernel_adapter = kernel_adapter
        
        # Define the prompt for intent classification
        self.intent_prompt = """
        You are an intent classifier for a document processing system.
        Based on the user's query, determine which of the following intents best matches their request:
        
        1. qna: The user wants to ask a question about a document or retrieve specific information.
        2. summarization: The user wants a summary or overview of a document.
        3. proofreading: The user wants to check a document for grammar, spelling, or other issues.
        
        User query: {{$query}}
        
        Respond with only one of the following: "qna", "summarization", or "proofreading".
        """
    
    async def route_intent(self, query: str) -> str:
        """
        Determine the user's intent from a natural language query using an LLM.
        
        Args:
            query: The user's natural language query
            
        Returns:
            The intent: "qna", "summarization", or "proofreading"
        """
        if not self.kernel_adapter or not self.kernel_adapter.initialized:
            # Fall back to rule-based intent classification if no kernel is available
            return self._rule_based_classification(query)
        
        try:
            # Create the intent classification prompt function
            intent_function = self.kernel_adapter.create_semantic_function(
                prompt_template=self.intent_prompt,
                description="Determines user intent from a query"
            )
            
            if not intent_function:
                return self._rule_based_classification(query)
                
            # Execute the function with the user's query
            result = await self.kernel_adapter.invoke_function_async(
                function=intent_function,
                query=query
            )
            
            if not result:
                return self._rule_based_classification(query)
                
            # Get the response text and normalize
            intent = result.result.strip().lower()
            
            # Validate that the intent is one of the expected values
            if intent not in ["qna", "summarization", "proofreading"]:
                # Fall back to rule-based classification if the LLM gives an unexpected response
                return self._rule_based_classification(query)
            
            return intent
            
        except Exception as e:
            print(f"Error in LLM-based intent classification: {str(e)}")
            # Fall back to rule-based intent classification on error
            return self._rule_based_classification(query)
    
    def _rule_based_classification(self, query: str) -> str:
        """
        Simple rule-based fallback for intent classification.
        """
        query = query.lower()
        
        # Simple keyword matching for intent classification
        if any(word in query for word in ["question", "answer", "ask", "query", "search", "find", "look up"]):
            return "qna"
        elif any(word in query for word in ["summarize", "summary", "overview", "brief", "tldr"]):
            return "summarization"
        elif any(word in query for word in ["proofread", "grammar", "spelling", "correct", "edit", "improve", "errors"]):
            return "proofreading"
        else:
            # Default to Q&A if intent is unclear
            return "qna"
