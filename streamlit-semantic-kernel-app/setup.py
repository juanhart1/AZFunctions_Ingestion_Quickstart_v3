from setuptools import setup, find_packages

setup(
    name="streamlit-semantic-kernel-app",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "streamlit",
        "semantic-kernel",
        "azure-storage-blob",
        "azure-search-documents",
        "python-dotenv",
        "httpx",
        "pandas",
        "pillow",
        "werkzeug",
        "numpy",
        "openai",
        "pydantic"
    ],
)
