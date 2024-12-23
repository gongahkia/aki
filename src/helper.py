# ----- required imports -----

import json
import ollama

# ----- helper functions -----


def nanoseconds_to_seconds(nanoseconds):
    """
    convert nanoseconds to seconds
    """
    return nanoseconds / 1_000_000_000.0


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
    # print(f"relevant texts sorted are: {relevant_texts}")
    prioritized_texts = [text for text, _ in relevant_texts[:sample_size]]
    return prioritized_texts


def query_model(client, context, topics, law_domain="tort", number_parties=3):
    """
    generates a query that is then
    used to prompt the model

    FUA continue to tweak this function, especially the prompts
    """
    topic_string = ", ".join(topics)
    context_string = "\n\nHere is a hypothetical:\n".join(context)
    if len(context) == 1:
        complete_prompt = f"""
        You are an AI tasked with generating law hypotheticals that contain specified topics. 

        Here is 1 example hypothetical that contains some of the same topics:

        {context_string}

        Now, generate a completely different, unique {law_domain} law hypothetical involving {number_parties} parties that includes the following topics:
        
        {topic_string}

        Ensure the following.

        1. Return only a single, detailed passage specifying all relevant facts. 
        2. Ensure there are only {law_domain} law issues covered within the hypothetical.
        3. Ensure the passage has ony {number_parties} parties involved.
        4. Do not provide a breakdown of the issues or analysis of the issues within the passage. 
        5. Ensure that there are no overlaps in names, situations or content. 
        """
    else:
        complete_prompt = f"""
        You are an AI tasked with generating law hypotheticals that contain specified topics. 

        Here are {len(context)} hypotheticals that contains some of the same topics:

        {context_string}

        Now, generate a completely different, unique {law_domain} law hypothetical involving {number_parties} parties that includes the following topics:
        
        {topic_string}

        Ensure the following.

        1. Return only a single, detailed passage specifying all relevant facts. 
        2. Ensure there are only {law_domain} law issues covered within the hypothetical.
        3. Ensure the passage has ony {number_parties} parties involved.
        4. Do not provide a breakdown of the issues or analysis of the issues within the passage. 
        5. Ensure that there are no overlaps in names, situations or content. 
        """
    print(complete_prompt)
    raw_response = client.generate(prompt=complete_prompt, model="llama2:7b")
    return raw_response


def sanitise_data(raw_response):
    """
    accepts ollama client model's complete output and groups relevant data into a json
    """
    return {
        "model": {
            "model_name": raw_response["model"],
            "model_creation_time": raw_response["created_at"],
        },
        "duration": {
            "load_model_duration": nanoseconds_to_seconds(
                raw_response["load_duration"]
            ),
            "prompt_evaluation_duration": nanoseconds_to_seconds(
                raw_response["prompt_eval_duration"]
            ),
            "response_generation_duration": nanoseconds_to_seconds(
                raw_response["eval_duration"]
            ),
            "total_duration": nanoseconds_to_seconds(raw_response["total_duration"]),
        },
        "tokens": {
            "response_tokens_count": raw_response["eval_count"],
            "response_tokens_per_second": raw_response["eval_count"]
            / nanoseconds_to_seconds(raw_response["eval_duration"]),
        },
        "response": raw_response["response"],
    }
