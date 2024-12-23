# ----- required imports -----

import helper as h

# ----- sample execution code -----

if __name__ == "__main__":

    TARGET_FILEPATH = "./../corpus/clean/tort/corpus.json"
    TOPICS = [
        "negligence",
        "duty of care",
        "standard of care",
        "causation",
        "remoteness",
    ]
    SAMPLE_SIZE = 1

    corpus_data = h.load_corpus(TARGET_FILEPATH)
    if corpus_data is not None:
        context = h.query_relevant_text(corpus_data, TOPICS, 1)
        print(f"relevant text identified as: {context}")
        model = h.start_model()
        response = h.query_model(model, context, TOPICS)
        print(f"Model Response: {response}")
    else:
        print("Failed to load the corpus.")
