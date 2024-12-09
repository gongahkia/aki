from transformers import pipeline

# Load the trained model and tokenizer
generator = pipeline("text-generation", model='./final_model', tokenizer=tokenizer)

# Generate a hypothetical based on a prompt
prompt = "Generate a legal hypothetical regarding contract law, involving breach of contract and two parties: Alice and Bob."
generated_text = generator(prompt, max_length=150)

print(generated_text[0]['generated_text'])
