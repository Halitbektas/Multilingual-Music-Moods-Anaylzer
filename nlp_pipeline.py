import torch
from transformers import BertTokenizer, BertModel
import numpy as np

device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
print(f"Using device: {device}")

MODEL_NAME = "bert-base-multilingual-cased"
tokenizer = BertTokenizer.from_pretrained(MODEL_NAME)
model = BertModel.from_pretrained(MODEL_NAME).to(device)

def get_bert_embeddings(text):
    if not text or text.strip() == "":
        return np.zeros(model.config.hidden_size)

    #Tokenizer

    inputs = tokenizer(text, return_tensors="pt",
                       truncation=True,
                       padding="max_length",
                       max_length=512).to(device)

    #MODEL ÇIKTI ALMA
    with torch.no_grad():
        outputs = model(**inputs)

    last_hidden_state = outputs.last_hidden_state # [batch_size, seq_length, hidden_size]

    #MEAN POOLING

    attention_mask = inputs['attention_mask']

    input_mask_expanded = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float() # [batch_size, seq_length, hidden_size]

    sum_embeddings = torch.sum(last_hidden_state * input_mask_expanded, 1) # [batch_size, hidden_size]
    sum_mask = torch.clamp(input_mask_expanded.sum(1), min=1e-9) # [batch_size, hidden_size]
    mean_embeddings = sum_embeddings / sum_mask # [batch_size, hidden_size]

    return mean_embeddings.cpu().numpy().flatten()


if __name__ == "__main__":
    test_lyrics = "Gülpembe, her sabah erken uyanır, güneşin doğuşunu izler."
    embedding = get_bert_embeddings(test_lyrics)
    print(f"Vektör Boyutu: {embedding.shape}") # (768,)
    print(f"Vektörden İlk 5 Değer: {embedding[:5]}")
    print(f"mean_embedding değeri: {np.mean(embedding)}")

