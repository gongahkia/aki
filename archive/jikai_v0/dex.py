from llama_index import ListIndex, Document


def index_corpus(relevant_texts_data):
    """
    attempts to use llamaindex to prepare each hypo as a seperate document and index it
    """
    try:
        documents = [Document(text=passage) for passage in relevant_texts_data]
        index = ListIndex(documents)
        return (True, index)
    except:
        return (False, None)
