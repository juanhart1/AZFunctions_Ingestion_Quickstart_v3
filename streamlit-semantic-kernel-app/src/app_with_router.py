import streamlit as st
import os
import json
import asyncio
from dotenv import load_dotenv

# Import from our modules
from kernel.config import load_semantic_kernel
from kernel.skills.qa_skill import QASkill
from kernel.skills.summarization_skill import SummarizationSkill
from kernel.skills.proofreading_skill import ProofreadingSkill
from kernel.skills.llm_router_skill import LLMRouterSkill
from utils.helpers import display_file_selector, display_result

# Load environment variables
load_dotenv()

# App configuration
st.set_page_config(
    page_title="Document Processing with Semantic Kernel",
    page_icon="📄",
    layout="wide"
)

# App title and description
st.title("Document Processing with Semantic Kernel")
st.markdown("""
This application uses Azure AI services to process documents. You can:
- Ask questions about documents (RAG with Azure AI Search)
- Get document summaries
- Check documents for grammar and spelling issues
""")

# Initialize Semantic Kernel via our adapter
kernel_adapter = load_semantic_kernel()

# Initialize skills
qa_skill = QASkill()
summarization_skill = SummarizationSkill()
proofreading_skill = ProofreadingSkill()
router_skill = LLMRouterSkill(kernel_adapter)

# Create sidebar with document selector
with st.sidebar:
    st.header("Document Selection")
    # Display file selector for all document types
    document_id = display_file_selector(
        container_name=os.environ.get("DOCUMENTS_CONTAINER", "documents"),
        connection_string_var="AZURE_STORAGE_CONNECTION_STRING"
    )

# Main content area
if document_id:
    # User intent input
    user_input = st.text_input("What would you like to do with this document?", 
                              placeholder="e.g., 'Summarize this document' or 'Are there any spelling errors?'")
    
    if user_input:
        # Use the router to determine the user's intent
        with st.spinner("Processing your request..."):
            # Get the coroutine for the route_intent method
            route_intent_coroutine = router_skill.route_intent(user_input)
            
            # Run the coroutine in an asyncio event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            intent = loop.run_until_complete(route_intent_coroutine)
            loop.close()
            
            # Process the request based on the determined intent
            if intent == "qna":
                # Process as a question
                answer = qa_skill.answer_question(user_input, document_id)
                display_result(answer, "qna")
                
            elif intent == "summarization":
                # Get the summary
                summary = summarization_skill.get_summary(document_id)
                display_result(summary, "summarization")
                
            elif intent == "proofreading":
                # Get the proofreading results
                proofreading_results = proofreading_skill.get_proofread(document_id)
                display_result(proofreading_results, "proofreading")
            
            # Display the detected intent
            st.caption(f"Detected intent: {intent}")
else:
    st.info("Please select a document from the sidebar to get started.")

# Footer
st.markdown("---")
st.markdown("Powered by Semantic Kernel and Azure AI")
