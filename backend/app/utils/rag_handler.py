import logging
from pathlib import Path
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.docstore.document import Document as LangchainDocument # Avoid name clash
import asyncio

from ..config import settings

logger = logging.getLogger(__name__)

# --- Embedding and Vector Store Setup ---

def get_embeddings():
    """Initializes Ollama embeddings."""
    logger.debug(f"Initializing Ollama embeddings with model: {settings.rag.embedding_model_name}")
    # Ensure Ollama server is accessible
    return OllamaEmbeddings(
        model=settings.rag.embedding_model_name,
        base_url=settings.ollama.base_url
    )

def get_vector_store(persist_directory: str | None = None) -> Chroma:
    """Initializes or loads the Chroma vector store."""
    persist_dir = persist_directory or str(settings.full_vector_store_path)
    logger.info(f"Accessing ChromaDB vector store at: {persist_dir}")
    embeddings = get_embeddings()
    # Note: collection_name can be customized if needed
    return Chroma(
        persist_directory=persist_dir,
        embedding_function=embeddings
    )

def get_llm():
    """Initializes the Ollama LLM."""
    logger.debug(f"Initializing Ollama LLM via base URL: {settings.ollama.base_url}")
    return Ollama(base_url=settings.ollama.base_url) # Add model name if needed: model="llama3"

# --- Text Processing and Indexing ---

def chunk_text(text: str) -> list[LangchainDocument]:
    """Splits text into manageable chunks."""
    logger.info(f"Chunking text (length: {len(text)} chars)")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.rag.chunk_size,
        chunk_overlap=settings.rag.chunk_overlap,
        length_function=len,
    )
    # Create Langchain Documents directly from splits
    docs = [LangchainDocument(page_content=chunk) for chunk in text_splitter.split_text(text)]
    logger.info(f"Split text into {len(docs)} chunks.")
    return docs

def add_text_to_vector_store(text: str, metadata: dict, doc_id: int):
    """Chunks text and adds it to the vector store with metadata."""
    logger.info(f"Adding text for document ID {doc_id} to vector store.")
    docs = chunk_text(text)

    # Add source document ID to each chunk's metadata
    doc_metadatas = []
    for doc in docs:
        chunk_metadata = metadata.copy() # Start with base metadata (filename, etc.)
        chunk_metadata["source_doc_id"] = str(doc_id) # Use string for Chroma compatibility
        # Add chunk-specific info if needed (e.g., chunk number)
        doc_metadatas.append(chunk_metadata)

    if not docs:
        logger.warning(f"No text chunks generated for document ID {doc_id}. Skipping vector store addition.")
        return

    try:
        vector_store = get_vector_store()
        vector_store.add_documents(docs, ids=[f"{doc_id}_{i}" for i in range(len(docs))])
        # Persist changes explicitly (important for Chroma)
        vector_store.persist()
        logger.info(f"Successfully added {len(docs)} chunks for document ID {doc_id} to vector store.")
    except Exception as e:
        logger.error(f"Failed to add document {doc_id} to vector store: {e}")
        raise # Re-raise to be caught by task handler

# --- Retrieval and Question Answering ---

def setup_rag_chain(relevant_doc_ids: list[int] | None = None):
    """Sets up the RetrievalQA chain, optionally filtering by document IDs."""
    logger.info(f"Setting up RAG chain. Filtering for doc IDs: {relevant_doc_ids}")
    vector_store = get_vector_store()
    llm = get_llm()

    search_kwargs = {'k': 4} # Default number of chunks to retrieve
    if relevant_doc_ids:
        # Chroma specific filtering syntax (adjust if using FAISS etc.)
        search_kwargs['filter'] = {
            "source_doc_id": {"$in": [str(doc_id) for doc_id in relevant_doc_ids]}
        }
        logger.debug(f"RAG search_kwargs with filter: {search_kwargs}")

    retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        chain_type="stuff", # Options: "stuff", "map_reduce", "refine", "map_rerank"
        retriever=retriever,
        return_source_documents=True # Return which chunks were used
    )
    logger.info("RAG chain setup complete.")
    return qa_chain

async def query_rag(question: str, relevant_doc_ids: list[int] | None = None) -> dict:
    """Queries the RAG chain."""
    logger.info(f"Performing RAG query: '{question[:50]}...' with doc IDs: {relevant_doc_ids}")
    try:
        qa_chain = setup_rag_chain(relevant_doc_ids)
        # LangChain RAG calls are often synchronous, run in thread pool executor
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(None, qa_chain.invoke, {"query": question})
        # result = qa_chain.invoke({"query": question}) # Synchronous version

        logger.info(f"RAG query successful. Answer: '{result.get('result', '')[:50]}...'")
        return result # Contains 'query', 'result', 'source_documents'
    except Exception as e:
        logger.error(f"RAG query failed: {e}")
        # Depending on error, could be Ollama connection, vector store issue, etc.
        raise RuntimeError(f"Failed to get answer from RAG system: {e}") from e
