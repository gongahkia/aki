import os
from datasets import Dataset
from transformers import GPT2Tokenizer

target_directory = "../corpus/tort"
if not os.path.exists(target_directory):
    raise FileNotFoundError(f"The directory '{target_directory}' does not exist.")
else:
    text_files = [f for f in os.listdir(target_directory) if f.endswith('.txt')]
    corpus = []
    count = 0

    for file in text_files:
        file_path = os.path.join(target_directory, file)  
        try:
            with open(file_path, 'r', encoding='utf-8') as f:  
                corpus.append(f.read().strip())
                count += 1
        except Exception as e:
            print(f"Error reading file '{file_path}': {e}")

dataset = Dataset.from_dict({'text': corpus})
print(f'{count} documents added to the corpus')
print(dataset)

tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
tokenizer.pad_token = tokenizer.eos_token  

def tokenize_function(examples):
    return tokenizer(examples['text'], padding="max_length", truncation=True)

tokenized_dataset = dataset.map(tokenize_function, batched=True)

tokenized_dataset.save_to_disk("./tokenized_data")