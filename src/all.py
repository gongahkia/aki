import os
from datasets import Dataset
from transformers import GPT2Tokenizer, GPT2LMHeadModel, GPT2Config, Trainer, TrainingArguments

# Ensure the target directory and dataset are set up correctly
target_directory = "../../corpus/tort"
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

# Create a dataset
dataset = Dataset.from_dict({'text': corpus})
print(f'{count} documents added to the corpus')
print(dataset)

# Initialize the tokenizer (ensure you load GPT-2 tokenizer)
tokenizer = GPT2Tokenizer.from_pretrained("gpt2")
tokenizer.pad_token = tokenizer.eos_token  # Set the padding token to EOS

# Function to tokenize the text
def tokenize_function(examples):
    return tokenizer(examples['text'], padding="max_length", truncation=True)

# Apply tokenization to the dataset
tokenized_dataset = dataset.map(tokenize_function, batched=True)
print(tokenized_dataset[0])  # Print the first tokenized example to check

# Now you can proceed with model setup and training, as outlined earlier:
# Initialize a GPT-2 model (from scratch or pre-trained)
config = GPT2Config(
    vocab_size=tokenizer.vocab_size,
    n_positions=1024,
    n_ctx=1024,
    n_embd=768,
    n_layer=12,
    n_head=12
)

model = GPT2LMHeadModel(config)

# Training setup (example configuration)
training_args = TrainingArguments(
    output_dir='./results',      
    num_train_epochs=3,         
    per_device_train_batch_size=4, 
    save_steps=10_000,          
    save_total_limit=2,         
    logging_dir='./logs',       
    logging_steps=500,          
)

trainer = Trainer(
    model=model,                
    args=training_args,         
    train_dataset=tokenized_dataset,  
)

trainer.train()

# Example of generating a scenario after training
input_topic = "Space Exploration"
input_ids = tokenizer.encode(f"Generate a scenario for the topic: {input_topic}", return_tensors='pt')

# Generate a scenario
generated_ids = model.generate(input_ids, max_length=100, num_return_sequences=1)

# Decode and print the generated scenario
generated_text = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
print(generated_text)
