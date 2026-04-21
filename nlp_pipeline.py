from sentence_transformers import SentenceTransformer
import torch
import numpy as np

device = torch.device("mps") if torch.backends.mps.is_available() else torch.device("cpu")
print(f"Using device: {device}")

MODEL_NAME = 'sentence-transformers/distiluse-base-multilingual-cased-v1'
model = SentenceTransformer(MODEL_NAME, device=device)
def get_embeddings(text):
    if not text or text.strip() == "":
        return np.zeros(512)

    with torch.no_grad():
        embedding = model.encode(text, convert_to_numpy=True, show_progress_bar=False)

    return embedding.flatten()


if __name__ == "__main__":
    test_lyrics = "Gülpembe, her sabah erken uyanır, güneşin doğuşunu izler."
    embedding = get_embeddings(test_lyrics)
    print(f"Vektör Boyutu: {embedding.shape}") # (512,)
    print(f"Vektörden İlk 5 Değer: {embedding[:5]}")
    print(f"mean_embedding değeri: {np.mean(embedding)}")

