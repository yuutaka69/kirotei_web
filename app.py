import streamlit as st
import pandas as pd
import os
import math
from streamlit_geolocation import streamlit_geolocation
import numpy as np

# --- 1. 基本設定とヘルパー関数の定義 ---

st.set_page_config(layout="centered", page_title="最寄りキロ程検索")

# データが格納されているフォルダのパス
DATA_DIR = "data"

# NumPyを使った高速な距離計算関数
def calculate_distance_vectorized(lat1, lon1, lat2_array, lon2_array):
    """ユーザーの緯度経度と全データの緯度経度から一度に距離を計算する"""
    R = 6371e3
    lat1_rad, lon1_rad = np.radians(lat1), np.radians(lon1)
    lat2_rad, lon2_rad = np.radians(lat2_array), np.radians(lon2_array)
    dlon, dlat = lon2_rad - lon1_rad, lat2_rad - lat1_rad
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
    return R * c

# データを読み込む関数（キャッシュで高速化）
@st.cache_data
def load_all_data(data_dir):
    """dataフォルダ内の全CSVを読み込み、一つのDataFrameに結合する"""
    all_csv_files = []
    try:
        all_csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    except FileNotFoundError:
        return pd.DataFrame(), False

    if not all_csv_files:
        return pd.DataFrame(), True

    df_list = []
    for file_name in all_csv_files:
        file_path = os.path.join(data_dir, file_name)
        try:
            df = pd.read_csv(file_path, low_memory=False)
            if 'Lat' in df.columns and 'Lon' in df.columns:
                df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
                df['Lon'] = pd.to_numeric(df['Lon'], errors='coerce')
                df.dropna(subset=['Lat', 'Lon'], inplace=True)
                df_list.append(df)
        except Exception:
            pass
    
    if not df_list:
        return pd.DataFrame(), True
        
    master_data = pd.concat(df_list, ignore_index=True)
    return master_data, True

# --- 2. StreamlitアプリのUIとメイン処理 ---

st.title("🛰️ 最寄りキロ程検索ツール (リアルタイム版)")
st.write(f"あなたの現在地が更新されるたびに、最も近い地点の情報を自動で検索・表示します。")

# 全データの読み込み
master_data, success = load_all_data(DATA_DIR)

if not success:
    st.error(f"'{DATA_DIR}' フォルダが見つかりません。")
elif master_data.empty:
    st.warning(f"`{DATA_DIR}`フォルダに有効なCSVデータが見つかりませんでした。")
else:
    st.success(f"準備完了 ({len(master_data):,} 件のデータをスキャン対象とします)")
    st.markdown("---")

    st.subheader("現在地と最寄り地点情報")
    
    # ▼▼▼【修正箇所】'key'引数を削除 ▼▼▼
    location = streamlit_geolocation()

    # 結果表示用のプレースホルダー
    results_placeholder = st.empty()

    if location and location.get('latitude'):
        user_lat = location['latitude']
        user_lon = location['longitude']
        
        with st.spinner("現在地が更新されました。最寄り地点を再計算中..."):
            lat_array = master_data['Lat'].values
            lon_array = master_data['Lon'].values
            distances = calculate_distance_vectorized(user_lat, user_lon, lat_array, lon_array)
            nearest_idx = np.argmin(distances)
            nearest_point = master_data.iloc[nearest_idx]
            min_distance = distances[nearest_idx]

            # --- 結果表示 ---
            with results_placeholder.container():
                st.write(f"**あなたの現在地:** 緯度 `{user_lat:.6f}`, 経度 `{user_lon:.6f}`")
                st.markdown("---")
                
                st.subheader("✅ 検索結果")
                col1, col2 = st.columns(2)

                kilopost_col_name = 'Distance' 
                if kilopost_col_name in nearest_point and pd.notna(nearest_point[kilopost_col_name]):
                    try:
                        kilo_val = float(nearest_point[kilopost_col_name])
                        col1.metric("最寄りのキロ程 (Distance)", f"{kilo_val:.1f}")
                    except (ValueError, TypeError):
                        col1.metric("最寄りのキロ程 (Distance)", "値が不正")
                else:
                    col1.metric("最寄りのキロ程 (Distance)", "情報なし")
                
                col2.metric("現在地からの距離", f"{min_distance:.1f} m")
                
                st.write("**詳細情報:**")
                display_columns = ['踏切名', '線名', '支社名', '箇所名（系統名なし）', '踏切種別']
                details_to_show = {col: nearest_point.get(col, "情報なし") for col in display_columns if col in nearest_point}
                st.table(pd.DataFrame(details_to_show.items(), columns=['項目', '内容']))

    else:
        results_placeholder.info("GPS位置情報の取得待機中... ブラウザの許可を確認してください。")
