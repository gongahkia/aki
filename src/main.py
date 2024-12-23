# ----- required imports -----

import helper as h

# ----- sample execution code -----

if __name__ == "__main__":

    TARGET_FILEPATH = "./../corpus/clean/tort/corpus.json"

    corpus_data = h.load_corpus(TARGET_FILEPATH)
    if corpus_data is not None:
        topics = [
            "negligence",
            "duty of care",
            "standard of care",
            "causation",
            "remoteness",
        ]
        relevant_text = h.query_relevant_text(corpus_data, topics)
        print(f"relevant text identified as: {relevant_text}")

        model = h.start_model()
        texts = h.chunk_corpus(relevant_text)
        print(texts)

        print("balls")

        # response = h.query_model(model, vector_store, topics)
        # print(f"Model Response: {response}")

    else:
        print("Failed to load the corpus.")
