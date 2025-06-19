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
from utils.helpers import display_file_selector, display_result, display_file_uploader

# Load environment variables
load_dotenv()

# Initialize session state for persistent state between reruns
if 'functionality' not in st.session_state:
    st.session_state['functionality'] = "Document Processing"
if 'document_id' not in st.session_state:
    st.session_state['document_id'] = None

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
- Upload new PDF documents to Azure Storage
""")

# Initialize Semantic Kernel via our adapter
kernel_adapter = load_semantic_kernel()

# Initialize skills
qa_skill = QASkill()
summarization_skill = SummarizationSkill()
proofreading_skill = ProofreadingSkill()
router_skill = LLMRouterSkill(kernel_adapter)

# Create sidebar with functionality options
with st.sidebar:
    st.header("Select Functionality")
    functionality = st.radio(
        "What would you like to do?",
        options=["Document Processing", "Upload Document"],
        index=0,
        key="functionality"
    )
    
    if functionality == "Document Processing":
        st.subheader("Document Selection")
        # Display file selector for all document types
        document_id = display_file_selector(
            container_name=os.environ.get("DOCUMENTS_CONTAINER", "documents"),
            connection_string_var="AZURE_STORAGE_CONNECTION_STRING"
        )
        # Store the selected document ID in session state
        if document_id:
            st.session_state['document_id'] = document_id
        elif 'document_id' in st.session_state:
            document_id = st.session_state['document_id']
    else:
        document_id = None

# Main content area
if functionality == "Document Processing":
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
elif functionality == "Upload Document":
    st.header("Upload Document")
    
    # Add tabs for different document types
    upload_tab, _, _, _ = st.tabs(["General Documents", "Q&A Documents", "Summarization Documents", "Proofreading Documents"])
    
    with upload_tab:
        st.subheader("Upload a document to Azure Storage")
        
        # Display the file uploader
        upload_success, document_id = display_file_uploader(
            container_name=os.environ.get("DOCUMENTS_CONTAINER", "documents"),
            connection_string_var="AZURE_STORAGE_CONNECTION_STRING",
            key="general_uploader"
        )
        
        if upload_success:
            # Display the document ID and instructions
            st.info(f"""
            Your document has been uploaded with ID: **{document_id}**
            
            You can now select this document in the file selector when using Document Processing.
            """)
            
            # Add a button to navigate back to document processing
            if st.button("Start Processing This Document"):
                # Use st.session_state to set the values for the next rerun
                st.session_state['functionality'] = "Document Processing"
                st.session_state['document_id'] = document_id
                st.rerun()

# Footer
st.markdown("---")
st.markdown("Powered by Semantic Kernel and Azure AI")
