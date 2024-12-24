# ----- required imports -----

import agent as a
import helper as h

# ----- sample execution code -----

if __name__ == "__main__":

    TARGET_FILEPATH = "./../corpus/clean/tort/corpus.json"
    LOG_FILEPATH = "./generated_log/log.json"
    TOPICS = ["battery", "assault", "rylands v fletcher"]
    SAMPLE_SIZE = 1

    h.remove_file(LOG_FILEPATH)

    corpus_data = h.load_corpus(TARGET_FILEPATH)
    ALL_TOPICS = h.extract_all_topics(corpus_data)

    h.write_generic_log(LOG_FILEPATH, ALL_TOPICS)

    if corpus_data is not None:
        original_context = h.query_relevant_text(corpus_data, TOPICS, 1)
        h.write_query_metadata_log(LOG_FILEPATH, original_context, TOPICS)
        client = a.start_model()
        if client:

            # --- hypothetical generation agent ---

            (agent_role, raw_response) = a.query_hypothetical_generation_model(
                client, original_context, TOPICS
            )
            s1 = h.sanitise_data(raw_response)
            generated_hypothetical = s1["response"]
            h.write_agent_log(LOG_FILEPATH, agent_role, s1)

            # --- heuristic adherence check agent ---

            (agent_role, raw_response) = a.query_agent_1_model(
                client, TOPICS, generated_hypothetical
            )
            s2 = h.sanitise_data(raw_response)
            h.write_agent_log(LOG_FILEPATH, agent_role, s2)

            # --- plagarism check agent ---

            (agent_role, raw_response) = a.query_agent_2_model(
                client, original_context, generated_hypothetical
            )
            s3 = h.sanitise_data(raw_response)
            h.write_agent_log(LOG_FILEPATH, agent_role, s3)

            # --- legal analysis agent ---

            (agent_role, raw_response) = a.query_legal_analysis_model(
                client, ALL_TOPICS, generated_hypothetical
            )
            s4 = h.sanitise_data(raw_response)
            h.write_agent_log(LOG_FILEPATH, agent_role, s4)

            # --- process end ---

            h.update_generic_log(LOG_FILEPATH)
            print("Success: Ok all done")

        else:

            print("Error: Unable to load model")

    else:
        print("Error: Failed to load the corpus.")
