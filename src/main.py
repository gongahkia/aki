# ----- required imports -----

import helper as h

# ----- sample execution code -----

if __name__ == "__main__":

    TARGET_FILEPATH = "./../corpus/clean/tort/corpus.json"

    data = h.load_corpus(TARGET_FILEPATH)
    if data is not None:
        model = h.start_model()
        texts = h.chunk_corpus(data)
        vector_store = h.create_vector_store(texts)
        topics = [
            "negligence",
            "duty of care",
            "standard of care",
            "causation",
            "remoteness",
        ]
        response = h.query_model(model, vector_store, topics)
        print(f"Model Response: {response}")
    else:
        print("Failed to load the corpus.")
