# ----- required imports -----

import helper as h

# ----- sample execution code -----

if __name__ == "__main__":

    TARGET_FILEPATH = "./../corpus/clean/tort/corpus.json"
    TOPICS = ["negligence", "trespass to land", "private nuisance"]
    SAMPLE_SIZE = 1

    corpus_data = h.load_corpus(TARGET_FILEPATH)
    if corpus_data is not None:
        context = h.query_relevant_text(corpus_data, TOPICS, 1)
        client = h.start_model()
        if client:
            raw_response = h.query_model(client, context, TOPICS)
            fin = h.sanitise_data(raw_response)
            print(fin)
            print("Success: Ok all done")
        else:
            print("Error: Unable to load model")
    else:
        print("Error: Failed to load the corpus.")
