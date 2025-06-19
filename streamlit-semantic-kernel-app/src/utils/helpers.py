import streamlit as st
import os
import json
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from utils.file_upload import upload_file_to_blob

def display_file_selector(container_name, connection_string_var):
    """
    Display a file selector for a blob container.
    
    Args:
        container_name: The name of the blob container
        connection_string_var: The environment variable containing the connection string
        
    Returns:
        The selected document ID, or None if no document is selected
    """
    # Get the connection string from environment variables
    connection_string = os.environ.get(connection_string_var)
    
    if not connection_string:
        st.error(f"Error: {connection_string_var} environment variable not set")
        return None
    
    # Initialize the blob service client
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
    except Exception as e:
        st.error(f"Error connecting to blob storage: {str(e)}")
        return None
    
    # Get a list of document IDs
    try:
        # List all blobs in the container
        blobs = container_client.list_blobs()
        
        # Extract unique document IDs from blob names
        document_ids = set()
        for blob in blobs:
            # Blob names are expected to be in the format "document_id/file.ext"
            parts = blob.name.split('/')
            if len(parts) > 0:
                document_ids.add(parts[0])
        
        document_ids = sorted(list(document_ids))
        
    except Exception as e:
        st.error(f"Error listing blobs: {str(e)}")
        return None
    
    # Display the dropdown
    if len(document_ids) > 0:
        selected_document = st.selectbox("Select a document", document_ids)
        return selected_document
    else:
        st.info("No documents found in the container")
        return None

def display_file_uploader(container_name, connection_string_var, key=None):
    """
    Display a file uploader for uploading PDFs to Azure Blob Storage.
    
    Args:
        container_name: The name of the blob container
        connection_string_var: The environment variable containing the connection string
        key: Optional key for the Streamlit file_uploader widget
        
    Returns:
        Tuple of (success, document_id) where success is a boolean and document_id is the ID of the uploaded document
    """
    # Create the file uploader widget
    uploaded_file = st.file_uploader(
        "Upload a PDF document", 
        type=["pdf"], 
        key=key,
        help="Upload a PDF file to process. The file will be stored in Azure Blob Storage."
    )
    
    if uploaded_file is not None:
        # Display a preview of the file
        st.write(f"Selected file: **{uploaded_file.name}**")
        
        # Add an upload button
        if st.button("Upload to Azure", key=f"upload_btn_{key}"):
            with st.spinner("Uploading file to Azure..."):
                # Upload the file using our utility function
                success, document_id, error_message = upload_file_to_blob(
                    uploaded_file=uploaded_file,
                    container_name=container_name,
                    connection_string_var=connection_string_var
                )
                
                if success:
                    st.success(f"File uploaded successfully! Document ID: {document_id}")
                    return True, document_id
                else:
                    st.error(error_message)
                    return False, None
    
    return False, None

def display_result(result, result_type):
    """
    Display a formatted result.
    
    Args:
        result: The result to display
        result_type: The type of result ("qna", "summarization", or "proofreading")
    """
    if result_type == "qna":
        st.subheader("Answer")
        st.write(result)
    elif result_type == "summarization":
        st.header("Document Summary")
        
        # Add horizontal rule for better visual separation
        st.markdown("---")
        
        # Check if result is a dict with the new format
        if isinstance(result, dict):
            if "error" in result:
                st.error(result["error"])
            elif "executive" in result and "detailed" in result:
                # Create a container for the metadata
                meta_col1, meta_col2 = st.columns(2)
                
                # Display document info if available
                if "source_file" in result and result["source_file"]:
                    meta_col1.info(f"📄 **Source**: {result['source_file']}")
                
                if "generated_date" in result and result["generated_date"]:
                    # Format the date nicely if possible
                    try:
                        from datetime import datetime
                        date_obj = datetime.fromisoformat(result["generated_date"])
                        formatted_date = date_obj.strftime("%B %d, %Y at %I:%M %p")
                        meta_col2.info(f"🕒 **Generated**: {formatted_date}")
                    except:
                        meta_col2.info(f"🕒 **Generated**: {result['generated_date']}")
                
                st.markdown("---")
                
                # Display executive summary
                st.subheader("Executive Summary")
                st.markdown(f"""
                <div style='
                    background-color: rgba(0, 0, 0, 0.05); 
                    color: inherit; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border: 1px solid rgba(128, 128, 128, 0.2);
                    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
                '>
                    {result['executive']}
                </div>
                """, unsafe_allow_html=True)
                
                # Add some space
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Display detailed summary
                st.subheader("Detailed Summary")
                st.markdown(f"""
                <div style='
                    background-color: rgba(0, 0, 0, 0.05); 
                    color: inherit; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border: 1px solid rgba(128, 128, 128, 0.2);
                    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
                '>
                    {result['detailed']}
                </div>
                """, unsafe_allow_html=True)
                
                # Add some space
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Create two columns for topics and conclusions
                if ("topics" in result and result["topics"]) or ("conclusions" in result and result["conclusions"]):
                    col1, col2 = st.columns(2)
                    
                    # Display Key Topics/Themes if available
                    if "topics" in result and result["topics"]:
                        with col1:
                            st.subheader("Key Topics/Themes")
                            topics_html = "<div style='background-color: rgba(0, 0, 0, 0.05); padding: 15px; border-radius: 5px; border: 1px solid rgba(128, 128, 128, 0.2); box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);'>"
                            for topic in result["topics"]:
                                topics_html += f"<p style='margin-bottom: 8px; color: inherit;'>🔹 {topic}</p>"
                            topics_html += "</div>"
                            st.markdown(topics_html, unsafe_allow_html=True)
                    
                    # Display Main Conclusions/Takeaways if available
                    if "conclusions" in result and result["conclusions"]:
                        with col2:
                            st.subheader("Main Conclusions/Takeaways")
                            conclusions_html = "<div style='background-color: rgba(0, 0, 0, 0.05); padding: 15px; border-radius: 5px; border: 1px solid rgba(128, 128, 128, 0.2); box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);'>"
                            for i, conclusion in enumerate(result["conclusions"], 1):
                                conclusions_html += f"<p style='margin-bottom: 8px; color: inherit;'><strong>{i}.</strong> {conclusion}</p>"
                            conclusions_html += "</div>"
                            st.markdown(conclusions_html, unsafe_allow_html=True)
                
            elif "summary" in result:
                # Legacy format with just one summary
                st.markdown(f"""
                <div style='
                    background-color: rgba(0, 0, 0, 0.05); 
                    color: inherit; 
                    padding: 15px; 
                    border-radius: 5px; 
                    border: 1px solid rgba(128, 128, 128, 0.2);
                    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
                '>
                    {result['summary']}
                </div>
                """, unsafe_allow_html=True)
            else:
                st.write("Unknown summary format")
        else:
            # Handle legacy string format
            st.markdown(f"""
            <div style='
                background-color: rgba(0, 0, 0, 0.05); 
                color: inherit; 
                padding: 15px; 
                border-radius: 5px; 
                border: 1px solid rgba(128, 128, 128, 0.2);
                box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
            '>
                {result}
            </div>
            """, unsafe_allow_html=True)
    elif result_type == "proofreading":
        st.subheader("Proofreading Results")
        st.write(result)
    else:
        st.write(result)
