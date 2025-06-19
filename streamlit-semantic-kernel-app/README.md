# Document Processing with Semantic Kernel

This application uses Azure AI services to process documents through a Streamlit UI with Semantic Kernel as the orchestration layer.

## Features

- **Q&A**: Ask questions about documents using RAG with Azure AI Search
- **Summarization**: Get summaries of documents
- **Proofreading**: Check documents for grammar and spelling issues
- **Intent Routing**: Determine the user's intent from natural language queries

## Setup

### Prerequisites

- Python 3.9+
- Azure OpenAI resource
- Azure AI Search resource
- Azure Blob Storage account

### Installation

1. Clone this repository
2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Create a `.env` file based on the `.env.example` template and fill in your Azure credentials.

### Running the Application

```bash
cd src
streamlit run app.py
```

For the version with intent routing:

```bash
cd src
streamlit run app_with_router.py
```

## Project Structure

```
streamlit-semantic-kernel-app/
├── .env.example              # Template for environment variables
├── requirements.txt          # Project dependencies
├── README.md                 # This file
└── src/                      # Source code
    ├── app.py                # Main Streamlit application
    ├── app_with_router.py    # Enhanced app with intent routing
    ├── kernel/               # Semantic Kernel implementation
    │   ├── config.py         # Kernel configuration
    │   └── skills/           # Semantic Kernel skills
    │       ├── qa_skill.py             # Q&A skill
    │       ├── summarization_skill.py  # Summarization skill
    │       ├── proofreading_skill.py   # Proofreading skill
    │       ├── semantic_router_skill.py # Rule-based intent router
    │       └── llm_router_skill.py     # LLM-based intent router
    └── utils/                # Utility functions
        └── helpers.py        # Helper functions for the UI
```

## Azure AI Services

This application uses the following Azure AI services:

- **Azure OpenAI**: For LLM-based intent routing and text generation
- **Azure AI Search**: For document search and retrieval in the Q&A skill
- **Azure Blob Storage**: For storing and retrieving document summaries and proofreading results

## Environment Variables

See the `.env.example` file for the required environment variables.
