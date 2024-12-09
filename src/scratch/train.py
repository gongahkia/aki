import os
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import GPT2Tokenizer
import random

num_epochs = 3  # Number of epochs to train
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)

# Training loop
for epoch in range(num_epochs):
    model.train()  # Set model to training mode
    running_loss = 0.0

    for batch_idx, batch in enumerate(dataloader):
        # Move batch to the device (GPU/CPU)
        batch = batch.to(device)

        # Prepare input and labels
        inputs = batch[:, :-1]  # All but the last token
        labels = batch[:, 1:]   # All but the first token

        # Zero the gradients
        optimizer.zero_grad()

        # Forward pass
        outputs = model(inputs)  # Shape (seq_length, batch_size, vocab_size)
        
        # Calculate loss
        loss = criterion(outputs.view(-1, len(tokenizer)), labels.view(-1))
        
        # Backpropagation
        loss.backward()
        
        # Optimizer step
        optimizer.step()

        # Update running loss
        running_loss += loss.item()

    # Print average loss for this epoch
    avg_loss = running_loss / len(dataloader)
    print(f"Epoch [{epoch+1}/{num_epochs}], Loss: {avg_loss:.4f}")

    # Optionally save the model checkpoint
    torch.save(model.state_dict(), f"law_hypothetical_model_epoch_{epoch+1}.pth")