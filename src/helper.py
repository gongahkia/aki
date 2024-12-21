# ----- required imports -----

import json
import ollama
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ----- helper functions -----


def load_corpus(filepath):
    """
    reads the local corpus json file and
    returns the data
    """
    try:
        with open(filepath, "r") as file:
            return json.load(file)
    except Exception as e:
        print(f"Error loading corpus: {e}")
        return None


def chunk_corpus(data):
    """
    processes corpus using chunking
    """
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = [entry["text"] for entry in data]
    return text_splitter.split_text(texts)


def create_vector_store(texts):
    """
    creates a vector store for
    effective context retrieval
    """
    embeddings = OpenAIEmbeddings()  # Use appropriate embeddings for your model
    vector_store = FAISS.from_texts(texts, embeddings)
    return vector_store


def start_model():
    """
    attempts to start and return an ollama model, else returns none
    """
    try:
        client = ollama.Client()
        return client
    except:
        return None


def load_model(model_name):
    """
    attempts to load the specified
    ollama client model
    """
    try:
        model = Ollama(model_name=model_name)
        return (True, model)
    except Exception as e:
        print(f"Error loading model '{model_name}': {e}")
        return (False, None)


def query_model(model, vector_store, topics):
    """
    generates a query that is then
    used to prompt the model
    """
    relevant_texts = vector_store.similarity_search(topics, k=3)
    context = "\n".join([text.page_content for text in relevant_texts])
    topic_string = ", ".join(topics)
    prompt = f"""
    You are an AI tasked with generating law hypotheticals that contain specified topics. 

    Here is some relevant training data:

    {context}

    Now, generate a law hypothetical that includes the following topics:
    
    {topic_string}
    """
    response = model(prompt)
    return response


# ----- sample execution -----

if __name__ == "__main__":
    TARGET_FILEPATH = "./../corpus/clean/tort/corpus.json"
    MODEL_NAME = "llama2:7b"
    data = load_corpus(TARGET_FILEPATH)
    if data is not None:
        model = start_model()
        texts = chunk_corpus(data)
        vector_store = create_vector_store(texts)
        topics = [
            "negligence",
            "duty of care",
            "standard of care",
            "causation",
            "remoteness",
        ]
        response = query_model(model, vector_store, topics)
        print(f"Model Response: {response}")
    else:
        print("Failed to load the corpus.")
