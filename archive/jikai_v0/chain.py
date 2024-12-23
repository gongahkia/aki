from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter


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


def chunk_corpus(relevant_texts_data):
    """
    processes corpus using chunking and proceses each hypo seperately
    """
    # print(f"chunking the following text:{relevant_texts_data}")
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    if isinstance(relevant_texts_data, list):
        chunks = []
        for passage in relevant_texts_data:
            if isinstance(passage, str):
                chunks.extend(text_splitter.split_text(passage))
            else:
                raise ValueError(
                    f"Error: List item expected to be a string but datatype {type(passage)} found."
                )
        return chunks


def create_vector_store(chunked_texts):
    """
    creates a vector store for effective context retrieval
    """
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    vector_store = FAISS.from_texts(chunked_texts, embeddings)
    return vector_store
