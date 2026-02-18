
import time
import sys
import os

sys.path.append(os.getcwd())

def test_import(module_name):
    print(f"Importing {module_name}...")
    start = time.time()
    try:
        __import__(module_name)
        print(f"SUCCESS: {module_name} imported in {time.time() - start:.2f}s")
    except Exception as e:
        print(f"FAILURE: {module_name}: {e}")

if __name__ == "__main__":
    test_import("src.services.llm_service")
    test_import("src.services.vector_service")
    test_import("src.services.corpus_service")
    test_import("src.services.database_service")
    test_import("src.services.hypothetical_service")
    test_import("src.ml.pipeline")
