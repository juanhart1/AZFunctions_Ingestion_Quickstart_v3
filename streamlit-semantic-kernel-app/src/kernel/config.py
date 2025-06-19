import os
from .adapter import load_kernel_adapter

def load_semantic_kernel():
    """
    Initialize and configure the Semantic Kernel instance with Azure OpenAI
    """
    # Use our adapter to load the kernel
    return load_kernel_adapter()
