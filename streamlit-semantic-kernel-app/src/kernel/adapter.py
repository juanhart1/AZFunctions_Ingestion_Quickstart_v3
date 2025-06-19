"""
This module provides a simple adapter for the semantic-kernel package.
It abstracts away the direct dependency on semantic-kernel, making it
easier to handle version changes and dependency issues.
"""

import os
from typing import Dict, Any, Optional, List

class KernelAdapter:
    """
    An adapter for the semantic-kernel package.
    This class provides a simplified interface for working with Semantic Kernel
    and abstracts away the direct dependency.
    """
    
    def __init__(self):
        """Initialize the kernel adapter."""
        self.kernel = None
        self.initialized = False
        
        try:
            import semantic_kernel as sk
            self.sk = sk
            self.kernel = sk.Kernel()
            self.initialized = True
        except ImportError as e:
            print(f"Warning: Could not import semantic_kernel: {e}")
            print("The adapter will not have LLM capabilities.")
    
    def add_openai_services(self, 
                          endpoint: str, 
                          api_key: str, 
                          completion_deployment: str, 
                          embedding_deployment: str) -> bool:
        """
        Add Azure OpenAI services to the kernel.
        
        Args:
            endpoint: The Azure OpenAI endpoint
            api_key: The Azure OpenAI API key
            completion_deployment: The deployment name for completions
            embedding_deployment: The deployment name for embeddings
            
        Returns:
            True if successful, False otherwise
        """
        if not self.initialized:
            return False
            
        try:
            # In Semantic Kernel 1.0.0+, the API has changed
            # Add chat completion service
            from semantic_kernel.connectors.ai.open_ai import AzureChatCompletion, AzureTextEmbedding
            
            chat_service = AzureChatCompletion(
                deployment_name=completion_deployment,
                endpoint=endpoint,
                api_key=api_key
            )
            # The current API doesn't use service_id parameter
            self.kernel.add_service(chat_service)
            
            # Add text embedding service
            embedding_service = AzureTextEmbedding(
                deployment_name=embedding_deployment,
                endpoint=endpoint,
                api_key=api_key
            )
            self.kernel.add_service(embedding_service)
            
            return True
        except Exception as e:
            print(f"Error adding OpenAI services: {e}")
            return False
    
    def create_semantic_function(self, prompt_template: str, description: str = ""):
        """
        Create a semantic function from a prompt template.
        
        Args:
            prompt_template: The prompt template
            description: A description of the function
            
        Returns:
            The semantic function, or None if initialization failed
        """
        if not self.initialized:
            return None
            
        try:
            # In Semantic Kernel 1.0.0+, the create_semantic_function API has changed
            from semantic_kernel.functions import KernelFunction
            from semantic_kernel.prompt_template import PromptTemplate
            
            # For Semantic Kernel 1.33.0, the API might be slightly different
            prompt_config = PromptTemplate(
                template=prompt_template
            )
            
            # Create a function with the updated API
            function = self.kernel.create_function_from_prompt(
                prompt=prompt_template,
                description=description
            )
            
            return function
        except Exception as e:
            print(f"Error creating semantic function: {e}")
            return None
    
    def create_new_context(self) -> Optional[Dict[str, Any]]:
        """
        Create a new kernel context.
        
        Returns:
            A new kernel context, or None if initialization failed
        """
        if not self.initialized:
            return None
            
        try:
            # In Semantic Kernel 1.0.0+, contexts are managed differently
            from semantic_kernel import KernelArguments
            return KernelArguments()
        except Exception as e:
            print(f"Error creating kernel context: {e}")
            return {}
    
    async def invoke_function_async(self, function, context=None, **kwargs):
        """
        Invoke a semantic function asynchronously.
        
        Args:
            function: The semantic function to invoke
            context: The kernel context
            **kwargs: Additional arguments to pass to the function
            
        Returns:
            The function result, or None if an error occurred
        """
        if not self.initialized:
            return None
            
        try:
            if context is None:
                context = self.create_new_context()
                
            # Add kwargs to context
            for key, value in kwargs.items():
                context[key] = value
                
            # In Semantic Kernel 1.0.0+, the invoke_async method is replaced
            result = await self.kernel.invoke(function, arguments=context)
            return result
        except Exception as e:
            print(f"Error invoking function: {e}")
            return None

def load_kernel_adapter():
    """
    Initialize and configure the Kernel Adapter with Azure OpenAI.
    
    Returns:
        An initialized KernelAdapter instance
    """
    # Create a new adapter
    adapter = KernelAdapter()
    
    # Get Azure OpenAI credentials from environment variables
    aoai_endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
    aoai_api_key = os.environ.get("AZURE_OPENAI_API_KEY")
    
    # Set up deployment names
    completion_model_deployment = os.environ.get("AZURE_OPENAI_COMPLETION_DEPLOYMENT", "gpt-35-turbo")
    embedding_model_deployment = os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-ada-002")
    
    # Add Azure OpenAI services if credentials are available
    if aoai_endpoint and aoai_api_key:
        adapter.add_openai_services(
            endpoint=aoai_endpoint,
            api_key=aoai_api_key,
            completion_deployment=completion_model_deployment,
            embedding_deployment=embedding_model_deployment
        )
    else:
        print("Warning: Azure OpenAI credentials not found. Adapter will not have AI capabilities.")
    
    return adapter
