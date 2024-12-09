import os
from datasets import Dataset
from transformers import GPT2Tokenizer

text_files = [f for f in os.listdir() if f.endswith('.txt')]
corpus = []

for file in text_files:
    with open(file, 'r') as f:
        corpus.append(f.read().strip())

dataset = Dataset.from_dict({'text': corpus})
