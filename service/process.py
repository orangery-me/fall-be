import pandas as pd
import numpy as np
import json
import joblib
from collections import deque
from scipy.stats import skew, kurtosis
from sklearn.preprocessing import StandardScaler
from sklearn.preprocessing import LabelEncoder
from tensorflow.keras.models import load_model
import time


def load_data(source):
    with open(source, 'r', encoding='utf-8') as file:
        data = json.load(file)
        return data

def extract_features(data):
    return [
        np.mean(data),  # Giá trị trung bình
        np.std(data),  # Độ lệch chuẩn
        np.sqrt(np.mean(np.square(data))),  # Căn bậc hai trung bình bình phương (RMS)
        np.max(data),  # Biên độ lớn nhất
        np.min(data),  # Biên độ nhỏ nhất
        np.median(data),  # Trung vị
        np.sum(np.diff(np.sign(data)) != 0),  # Số lần đổi dấu
        skew(data),  # Độ lệch
        kurtosis(data),  # Độ nhọn
        np.percentile(data, 25),  # Q1
        np.percentile(data, 75),  # Q3
        np.correlate(data, data, mode='full')[len(data)-1]  # Tự tương quan
    ]


# Tạo các cửa sổ thời gian
def create_windows(data, window_size=50, overlap=0.5):
    step = int(window_size * (1 - overlap))
    data_len = data.shape[0]
    return np.array([data[i:i + window_size] for i in range(0, data_len - window_size + 1, step)])

# Lấy thời gian bắt đầu và kết thúc của các cửa sổ
def get_start_end_time(data, window_size=50, overlap=0.5):
    step = int(window_size * (1 - overlap))
    data_len = data.shape[0]
    start_times = data[0 : data_len - window_size + 1 : step]
    end_times = data[window_size - 1 : data_len : step]
    return start_times, end_times

                
def prepare_data_for_lstm(buffer, sequence_length=3):
    # Chuyển đổi dữ liệu thành định dạng phù hợp cho LSTM (queue to list)
    buffer_list = list(buffer)
    sequences = []
    
    if len(buffer_list) < sequence_length:
        print("Buffer length is less than sequence length. Returning empty array.")
        return np.array(sequences)
    
    for i in range(len(buffer) - sequence_length + 1):
        seq = np.stack(buffer_list[i:sequence_length + i], axis=0)
        sequences.append(seq)
    return np.array(sequences)

def normalize_data(data):
    scaler = joblib.load('model/scaler.pkl')
    data = scaler.transform(data)
    return data

def process_data(data, window_size=50, overlap=0.5):
    if isinstance(data, dict):
        session_data = next(iter(data.values()))
    else:
        session_data = data

    df = pd.DataFrame(session_data)

    # Lấy các cột cảm biến từ dict lồng nhau
    acc_x = df["acceleration"].apply(lambda x: x.get("x") if isinstance(x, dict) else np.nan).astype(float).values
    acc_y = df["acceleration"].apply(lambda x: x.get("y") if isinstance(x, dict) else np.nan).astype(float).values
    acc_z = df["acceleration"].apply(lambda x: x.get("z") if isinstance(x, dict) else np.nan).astype(float).values
    vec_x = df["rotation"].apply(lambda x: x.get("x") if isinstance(x, dict) else np.nan).astype(float).values
    vec_y = df["rotation"].apply(lambda x: x.get("y") if isinstance(x, dict) else np.nan).astype(float).values
    vec_z = df["rotation"].apply(lambda x: x.get("z") if isinstance(x, dict) else np.nan).astype(float).values

    # Chuẩn hóa timestamp: loại bỏ dấu cách thừa sau dấu hai chấm
    df["timestamp"] = df["timestamp"].str.replace(r':\s+', ':', regex=True)
    timestamp = pd.to_datetime(df["timestamp"]).values


    # Chia dữ liệu thành các cửa sổ (5 giây)
    acc_x_win = create_windows(acc_x, window_size, overlap)
    acc_y_win = create_windows(acc_y, window_size, overlap)
    acc_z_win = create_windows(acc_z, window_size, overlap)
    vec_x_win = create_windows(vec_x, window_size, overlap)
    vec_y_win = create_windows(vec_y, window_size, overlap)
    vec_z_win = create_windows(vec_z, window_size, overlap)
    # start_times, end_times = get_start_end_time(timestamp, window_size, overlap)
    start_times, end_times = timestamp[0], timestamp[-1]

    # Trích xuất đặc trưng từ mỗi cửa sổ
    all_window_features = []
    for k in range(acc_x_win.shape[0]):  # Lặp qua từng cửa sổ
        window_features = (
            extract_features(acc_x_win[k]) +
            extract_features(acc_y_win[k]) +
            extract_features(acc_z_win[k]) +
            extract_features(vec_x_win[k]) +
            extract_features(vec_y_win[k]) +
            extract_features(vec_z_win[k])
        )
        all_window_features.append(window_features)
        
    normalized_features = normalize_data(np.array(all_window_features))
    
    for feature in normalized_features:
        feature_buffer.append(feature)
    
    X = prepare_data_for_lstm(feature_buffer, sequence_length = 3)

    # return X, start_times, end_times
    return X, start_times, end_times

feature_buffer = deque(maxlen=3)