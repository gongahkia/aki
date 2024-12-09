from transformers import Trainer, TrainingArguments

# Set up training arguments
training_args = TrainingArguments(
    output_dir='./results',  # where to save the model
    evaluation_strategy="epoch",
    per_device_train_batch_size=4,
    per_device_eval_batch_size=4,
    num_train_epochs=3,
    logging_dir='./logs',
)

# Initialize the Trainer
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=tokenized_dataset,
    eval_dataset=tokenized_dataset,  # Use the same dataset for eval
)

# Fine-tune the model
trainer.train()

# Save the trained model
model.save_pretrained('./final_model')
