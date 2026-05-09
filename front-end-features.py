import pandas as pd
import numpy as np
import pickle
import joblib

som = pickle.load(open('som_results/mmma_som_model_final.pkl', 'rb'))
laser_scaler = joblib.load('som_results/laser_scaler.pkl')
laser_pca = joblib.load('som_results/laser_pca_model.pkl')
final_scaler = joblib.load('som_results/final_som_scaler.pkl')

df_db = pd.read_csv('som_music_database.csv')
df_raw = pd.read_csv('raw_music_data.csv')

def get_song_location(song_id):
    song_info = df_db[df_db['song_id'] == song_id]

    if song_info.empty:
        return {"error": "Song ID not found in the database."}

    x = int(song_info['som_x'].values[0])
    y = int(song_info['som_y'].values[0])

    return {
        "song_id": song_id,
        "title": song_info['title'].values[0],
        "artist": song_info['artist'].values[0],
        "coordinates": {"x": x, "y": y}
    }

def get_neighbors(x, y, exclude_song_id=None, limit=5):
    neighbors = df_db[(df_db['som_x'] == x) & (df_db['som_y'] == y)]

    if exclude_song_id is not None:
        neighbors = neighbors[neighbors['song_id'] != exclude_song_id]

    results = neighbors.head(limit)[['song_id', 'title', 'artist']].to_dict(orient='records')

    return {"neighbors": results}

def get_cell_mood_label(x, y):
    return None

def get_musical_dna(song_id,x,y):
    song_feat = df_raw[df_raw['song_id'] == song_id].iloc[0]

    cell_songs = df_db[(df_db['som_x'] == x) & (df_db['som_y'] == y)]
    cell_avg = df_raw[df_raw['song_id'].isin(cell_songs)].mean(numeric_only=True)

    features_to_plot = ['tempo', 'energy_rms', 'spectral_centroid']

    return {
        "song_dna":{feat: song_feat[feat] for feat in features_to_plot},
        "cell_avg_dna":{feat: cell_avg[feat] for feat in features_to_plot}
    }

def generate_journey_playlist(start_x, start_y, end_x, end_y, steps=10):
    x_path = np.linspace(start_x, end_x, steps).astype(int)
    y_path = np.linspace(start_y, end_y, steps).astype(int)

    playlist = []
    visited_cells = set()

    for px,py in zip(x_path, y_path):
        if (px, py) not in visited_cells:
            cell_songs = df_db[(df_db['som_x'] == px) & (df_db['som_y'] == py)]
            if not cell_songs.empty:
                song = cell_songs.sample(1).iloc[0]
                playlist.append({
                    "song_id": song['song_id'],
                    "title": song['title'],
                    "artist": song['artist'],
                    "cell": {"x": int(px), "y": int(py)}
                })
            visited_cells.add((px, py))
    return {"journey_playlist": playlist}


def predict_new_song(audio_features_dict, laser_emb_list):
    laser_df = pd.DataFrame([laser_emb_list])
    laser_scaled = laser_scaler.transform(laser_df)
    laser_pca_out = laser_pca.transform(laser_scaled)

    audio_df = pd.DataFrame([audio_features_dict])

    combined_data = np.concatenate((audio_df.values, laser_pca_out), axis=1)

    final_input = final_scaler.transform(combined_data)
    winner_x, winner_y = som.winner(final_input[0])

    return {
        "status": "success",
        "predicted_coordinates": {"x": int(winner_x), "y": int(winner_y)}
    }