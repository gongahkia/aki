import os
import sys

# Add src to path
sys.path.append(os.getcwd())

try:
    print("Importing src.tui.rich_app...")
    from src.tui.rich_app import JikaiTUI

    print("SUCCESS: Imported JikaiTUI")

    print("Importing flows...")
    from src.tui.flows import cleanup, corpus, gen, history, label, ocr, settings, train

    print("SUCCESS: Imported all flows")

except ImportError as e:
    print(f"FAILURE: {e}")
    sys.exit(1)
except Exception as e:
    print(f"FAILURE: {e}")
    sys.exit(1)
