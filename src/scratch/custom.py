class LawHypotheticalDataset(Dataset):
    def __init__(self, corpus):
        self.corpus = corpus
    
    def __len__(self):
        return len(self.corpus)
    
    def __getitem__(self, idx):
        return torch.tensor(self.corpus[idx])

# Create a dataset and dataloader
dataset = LawHypotheticalDataset(encoded_corpus)
dataloader = DataLoader(dataset, batch_size=4, shuffle=True)

# Loss function and optimizer
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
