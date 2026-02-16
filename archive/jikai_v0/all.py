import os

from datasets import Dataset
from transformers import (
    GPT2Config,
    GPT2LMHeadModel,
    GPT2Tokenizer,
    Trainer,
    TrainingArguments,
)


def prepare_corpus(target_directory_filepath):
    if not os.path.exists(target_directory):
        raise FileNotFoundError(f"The directory '{target_directory}' does not exist.")
    else:
        text_files = [f for f in os.listdir(target_directory) if f.endswith(".txt")]
        corpus = []
        count = 0
        for file in text_files:
            file_path = os.path.join(target_directory, file)
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    corpus.append(f.read().strip())
                    count += 1
            except Exception as e:
                print(f"Error reading file '{file_path}': {e}")
    print(f"{count} documents added to the corpus")
    return Dataset.from_dict({"text": corpus})


target_directory = "../corpus/tort"
dataset = prepare_corpus(target_directory)
print(dataset)

tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
tokenizer.pad_token = tokenizer.eos_token


def tokenize_function(examples):
    return tokenizer(examples["text"], padding="max_length", truncation=True)


tokenized_dataset = dataset.map(tokenize_function, batched=True)
print(tokenized_dataset[0])
print(tokenized_dataset[len(tokenized_dataset) - 1])

config = GPT2Config(
    vocab_size=tokenizer.vocab_size,
    n_positions=1024,
    n_ctx=1024,
    n_embd=768,
    n_layer=12,
    n_head=12,
)

# FUA right now the script is breaking at the training portion of the model

model = GPT2LMHeadModel(config)

training_args = TrainingArguments(
    output_dir="./results",
    num_train_epochs=3,
    per_device_train_batch_size=4,
    save_steps=10_000,
    save_total_limit=2,
    logging_dir="./logs",
    logging_steps=500,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
)

trainer.train()

num_parties = 3
input_topic_array = ["Negligence", "Vicarious liability"]

input_ids = tokenizer.encode(
    f"Generate a scenario for the topics: {' and '.join(input_topic_array)} with {num_parties} parties",
    return_tensors="pt",
)

generated_ids = model.generate(input_ids, max_length=100, num_return_sequences=1)
generated_text = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
print(generated_text)
