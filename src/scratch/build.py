class SimpleTransformer(nn.Module):
    def __init__(self, vocab_size, emb_size, num_heads, num_layers):
        super(SimpleTransformer, self).__init__()
        self.embedding = nn.Embedding(vocab_size, emb_size)
        self.transformer = nn.Transformer(
            d_model=emb_size, nhead=num_heads, num_encoder_layers=num_layers, num_decoder_layers=num_layers
        )
        self.fc = nn.Linear(emb_size, vocab_size)

    def forward(self, x):
        # x: shape (batch_size, seq_length)
        embedded = self.embedding(x)  # shape (batch_size, seq_length, emb_size)
        embedded = embedded.permute(1, 0, 2)  # shape (seq_length, batch_size, emb_size)
        transformer_out = self.transformer(embedded, embedded)  # shape (seq_length, batch_size, emb_size)
        logits = self.fc(transformer_out)  # shape (seq_length, batch_size, vocab_size)
        return logits

# Model initialization
model = SimpleTransformer(
    vocab_size=len(tokenizer),  # Vocabulary size is the size of tokenizer's vocabulary
    emb_size=256,               # Embedding size
    num_heads=8,                # Number of attention heads
    num_layers=4                # Number of transformer layers
)
