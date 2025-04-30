# app/utils/rag_handler.py
print("--- Start of rag_handler.py import ---") # Diagnostic print

import asyncio
import logging
from pathlib import Path # Import Path
from typing import List, Dict, Any

print("--- After standard imports in rag_handler.py ---") # Diagnostic print

# LangChain imports (ensure these libraries are installed)
try:
    from langchain_community.vectorstores import Chroma # Using community version
    from langchain_community.embeddings import OllamaEmbeddings # Using community version
    from langchain_community.llms import Ollama # Using community version
    from langchain.chains import RetrievalQA
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document # Using langchain_core Document
    print("--- After LangChain imports in rag_handler.py ---") # Diagnostic print
except ImportError as e:
    print(f"--- LangChain Import Error in rag_handler.py: {e} ---") # Diagnostic print for LangChain issues
    raise # Re-raise the import error

# Import settings for configuration
try:
    from ..config import settings
    print("--- After settings import in rag_handler.py ---") # Diagnostic print
except ImportError as e:
    print(f"--- Settings Import Error in rag_handler.py: {e} ---") # Diagnostic print
    raise # Re-raise the import error

# Import get_db for potential database interaction within RAG handler (if needed)
# This import is commented out in the current version, but keeping the structure
# try:
#     from ..database import get_db # Not directly used in current rag_handler logic provided
#     print("--- After database import in rag_handler.py ---") # Diagnostic print
# except ImportError as e:
#     print(f"--- Database Import Error in rag_handler.py: {e} ---") # Diagnostic print
#     raise # Re-raise the import error


logger = logging.getLogger(__name__)
print("--- After logger setup in rag_handler.py ---") # Diagnostic print


# --- Vector Store Initialization (using ChromaDB) ---
# Initialize a variable to hold the vector store instance
_vector_store = None
print("--- After _vector_store initialization in rag_handler.py ---") # Diagnostic print


def get_embedding_function():
    """Initializes and returns the embedding function."""
    print("--- Inside get_embedding_function definition ---") # Diagnostic print
    # Ensure Ollama is running and the embedding model is pulled (e.g., ollama pull nomic-embed-text)
    # The OllamaEmbeddings constructor should point to your Ollama instance
    try:
        embedding_function = OllamaEmbeddings(
            base_url=settings.ollama.base_url,
            model=settings.rag.embedding_model_name # Use the embedding model name from settings
        )
        logger.info(f"Initialized OllamaEmbeddings with model: {settings.rag.embedding_model_name}")
        print("--- get_embedding_function defined successfully ---") # Diagnostic print
        return embedding_function
    except Exception as e:
        print(f"--- Error defining get_embedding_function: {e} ---") # Diagnostic print
        logger.error(f"Failed to initialize embedding function: {e}")
        raise RuntimeError(f"Failed to initialize embedding function: {e}") from e


def get_vector_store():
    """Gets or initializes the ChromaDB vector store."""
    print("--- Inside get_vector_store definition ---") # Diagnostic print
    global _vector_store
    if _vector_store is None:
        try:
            # Ensure the vector store directory exists
            chroma_path = Path(settings.full_vector_store_path)
            chroma_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Initializing Chroma vector store at: {chroma_path}")

            # Initialize Chroma with the embedding function
            # The collection_name should be consistent
            _vector_store = Chroma(
                persist_directory=str(chroma_path),
                embedding_function=get_embedding_function(), # Calls get_embedding_function which uses settings
                collection_name=settings.rag.collection_name # Use collection name from settings (Add this to config.yaml)
            )
            logger.info("Chroma vector store initialized.")
            print("--- Chroma vector store initialized successfully ---") # Diagnostic print
        except Exception as e:
            print(f"--- Error initializing Chroma vector store: {e} ---") # Diagnostic print
            logger.error(f"Failed to initialize Chroma vector store: {e}")
            _vector_store = None # Ensure it's None if initialization fails
            raise RuntimeError(f"Failed to initialize vector store: {e}") from e # Re-raise

    return _vector_store

print("--- After get_vector_store definition in rag_handler.py ---") # Diagnostic print


# --- Document Processing for RAG ---

