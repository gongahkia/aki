from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings


def load_model(model_name):
    """
    attempts to load the specified
    ollama client model, now deprecated
    """
    try:
        model = Ollama(model_name=model_name)
        return (True, model)
    except Exception as e:
        print(f"Error loading model '{model_name}': {e}")
        return (False, None)


def create_vector_store(chunked_texts):
    """
    creates a vector store for effective context retrieval
    """
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    vector_store = FAISS.from_texts(chunked_texts, embeddings)
    return vector_store
