import streamlit as st
import json
import os
import json
import requests
from datetime import datetime
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

def display_multi_file_selector(container_name, connection_string_var):
    """
    Display a multi-file selector for selecting multiple documents from a blob container.
    
    Args:
        container_name: The name of the blob container
        connection_string_var: The environment variable containing the connection string
        
    Returns:
        List of selected document IDs, or empty list if none are selected
    """
    # Get the connection string from environment variables
    connection_string = os.environ.get(connection_string_var)
    
    if not connection_string:
        st.error(f"Error: {connection_string_var} environment variable not set")
        return []
    
    # Initialize the blob service client
    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)
    except Exception as e:
        st.error(f"Error connecting to blob storage: {str(e)}")
        return []
    
    # Get a list of document IDs
    try:
        # List all blobs in the container
        blobs = container_client.list_blobs()
        
        # Extract unique document IDs from blob names
        document_ids = set()
        for blob in blobs:
            # Handle both blob naming formats:
            # 1. "document_id/file.ext" (path format)
            # 2. "document_id_file.ext" (prefix format from file_upload.py)
            
            # Check if this is a path-based format with slashes
            if '/' in blob.name:
                parts = blob.name.split('/')
                if len(parts) > 0:
                    document_ids.add(parts[0])
            # Check for the doc_ID_filename.ext format (from Streamlit uploads)
            elif blob.name.startswith('doc_'):
                # Extract the document ID which is in format doc_timestamp_uniqueid
                parts = blob.name.split('_', 3)  # Split on first 3 underscores
                if len(parts) >= 3:
                    # Reconstruct document_id as doc_timestamp_uniqueid
                    document_id = f"{parts[0]}_{parts[1]}_{parts[2]}"
                    document_ids.add(document_id)
            # Add the full name as a fallback
            else:
                document_ids.add(blob.name)
        
        document_ids = sorted(list(document_ids))
        
    except Exception as e:
        st.error(f"Error listing blobs: {str(e)}")
        return []
    
    # Display the multi-select
    if len(document_ids) > 0:
        # Use a multi-select widget
        selected_documents = st.multiselect(
            "Select documents to compare (minimum 2)",
            options=document_ids,
            default=None,
            help="Select two or more documents to compare"
        )
        return selected_documents
    else:
        st.info("No documents found in the container")
        return []

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
        
        # Add checkbox for immediate ingestion
        trigger_ingestion = st.checkbox("Trigger ingestion after upload", value=True, 
                                       help="Start the ingestion process immediately after upload",
                                       key=f"trigger_ingestion_{key}")
        
        # Import ingestion_utils for ingestion configuration if needed
        ingestion_params = None
        if trigger_ingestion:
            from utils.ingestion_utils import display_ingestion_params_form
            ingestion_params = display_ingestion_params_form()
        
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
                    
                    # Trigger ingestion if requested
                    if trigger_ingestion:
                        from utils.ingestion_utils import trigger_ingestion_workflow
                        
                        # Get the blob name (document_id_filename.pdf format)
                        blob_name = f"{document_id}_{uploaded_file.name}"
                        
                        with st.spinner("Triggering document ingestion..."):
                            # Use the parameters from session state
                            ingestion_result = trigger_ingestion_workflow(
                                document_path=blob_name,
                                **(ingestion_params or {})
                            )
                            
                            if ingestion_result.get("success", False):
                                st.success("Document ingestion process started successfully!")
                                # Store the ingestion status in session state for tracking
                                st.session_state[f"ingestion_status_{document_id}"] = {
                                    "status": "started",
                                    "document_id": document_id,
                                    "blob_name": blob_name,
                                    "timestamp": datetime.now().isoformat(),
                                    "orchestration_data": ingestion_result.get("data", {})
                                }
                                
                                # Display the initial status
                                st.success("Document ingestion process started successfully!")
                                
                                # If we have the status query URI, show a button to check status
                                if "data" in ingestion_result and "statusQueryGetUri" in ingestion_result["data"]:
                                    status_uri = ingestion_result["data"]["statusQueryGetUri"]
                                    st.info(f"""
                                    You can track the status of this ingestion process in the "Document Ingestion Status" 
                                    section below or refresh this page later to see updates.
                                    """)
                                
                            else:
                                st.error(f"Failed to trigger ingestion: {ingestion_result.get('error', 'Unknown error')}")
                                # Still store the status but mark as failed
                                st.session_state[f"ingestion_status_{document_id}"] = {
                                    "status": "failed",
                                    "document_id": document_id,
                                    "blob_name": blob_name,
                                    "timestamp": datetime.now().isoformat(),
                                    "error": ingestion_result.get('error', 'Unknown error')
                                }
                                
                                # Display a troubleshooting message
                                st.info("""
                                **Troubleshooting steps:**
                                1. Check if the Azure Functions app is running (local or deployed)
                                2. Verify the function URL in the .env file
                                3. Check the Azure Functions logs for more details
                                """)
                    
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
                
                # Ensure executive summary is a string, not a JSON object
                exec_summary = result['executive']
                if isinstance(exec_summary, dict) or isinstance(exec_summary, list):
                    exec_summary = json.dumps(exec_summary, indent=2)
                
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
                    {exec_summary}
                </div>
                """, unsafe_allow_html=True)
                
                # Add some space
                st.markdown("<br>", unsafe_allow_html=True)
                
                # Ensure detailed summary is a string, not a JSON object
                detailed_summary = result['detailed']
                if isinstance(detailed_summary, dict) or isinstance(detailed_summary, list):
                    detailed_summary = json.dumps(detailed_summary, indent=2)
                
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
                    {detailed_summary}
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
                            
                            # Handle topics that might be strings, dicts, or lists
                            topics = result["topics"]
                            if not isinstance(topics, list):
                                if isinstance(topics, dict):
                                    topics = [f"{k}: {v}" for k, v in topics.items()]
                                else:
                                    topics = [str(topics)]
                                
                            for topic in topics:
                                if isinstance(topic, dict):
                                    for k, v in topic.items():
                                        topics_html += f"<p style='margin-bottom: 8px; color: inherit;'>🔹 {k}: {v}</p>"
                                else:
                                    topics_html += f"<p style='margin-bottom: 8px; color: inherit;'>🔹 {topic}</p>"
                            topics_html += "</div>"
                            st.markdown(topics_html, unsafe_allow_html=True)
                    
                    # Display Main Conclusions/Takeaways if available
                    if "conclusions" in result and result["conclusions"]:
                        with col2:
                            st.subheader("Main Conclusions/Takeaways")
                            conclusions_html = "<div style='background-color: rgba(0, 0, 0, 0.05); padding: 15px; border-radius: 5px; border: 1px solid rgba(128, 128, 128, 0.2); box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);'>"
                            
                            # Handle conclusions that might be strings, dicts, or lists
                            conclusions = result["conclusions"]
                            if not isinstance(conclusions, list):
                                if isinstance(conclusions, dict):
                                    conclusions = [f"{k}: {v}" for k, v in conclusions.items()]
                                else:
                                    conclusions = [str(conclusions)]
                            
                            for i, conclusion in enumerate(conclusions, 1):
                                if isinstance(conclusion, dict):
                                    for k, v in conclusion.items():
                                        conclusions_html += f"<p style='margin-bottom: 8px; color: inherit;'><strong>{i}.</strong> {k}: {v}</p>"
                                else:
                                    conclusions_html += f"<p style='margin-bottom: 8px; color: inherit;'><strong>{i}.</strong> {conclusion}</p>"
                            conclusions_html += "</div>"
                            st.markdown(conclusions_html, unsafe_allow_html=True)
                
            elif "summary" in result:
                # Format and display summary if it's a raw JSON string or object
                summary_content = result['summary']
                if isinstance(summary_content, dict) or isinstance(summary_content, list):
                    formatted_summary = json.dumps(summary_content, indent=2)
                    st.code(formatted_summary, language='json')
                else:
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
                # If we have a structure we don't recognize, display it as formatted JSON
                st.subheader("Summary Data")
                st.json(result)
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
        st.header("Proofreading Results")
        
        # Add horizontal rule for better visual separation
        st.markdown("---")
        
        # Check if result is a dict with the updated format
        if isinstance(result, dict):
            if "error" in result:
                st.error(result["error"])
            else:
                # Create a container for the metadata
                meta_col1, meta_col2 = st.columns(2)
                
                # Display document info if available
                if "source_file" in result and result["source_file"]:
                    meta_col1.info(f"📄 **Source**: {result['source_file']}")
                
                # Show total issues summary
                total_issues = result.get("total_issues", 0)
                if total_issues > 0:
                    meta_col2.warning(f"Found {total_issues} potential issues in this document")
                else:
                    meta_col2.success("No issues found in this document")
                
                # Create tabs for different issue categories
                categories = [
                    ("grammar_issues", "Grammar Issues 🔤", "grammar"),
                    ("spelling_issues", "Spelling Issues 📝", "spelling"),
                    ("clarity_issues", "Clarity Issues 🔍", "clarity"),
                    ("style_issues", "Style Issues ✒️", "style"),
                    ("other_issues", "Other Issues ❓", "other")
                ]
                
                # Filter out empty categories
                active_categories = [(key, name, icon) for key, name, icon in categories if result.get(key, [])]
                
                if active_categories:
                    # Create tabs only for categories that have issues
                    tabs = st.tabs([name + f" ({len(result.get(key, []))})" for key, name, _ in active_categories])
                    
                    # Display issues in each tab
                    for i, (category_key, category_name, icon) in enumerate(active_categories):
                        issues = result.get(category_key, [])
                        with tabs[i]:
                            for j, issue in enumerate(issues, 1):
                                st.markdown(f"""
                                <div style='
                                    background-color: rgba(0, 0, 0, 0.05); 
                                    color: inherit; 
                                    padding: 15px; 
                                    border-radius: 5px; 
                                    border: 1px solid rgba(128, 128, 128, 0.2);
                                    box-shadow: 0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24);
                                    margin-bottom: 10px;
                                '>
                                    <p><strong>Issue {j}:</strong></p>
                                    <p><strong>Original: </strong><span style='color: var(--theme-danger-text-color, #d62728);'>{issue.get('original', 'N/A')}</span></p>
                                    <p><strong>Suggestion: </strong><span style='color: var(--theme-success-text-color, #15b78f);'>{issue.get('suggestion', 'N/A')}</span></p>
                                    <p><strong>Context: </strong>"<em>{issue.get('context', 'N/A')}</em>"</p>
                                    <p><strong>Explanation: </strong>{issue.get('explanation', 'N/A')}</p>
                                </div>
                                """, unsafe_allow_html=True)
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
    else:
        st.write(result)

def display_ingestion_status():
    """
    Display the status of ongoing and completed ingestion processes.
    """
    # Import check_ingestion_status
    from utils.ingestion_utils import check_ingestion_status
    
    # Filter session state keys to find ingestion status entries
    ingestion_keys = [k for k in st.session_state.keys() if k.startswith("ingestion_status_")]
    
    if not ingestion_keys:
        return
        
    st.subheader("Document Ingestion Status")
    
    # Add a refresh button for all statuses
    if st.button("Refresh All Statuses"):
        st.success("Refreshing all ingestion statuses...")
    
    for key in ingestion_keys:
        status_data = st.session_state[key]
        doc_id = status_data.get("document_id", "Unknown")
        blob_name = status_data.get("blob_name", "Unknown")
        timestamp = status_data.get("timestamp", "Unknown")
        status = status_data.get("status", "Unknown")
        error_message = status_data.get("error", None)
        orchestration_data = status_data.get("orchestration_data", {})
        
        # Create a unique key for each status
        status_key = f"status_{doc_id}"
        
        # Choose color based on status
        if status == "started" or status == "running":
            status_color = "blue"
            status_icon = "🔄"
        elif status == "completed":
            status_color = "green" 
            status_icon = "✅"
        elif status == "failed":
            status_color = "red"
            status_icon = "❌"
        else:
            status_color = "orange"
            status_icon = "❓"
        
        with st.expander(f"{status_icon} Document: {blob_name} (ID: {doc_id})"):
            # Check for status query URI in the orchestration data
            status_query_uri = orchestration_data.get("statusQueryGetUri", None)
            
            # Show current status from session state
            st.markdown(f"**Status:** <span style='color:{status_color};'>{status}</span>", unsafe_allow_html=True)
            st.write(f"**Started:** {timestamp}")
            
            # If we have a status URI, add a refresh button and check real-time status
            if status_query_uri:
                if st.button("Check Current Status", key=f"check_status_{doc_id}"):
                    with st.spinner("Checking ingestion status..."):
                        # Call the function to check the current status
                        current_status = check_ingestion_status(status_query_uri)
                        
                        if current_status.get("success", False):
                            # Update the display with the current status
                            runtime_status = current_status.get("runtime_status", "Unknown")
                            custom_status = current_status.get("custom_status", "")
                            
                            # Show runtime status with appropriate color
                            if runtime_status == "Completed":
                                st.markdown(f"**Current Status:** <span style='color:green;'>{runtime_status}</span>", unsafe_allow_html=True)
                                # Update session state
                                st.session_state[key]["status"] = "completed"
                            elif runtime_status == "Failed":
                                st.markdown(f"**Current Status:** <span style='color:red;'>{runtime_status}</span>", unsafe_allow_html=True)
                                # Update session state
                                st.session_state[key]["status"] = "failed"
                                if "output" in current_status:
                                    st.session_state[key]["error"] = current_status["output"]
                            elif runtime_status == "Running":
                                st.markdown(f"**Current Status:** <span style='color:blue;'>{runtime_status}</span>", unsafe_allow_html=True)
                                # Update session state
                                st.session_state[key]["status"] = "running"
                            else:
                                st.markdown(f"**Current Status:** <span style='color:orange;'>{runtime_status}</span>", unsafe_allow_html=True)
                            
                            # Show custom status if available
                            if custom_status:
                                st.markdown(f"**Progress:** {custom_status}")
                            
                            # Show last updated time
                            if "last_updated_time" in current_status:
                                st.write(f"**Last Updated:** {current_status['last_updated_time']}")
                            
                            # Show output for completed or failed processes
                            if runtime_status in ["Completed", "Failed"] and "output" in current_status:
                                st.markdown("**Result:**")
                                st.code(current_status["output"], language="json")
                        else:
                            st.error(f"Failed to check status: {current_status.get('error', 'Unknown error')}")
                
                # Add information about the orchestration
                st.markdown("**Orchestration Details:**")
                st.json(orchestration_data)
            
            # Display error message if there is one
            if error_message:
                st.error(f"**Error:** {error_message}")
                
                # Add helpful suggestions based on common errors
                if error_message and "Connection error" in error_message:
                    st.info("""
