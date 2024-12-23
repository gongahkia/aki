# ----- required imports -----

import json
import ollama
from langchain_community.llms import Ollama
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter

# ----- helper functions -----


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
    ollama client model, now deprecated
    """
    try:
        model = Ollama(model_name=model_name)
        return (True, model)
    except Exception as e:
        print(f"Error loading model '{model_name}': {e}")
        return (False, None)


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


def query_relevant_text(corpus, topics):
    """
    retrieves relevant texts from
    the vector store based on topic
    """
    relevant_texts = []
    for entry in corpus:
        if all(topic in entry["topic"] for topic in topics):
            relevant_texts.append(entry["text"])
    return relevant_texts


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


def query_model(model, vector_store, topics):
    """
    generates a query that is then
    used to prompt the model

    FUA might need to remove the vector_store.similarity_search
    line if it doesn't serve the purpose of assingning cosine
    similarity to words that aren't exactly similar

    FUA also consider tweaking k value as needed where k represents
    number of nearest neighbours, higher k value returns more results
    while lower k value returns fewer results
    """
    relevant_texts = vector_store.similarity_search(topics, k=3)
    context = "\n".join([text["page_content"] for text in relevant_texts])
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
