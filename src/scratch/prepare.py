# Load text files
text_files = [f for f in os.listdir() if f.endswith('.txt')]
corpus = []

# Read each text file and store its contents
for file in text_files:
    with open(file, 'r') as f:
        corpus.append(f.read().strip())

# Tokenizer (using GPT2's tokenizer as an example)
tokenizer = GPT2Tokenizer.from_pretrained('gpt2')

# Encode corpus using the tokenizer
def encode_text(text):
    return tokenizer.encode(text, truncation=True, padding='max_length', max_length=512)

# Tokenize the entire corpus
encoded_corpus = [encode_text(text) for text in corpus]