async def add_document_to_vector_store(processed_text_path: Path, doc_id: int):
    """Reads text from a processed file, chunks it, and adds to the vector store."""
    print("--- Inside add_document_to_vector_store definition ---") # Diagnostic print
    logger.info(f"Adding document {doc_id} from {processed_text_path} to vector store.")
    if not processed_text_path.exists():
        logger.error(f"Processed text file not found for doc {doc_id} at {processed_text_path}")
        raise FileNotFoundError(f"Processed text file not found: {processed_text_path}")

    try:
        with open(processed_text_path, 'r', encoding='utf-8') as f:
            text = f.read()

        if not text.strip():
            logger.warning(f"Processed text file for doc {doc_id} is empty.")
            return # Do not add empty content to vector store

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag.chunk_size, # Use chunk size from settings
            chunk_overlap=settings.rag.chunk_overlap # Use chunk overlap from settings
        )
        chunks = text_splitter.split_text(text)
        logger.info(f"Split document {doc_id} into {len(chunks)} chunks.")

        # Create LangChain Document objects
        # Include metadata, especially the source document ID
        documents = [
            Document(
                page_content=chunk,
                metadata={"source": str(processed_text_path), "source_doc_id": str(doc_id)} # Store original doc ID as string
            )
            for chunk in chunks
        ]

        # Add documents to the vector store
        vector_store = get_vector_store()
        # Chroma's add_documents method is synchronous
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, vector_store.add_documents, documents)

        logger.info(f"Successfully added {len(chunks)} chunks for document {doc_id} to vector store.")
        print("--- add_document_to_vector_store finished successfully ---") # Diagnostic print


    except Exception as e:
        print(f"--- Error in add_document_to_vector_store: {e} ---") # Diagnostic print
        logger.error(f"Error adding document {doc_id} to vector store: {e}", exc_info=True)
        raise RuntimeError(f"Failed to add document to vector store: {e}") from e

print("--- After add_document_to_vector_store definition in rag_handler.py ---") # Diagnostic print


# --- Retrieval and Question Answering ---

def setup_rag_chain(relevant_doc_ids: list[int] | None = None):
    """Sets up the RetrievalQA chain, optionally filtering by document IDs."""
    print("--- Inside setup_rag_chain definition ---") # Diagnostic print
    logger.info(f"Setting up RAG chain. Filtering for doc IDs: {relevant_doc_ids}")
    try:
        vector_store = get_vector_store()
        llm = get_llm() # Assuming get_llm initializes the Ollama LLM

        search_kwargs = {'k': settings.rag.k_results} # Default number of chunks to retrieve (Add k_results to config.yaml)
        if relevant_doc_ids:
            # Chroma specific filtering syntax (adjust if using FAISS etc.)
            # Filter by 'source_doc_id' which is stored as a string
            search_kwargs['filter'] = {
                "source_doc_id": {"$in": [str(doc_id) for doc_id in relevant_doc_ids]}
            }
            logger.debug(f"RAG search_kwargs with filter: {search_kwargs}")
        else:
            logger.debug("No document ID filter applied for RAG.")

        retriever = vector_store.as_retriever(search_kwargs=search_kwargs)

        qa_chain = RetrievalQA.from_chain_type(
            llm=llm,
            chain_type="stuff", # Options: "stuff", "map_reduce", "refine", "map_rerank"
            retriever=retriever,
            return_source_documents=True # Return which chunks were used
        )
        logger.info("RAG chain setup complete.")
        print("--- setup_rag_chain defined successfully ---") # Diagnostic print
        return qa_chain
    except Exception as e:
        print(f"--- Error defining setup_rag_chain: {e} ---") # Diagnostic print
        logger.error(f"Error setting up RAG chain: {e}")
        raise RuntimeError(f"Failed to set up RAG chain: {e}") from e


def get_llm():
     """Initializes and returns the Ollama LLM."""
     print("--- Inside get_llm definition ---") # Diagnostic print
     # Initialize the Ollama LLM
     # The model_name should come from settings (e.g., settings.ollama.model_name)
     # You might need to add an Ollama model name to your config.yaml
     # Example: ollama: model_name: "llama2"
     try:
         llm_instance = Ollama(
             base_url=settings.ollama.base_url,
             model=settings.ollama.model_name, # Use model name from settings (Add this to config.yaml)
             # Add other Ollama parameters here if needed
         )
         logger.info(f"Initialized Ollama LLM with model: {settings.ollama.model_name}")
         print("--- get_llm defined successfully ---") # Diagnostic print
         return llm_instance
     except Exception as e:
         print(f"--- Error defining get_llm: {e} ---") # Diagnostic print
         logger.error(f"Failed to initialize Ollama LLM: {e}")
         raise RuntimeError(f"Failed to initialize LLM: {e}") from e


