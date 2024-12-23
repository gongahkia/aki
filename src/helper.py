# ----- required imports -----

import json
import ollama

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


def query_relevant_text(corpus, topics, sample_size):
    """
    retrieves relevant texts from the vector store based on topic,
    prioritizing those with the most overlapping topics
    """
    relevant_texts = []
    for entry in corpus:
        entry_topics = entry["topic"]
        overlap_count = len(set(entry_topics) & set(topics))
        if overlap_count > 0:
            relevant_texts.append((entry["text"], overlap_count))
    relevant_texts.sort(key=lambda x: x[1], reverse=True)
    print(f"relevant texts sorted are: {relevant_texts}")
    prioritized_texts = [text for text, _ in relevant_texts[:sample_size]]
    return prioritized_texts


def query_model(model, context, topics, law_domain="tort", number_parties=3):
    """
    generates a query that is then
    used to prompt the model
    """
    topic_string = ", ".join(topics)
    prompt = f"""
    You are an AI tasked with generating law hypotheticals that contain specified topics. 

    Here is an example hypothetical that contains some of the same topics:

    {context}

    Now, generate a completely different, unique {law_domain} law hypothetical involving {number_parties} parties that includes the following topics:
    
    {topic_string}

    Ensure that there are no overlaps in names, situations or content.
    """
    response = model(prompt)
    return response
