import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib
from sklearn.decomposition import PCA
import matplotlib.pyplot as plt
from minisom import MiniSom

def prepare_data_for_som(csv_path):
    df = pd.read_csv(csv_path)

    metadata_cols = ['title', 'artist', 'language', 'song_id']
    metadata = df[metadata_cols]

    feature_cols = [col for col in df.columns if col not in metadata_cols and col != 'url']
    features = df[feature_cols]

    if features.isnull().values.any():
        features = features.fillna(features.mean())

    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(features)

    return scaled_features, metadata, feature_cols, scaler


if __name__ == "__main__":
    csv_path = 'raw_music_dataset.csv'
    X, meta, cols, scaler = prepare_data_for_som(csv_path)
    print("Data prepared for SOM. Scaled features shape:", X.shape)

    pca = PCA(n_components=0.95)
    X_pca = pca.fit_transform(X)

    print(f"Orijinal Boyut: {X.shape[1]}")
    print(f"PCA Sonrası Boyut (95% Varyans): {X_pca.shape[1]}")

    plt.figure(figsize=(8, 4)) #kümülatif varyans oranını gösteren grafiği çizmek için bir figür oluşturuyoruz
    plt.plot(np.cumsum(pca.explained_variance_ratio_)) #kümülatif varyans oranını gösteren grafik
    plt.xlabel('Bileşen Sayısı') #x ekseni etiketi
    plt.ylabel('Kümülatif Varyans Oranı') #y ekseni etiketi
    plt.title('PCA Kümülatif Varyans Oranı') #grafik başlığı
    plt.grid(True) #grafiğe grid ekliyoruz
    plt.show() #grafiği gösteriyoruz

    joblib.dump(scaler, 'scaler_mmma.joblib')
    joblib.dump(pca, 'pca_mmma.joblib')

    print(X[0][:5])
    print(X_pca[0][:5])

    som = MiniSom(x=20, y=20, input_len=X_pca.shape[1], sigma=1.5, learning_rate=0.5) #SOM modelini oluşturuyoruz
    som.pca_weights_init(X_pca) #SOM ağırlıklarını PCA ile başlatıyoruz
    som.train_random(X_pca, 10000,verbose=True) #SOM modelini eğitiyoruz

    plt.figure(figsize=(12, 10))
    plt.pcolor(som.distance_map().T, cmap='magma') #SOM'un distance map'ini çiziyoruz
    plt.colorbar(label="hücreler arası mesafe") #colorbar ekliyoruz
    markers = {'tr': 'o', 'en': 's'}
    colors = {'tr': 'cyan', 'en': 'orange'}

    for i,x in enumerate(X_pca):
        w = som.winner(x)
        lang = meta.iloc[i]['language']
        plt.plot(w[0]+0.5, w[1]+0.5,
                 markers.get(lang, 'x'),
                 markerfacecolor=None,
                 markeredgecolor=colors.get(lang, 'gray'),
                 markersize=6,
                 markeredgewidth=2) #SOM üzerindeki her bir veri noktasını diline göre işaretliyoruz

    plt.title('SOM Distance Map with Language Markers') #grafik başlığı
    plt.show() #grafiği gösteriyoruz