print("--- After get_llm definition in rag_handler.py ---") # Diagnostic print


async def query_rag(question: str, relevant_doc_ids: list[int] | None = None) -> dict:
    """Queries the RAG chain, optionally filtering by document IDs."""
    print("--- Inside query_rag definition ---") # Diagnostic print
    logger.info(f"Performing RAG query: '{question[:50]}...' with doc IDs: {relevant_doc_ids}")
    try:
        # Pass relevant_doc_ids to setup_rag_chain
        qa_chain = setup_rag_chain(relevant_doc_ids)
        # LangChain RAG calls are often synchronous, run in thread pool executor
        loop = asyncio.get_running_loop()
        # The invoke method is the standard way to run the chain
        # Pass the query as a dictionary
        result = await loop.run_in_executor(None, qa_chain.invoke, {"query": question})

        logger.info(f"RAG query successful. Answer: '{result.get('result', '')[:50]}...'")
        # The result object contains 'query', 'result' (the answer), and 'source_documents'
        print("--- query_rag finished successfully ---") # Diagnostic print
        return result
    except Exception as e:
        print(f"--- Error in query_rag: {e} ---") # Diagnostic print
        logger.error(f"RAG query failed: {e}")
        # Depending on error, could be Ollama connection, vector store issue, etc.
        raise RuntimeError(f"Failed to get answer from RAG system: {e}") from e

print("--- After query_rag definition in rag_handler.py ---") # Diagnostic print


# --- RagHandler Class (for dependency injection) ---
# This class encapsulates the RAG logic and needs to be initialized once

print("--- Defining RagHandler class in rag_handler.py ---") # Diagnostic print
class RagHandler:
    def __init__(self):
        print("--- Inside RagHandler __init__ ---") # Diagnostic print
        self.vector_store = None
        self.llm = None
        print("--- RagHandler __init__ finished ---") # Diagnostic print


    async def ainit(self):
        """Asynchronous initialization of the RagHandler."""
        print("--- Inside RagHandler ainit ---") # Diagnostic print
        logger.info("Asynchronously initializing RagHandler...")
        try:
            # Initialize vector store and LLM within the async init method
            # Note: get_vector_store and get_llm might raise exceptions during their *initialization*
            # (e.g., if Ollama is not reachable or model is not found)
            self.vector_store = get_vector_store() # Calls get_vector_store
            print("--- RagHandler ainit: Vector store obtained ---") # Diagnostic print
            self.llm = get_llm() # Calls get_llm
            print("--- RagHandler ainit: LLM obtained ---") # Diagnostic print
            logger.info("RagHandler async initialization complete.")
            print("--- RagHandler ainit finished successfully ---") # Diagnostic print
        except Exception as e:
            print(f"--- Error in RagHandler ainit: {e} ---") # Diagnostic print
            logger.error(f"RagHandler async initialization failed: {e}")
            # Decide if initialization failure should prevent the app from starting
            # For now, re-raise the exception
            raise RuntimeError(f"Failed to initialize RAG handler: {e}") from e


    async def add_document(self, processed_text_path: Path, doc_id: int):
        """Wrapper for adding a document to the vector store."""
        print("--- Inside RagHandler add_document ---") # Diagnostic print
        # Ensure vector store is initialized
        if self.vector_store is None:
             raise RuntimeError("RagHandler not initialized: Vector store is None.")
        # Call the async function to add the document
        await add_document_to_vector_store(processed_text_path, doc_id)
        print("--- RagHandler add_document finished ---") # Diagnostic print


    async def query_rag(self, question: str, relevant_doc_ids: list[int] | None = None) -> dict:
        """Wrapper for querying the RAG chain."""
        print("--- Inside RagHandler query_rag ---") # Diagnostic print
        # Ensure LLM is initialized
        if self.llm is None:
            raise RuntimeError("RagHandler not initialized: LLM is None.")
        # Call the async query function, passing the LLM and vector store if needed
        # The query_rag function already uses get_llm and get_vector_store internally,
        # so we can just call it directly.
        result = await query_rag(question, relevant_doc_ids)
        print("--- RagHandler query_rag finished ---") # Diagnostic print
        return result

print("--- End of rag_handler.py import ---") # Diagnostic print
