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
    generates a query that is then used to prompt the model to generate a law hypothetical
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


def query_agent_1_model(
    client, topics, law_domain="tort", number_parties=3, model_name="llama2:7b"
):
    """
    performs agentic workflow to evaluate whether the generated hypo
    adheres to specified parameters

    FUA
    add parse hypothetical logic from the json
    """
    agent_role = "heuristic_adherence_agent"
    topic_string = ", ".join(topics)
    complete_prompt = f"""
    You are an AI tasked with evaluating a law hypotheticals against specified parameters.

    Here is the hypothetical:
    
    {hyothetical_string} 

    Now, return boolean True or False for each of these statements, and an explanation for why the answer is True or False.

    1. The hypothetical contains {number_parties} parties.
    2. The hypothetical only contains {law_domain} law issues.
    3. The hypothetical contains only the following topics: {topic_string}.
    4. There is no breakdown of legal issues within the passage.
    5. There is no analysis of legal issues within the passage.
    """
    print(complete_prompt)
    raw_response = client.generate(prompt=complete_prompt, model=model_name)
    return (agent_role, raw_response)


def query_agent_2_model(client, law_domain="tort", model_name="llama2:7b"):
    """
    performs agentic workflow to evaluate how similar the generated hypo is to the
    example hypos extracted from the corpus

    FUA
    add parse both hypothetical logic from the json
    """
    agent_role = "corpus_similarity_agent"
    complete_prompt = f"""
    You are an AI tasked with comparing how similar two {law_domain} law hypotheticals are.
    
    Here is the first hypothetical:
    
    {reference_hypothetical_string}

    Here is the second hypothetical:

    {generated_hypothetical_string}

    Now, return boolean True or False for each of these statements, and an explanation for why the answer is True or False.

    1. The hypotheticals are more different than they are similar.
    2. The hypotheticals are more similar than they are different.
    3. The hypotheticals have overlaps in names.
    4. The hypotheticals have overlaps in situations.
    5. The hypotheticals have overlaps in content. 
    """
    print(complete_prompt)
    raw_response = client.generate(prompt=complete_prompt, model=model_name)
    return (agent_role, raw_response)


def query_legal_analysis_model(
    client, all_topics, law_domain="tort", model_name="llama2:7b"
):
    """
    performs rudimentary legal analysis on the generated hypo
    to provide a recommended response for users

    FUA
    add parse the finalised hypothetical from the json
    """
    agent_role = "legal_analysis_agent"
    topics_string = ", ".join(all_topics)
    complete_prompt = f"""
    You are an AI tasked with performing legal analysis on a {law_domain} law hypothetical.
    
    Here is the {law_domain} law hypothetical:
    
    {hypothetical_string}

    Now, answer exactly the following questions. Only include explanations when explicitly requested. 

    1. How many parties are present in the hypothetical?
    2. What {law_domain} law issues are present? Mention only relevant issues from this list of topics: {topics_string}
    3. Which parties are liable for these legal issues under {law_domain} law? Provide explanations.
    4. Which parties can claim damages for these legal issues under {law_domain} law? Provide explanations.
    """
    print(complete_prompt)
    raw_response = client.generate(prompt=complete_prompt, model=model_name)
    return (agent_role, raw_response)
