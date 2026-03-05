"""
Script to load documents from text files into Milvus Lite vector store.

This script reads text files from the data directory, splits them into chunks,
creates embeddings, and stores them in a Milvus Lite vector database.
"""

import uuid

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from llama_stack_client import LlamaStackClient

from os import getenv

load_dotenv(verbose=True)


def load_and_index_documents(
    docs_to_load: str = None,
    embedding_model: str = None,
    base_url: str = None,
    api_key: str = None,
    chunk_size: int = 512,  # Increased from 64 to 512 for better context
    chunk_overlap: int = 128,  # Increased from 32 to 128 for better overlap
):
    """
    Load documents from directory and index them in Milvus Lite.

    Args:
        docs_to_load: Directory containing text files to load
        embedding_model: Name of the embedding model
        base_url: Base URL for embeddings API
        api_key: API key for embeddings
        chunk_size: Size of text chunks
        chunk_overlap: Overlap between chunks
    """
    if not embedding_model:
        embedding_model = getenv("EMBEDDING_MODEL")

    if not base_url:
        base_url = getenv("BASE_URL")

    if not api_key:
        api_key = getenv("API_KEY") or "not-needed"

    if not docs_to_load:
        docs_to_load = getenv("DOCS_TO_LOAD")

    client = LlamaStackClient(
        base_url=base_url,
        api_key=api_key,
    )

    vector_store_name = getenv("VECTOR_STORE_NAME") or "my_vector_store"
    provider_id = "milvus"
    embedding_dimension = 768

    # Delete any existing vector stores with the same name, then create a fresh one
    vector_store_list = client.vector_stores.list()

    for vs in vector_store_list.data:
        if vs.name == vector_store_name:
            print(f"Deleting existing vector store: {vs.id} ({vs.name})")
            client.vector_stores.delete(vector_store_id=vs.id)

    vector_store = client.vector_stores.create(
        name=vector_store_name,
        extra_body={
            "provider_id": provider_id,
            "embedding_model": embedding_model,
            "embedding_dimension": embedding_dimension,
        },
    )

    print(f"Vector store created: {vector_store.id} ({vector_store_name})")

    print("Loading documents from directory...")
    loader = TextLoader(docs_to_load)
    documents = loader.load()

    print("\nSplitting documents into chunks...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    all_chunks = text_splitter.split_documents(documents)

    # Filter out chunks that are empty, just whitespace, or just separator lines
    chunks = []
    for doc in all_chunks:
        content = doc.page_content.strip()
        if content and not all(c in "=-_*#|\n\r\t " for c in content):
            chunks.append(content)
    print(f"Created {len(chunks)} chunks (filtered out empty/separator chunks)")

    print("\nInitializing embeddings...")
    embeddings = OpenAIEmbeddings(
        model=embedding_model,
        api_key=api_key or "not-needed",
        base_url=base_url + "/v1",
        check_embedding_ctx_length=False,  # prevent fail if embedding model is not registered in OpenAI Registry
    )

    print("Creating embeddings...")
    embedding_vectors = embeddings.embed_documents(texts=chunks)

    print("Formatting chunks...")
    formatted_chunks = []
    for i, (text, embedding_vec) in enumerate(zip(chunks, embedding_vectors)):
        chunk = {
            "chunk_id": str(uuid.uuid4()),
            "content": text,
            "embedding": embedding_vec,
            "embedding_dimension": 768,
            "embedding_model": embedding_model,
            "chunk_metadata": {
                "document_id": "doc_1",
                "source": "sample_knowledge.txt",
            },
            "metadata": {
                "chunk_index": i,
            },
        }
        formatted_chunks.append(chunk)

    print("\nLoading chunks to Vector Store...")
    client.vector_io.insert(
        chunks=formatted_chunks,
        vector_store_id=vector_store.id,
    )


if __name__ == "__main__":
    load_and_index_documents()
