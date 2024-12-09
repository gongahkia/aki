def generate_text(model, tokenizer, prompt, max_length=100):
    model.eval()  # Set the model to evaluation mode

    # Tokenize the prompt
    input_ids = tokenizer.encode(prompt, return_tensors="pt").to(device)

    # Generate tokens autoregressively
    with torch.no_grad():
        for _ in range(max_length):
            outputs = model(input_ids)  # Get the logits
            next_token_logits = outputs[0, -1, :]  # Get logits for the last token

            # Apply softmax to get probabilities
            next_token_probs = torch.softmax(next_token_logits, dim=-1)

            # Sample from the probabilities
            next_token = torch.multinomial(next_token_probs, num_samples=1)

            # Append the new token to the sequence
            input_ids = torch.cat([input_ids, next_token], dim=-1)

    # Decode the generated tokens
    generated_text = tokenizer.decode(input_ids[0], skip_special_tokens=True)
    return generated_text

# Example usage
prompt = "Generate a legal hypothetical regarding negligence law involving Alice and Bob."
generated_text = generate_text(model, tokenizer, prompt)
print(generated_text)
