import json
from langchain.llms import Ollama


def load_corpus(filepath):
    """
    reads the local corpus json

    FUA implement this function
    """
    try:
        pass
        return json.loads()
    except:
        pass


def load_model(model_name):
    """
    attempts to load the specified
    ollama client model

    FUA tweak this function as needed
    """

    try:
        model = Ollama(model_name=model_name)
        return (True, model)
    except:
        return (False, None)


def query_model(model, context, question):
    """
    generates a query that is then used
    to prompt the model

    FUA tweak this function as needed
    """
    context = "\n".join([entry["text"] for entry in data])
    prompt = f"{context}\n\n{question}"
    response = model(prompt)
    return response