**Troubleshooting suggestions:**
1. Make sure the Azure Function app is running locally or deployed
2. Check the INGESTION_FUNCTION_URL in your .env file
3. If you're running functions locally, try `func start` in the terminal
                    """)
                    
            # Add option to terminate the orchestration if it's running
            if status in ["started", "running"] and "terminatePostUri" in orchestration_data:
                terminate_uri = orchestration_data["terminatePostUri"].replace("{text}", "Manually terminated by user")
                if st.button("Cancel Ingestion Process", key=f"terminate_{key}_{doc_id}"):
                    with st.spinner("Cancelling ingestion process..."):
                        try:
                            response = requests.post(terminate_uri)
                            if response.status_code in [200, 202]:
                                st.success("Ingestion process cancelled successfully")
                                # Update session state
                                st.session_state[key]["status"] = "cancelled"
                            else:
                                st.error(f"Failed to cancel ingestion: {response.status_code} - {response.text}")
                        except Exception as e:
                            st.error(f"Error cancelling ingestion: {str(e)}")
                
                # Add helpful suggestions based on error messages
                if error_message and "Connection error" in error_message:
                    st.info("**Troubleshooting suggestions:**\n"
                           "1. Make sure the Azure Function app is running locally or deployed\n"
                           "2. Check the INGESTION_FUNCTION_URL in your .env file\n"
                           "3. If you're running functions locally, try `func start` in the terminal")
                elif error_message and "timed out" in error_message:
                    st.info("**Troubleshooting suggestions:**\n"
                           "1. The function might be taking longer than expected\n"
                           "2. Check function logs for errors or long-running operations\n"
                           "3. Try increasing the timeout in the ingestion_utils.py file")
            
            # Add details expander for raw response if available
            if status_data.get("raw_response"):
                with st.expander("Response Details"):
                    st.code(status_data.get("raw_response"), language="text")
            
            # Add refresh button to check current status
            if st.button("Refresh Status", key=f"refresh_{key}_{doc_id}"):
                # In a real implementation, this would check the actual status with the Azure Function
                st.info("Refreshing status... (This would check the status with the Azure Function)")
                # For now, we'll just update the timestamp to show the refresh happened
                st.session_state[key]["last_checked"] = datetime.now().isoformat()
                
            # Add option to clear this status from the display
            if st.button("Clear", key=f"clear_{key}_{doc_id}"):
                del st.session_state[key]
                st.rerun()
