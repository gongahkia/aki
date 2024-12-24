# ----- required imports -----

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


def query_hypothetical_generation_model(
    client, context, topics, law_domain="tort", number_parties=3, model_name="llama2:7b"
):
    """
    generates a query that is then
    used to prompt the model

    FUA continue to tweak this function, especially the prompts
    """
    agent_role = "hypothetical_generation_agent"
    topic_string = ", ".join(topics)
    context_string = "\n\nHere is a hypothetical:\n".join(context)
    if len(context) == 1:
        complete_prompt = f"""
        You are an AI tasked with generating law hypotheticals that contain specified topics. 

        Here is 1 example hypothetical that contains some of the same topics:

        {context_string}

        Now, do the following. 

        1. Generate a completely distinct {law_domain} law hypothetical involving {number_parties} parties that includes the following topics: {topic_string}
        2. Return only one detailed law hypothetical
        3. Do not provide a breakdown of issues within the passage
        4. Do not provide anlaysis of the issues within the passage
        5. Ensure there are only {law_domain} law issues covered within the hypothetical.
        6. Ensure the passage has only {number_parties} parties involved.
        7. Ensure that there are no overlaps in names, situations or content. 
        """
    else:
        complete_prompt = f"""
        You are an AI tasked with generating law hypotheticals that contain specified topics. 

        Here are {len(context)} hypotheticals that contains some of the same topics:

        {context_string}

        Now, do the following. 

        1. Generate a completely distinct {law_domain} law hypothetical involving {number_parties} parties that includes the following topics: {topic_string}
        2. Return only one detailed law hypothetical
        3. Do not provide a breakdown of issues within the passage
        4. Do not provide anlaysis of the issues within the passage
        5. Ensure there are only {law_domain} law issues covered within the hypothetical.
        6. Ensure the passage has only {number_parties} parties involved.
        7. Ensure that there are no overlaps in names, situations or content. 
        """
    print(complete_prompt)
    raw_response = client.generate(prompt=complete_prompt, model=model_name)
    return (agent_role, raw_response)


def query_agent_1_model(client, model_name="llama2:7b"):
    """
    performs agentic workflow to evaluate whether the generated hypo
    adheres to specified parameters

    FUA
    to add implementation and specify return type as a json consisting of a boolean
    and string explanation
    """
    return None


def query_agent_2_model(client, model_name="llama2:7b"):
    """
    performs agentic workflow to evaluate how similar the generated hypo is to the
    example hypos extracted from the corpus

    FUA
    to add implementation and specify return type as a json consisting of a float that
    then is checked against a hardcoded heuristic value and the model's string explanation
    """
    return None


def query_legal_analysis_model(client, model_name="llama2:7b"):
    """
    performs rudimentary legal analysis on the generated hypo
    to provide a recommended response for users

    FUA
    to add implementation and specify return type as a json consisting of a string and see
    if the prompt can be specified so that the return is point-form which can then be .split()
    and sanitised further
    """
    return None
