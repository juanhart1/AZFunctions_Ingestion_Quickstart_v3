import streamlit as st
import os
import json
from dotenv import load_dotenv

# Import from our modules
from kernel.config import load_semantic_kernel
from kernel.skills.qa_skill import QASkill
from kernel.skills.summarization_skill import SummarizationSkill
from kernel.skills.proofreading_skill import ProofreadingSkill
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

# Create sidebar with functionality options
with st.sidebar:
    st.header("Select Functionality")
    functionality = st.radio(
        "What would you like to do?",
        options=["Q&A", "Summarization", "Proofreading"],
        index=0
    )

# Main content area
if functionality == "Q&A":
    st.header("Document Q&A")
    
    # Display file selector for Q&A
    document_id = display_file_selector(
        container_name=os.environ.get("QA_CONTAINER", "qna"),
        connection_string_var="AZURE_STORAGE_CONNECTION_STRING"
    )
    
    if document_id:
        # User query input
        query = st.text_input("Ask a question about the document")
        
        if query:
            with st.spinner("Searching for answer..."):
                # Process the query using the QA skill
                answer = qa_skill.answer_question(query, document_id)
                
                # Display the answer
                display_result(answer, "qna")

elif functionality == "Summarization":
    st.header("Document Summarization")
    
    # Display file selector for summarization
    document_id = display_file_selector(
        container_name=os.environ.get("SUMMARY_CONTAINER", "summaries"),
        connection_string_var="AZURE_STORAGE_CONNECTION_STRING"
    )
    
    if document_id:
        if st.button("Get Summary"):
            with st.spinner("Generating summary..."):
                # Get the summary using the Summarization skill
                summary = summarization_skill.get_summary(document_id)
                
                # Display the summary
                display_result(summary, "summarization")

else:  # Proofreading
    st.header("Document Proofreading")
    
    # Display file selector for proofreading
    document_id = display_file_selector(
        container_name=os.environ.get("PROOFREADING_CONTAINER", "proofreading"),
        connection_string_var="AZURE_STORAGE_CONNECTION_STRING"
    )
    
    if document_id:
        if st.button("Check Document"):
            with st.spinner("Checking document..."):
                # Get the proofreading results using the Proofreading skill
                proofreading_results = proofreading_skill.get_proofread(document_id)
                
                # Display the proofreading results
                display_result(proofreading_results, "proofreading")

# Footer
st.markdown("---")
st.markdown("Powered by Semantic Kernel and Azure AI")
