# ----- required imports -----

import json
import ollama
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


def query_model(model, context, topics):
    """
    generates a query that is then
    used to prompt the model
    """
    topic_string = ", ".join(topics)
    prompt = f"""
    You are an AI tasked with generating law hypotheticals that contain specified topics. 

    Here is an example hypothetical that contains some of the same topics:

    {context}

    Now, generate a completely different, unique law hypothetical that includes the following topics:
    
    {topic_string}

    Ensure that there are no overlaps in names, situations or content.
    """
    response = model(prompt)
    return response
