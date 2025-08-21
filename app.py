import streamlit as st
import pandas as pd
import os
import math
from streamlit_geolocation import streamlit_geolocation
import numpy as np # 計算を高速化するためにNumPyを使用

# --- 1. 基本設定とヘルパー関数の定義 ---

st.set_page_config(layout="centered", page_title="最寄りキロ程検索")

# データが格納されているフォルダのパス
DATA_DIR = "data"

# ★★★ NumPyを使った高速な距離計算関数 ★★★
def calculate_distance_vectorized(lat1, lon1, lat2_array, lon2_array):
    """ユーザーの緯度経度（単一）と全データの緯度経度（配列）から一度に距離を計算する"""
    R = 6371e3  # 地球の半径 (メートル)
    
    # 度をラジアンに変換
    lat1_rad = np.radians(lat1)
    lon1_rad = np.radians(lon1)
    lat2_rad = np.radians(lat2_array)
    lon2_rad = np.radians(lon2_array)

    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad

    # Haversineの公式
    a = np.sin(dlat / 2)**2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2)**2
    c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

    distances = R * c
    return distances

# データを読み込む関数（キャッシュで高速化）
@st.cache_data
def load_all_data(data_dir):
    """dataフォルダ内の全CSVを読み込み、一つのDataFrameに結合する"""
    all_csv_files = []
    try:
        all_csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    except FileNotFoundError:
        return pd.DataFrame(), False # データフレームとエラーフラグを返す

    if not all_csv_files:
        return pd.DataFrame(), True # データフレームとファイルなしフラグを返す

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
            # ファイル読み込みエラーはここでは無視
            pass
    
    if not df_list:
        return pd.DataFrame(), True
        
    master_data = pd.concat(df_list, ignore_index=True)
    return master_data, True # データフレームと成功フラグを返す

# --- 2. StreamlitアプリのUIとメイン処理 ---

st.title("🛰️ 最寄りキロ程検索ツール")
st.write(f"リポジトリ内の`{DATA_DIR}`フォルダにある全データを対象に、あなたの現在地に最も近い地点の情報を検索します。")

# 全データの読み込み
master_data, success = load_all_data(DATA_DIR)

if not success:
    st.error(f"'{DATA_DIR}' フォルダが見つかりません。リポジトリの構成を確認してください。")
elif master_data.empty:
    st.warning(f"`{DATA_DIR}`フォルダに有効なCSVデータが見つかりませんでした。")
else:
    st.success(f"準備完了 ({len(master_data):,} 件のデータを読み込みました)")
    st.markdown("---")

    st.subheader("1. 現在地を取得")
    # 位置情報を取得するウィジェット
    location = streamlit_geolocation()

    if location and location.get('latitude'):
        user_lat = location['latitude']
        user_lon = location['longitude']
        st.write(f"あなたの現在地: 緯度 `{user_lat:.6f}`, 経度 `{user_lon:.6f}`")
        
        st.subheader("2. 最寄り地点を検索")
        if st.button("検索開始", use_container_width=True):
            with st.spinner("全データから最も近い地点を計算中..."):
                # NumPy配列として緯度経度を抽出
                lat_array = master_data['Lat'].values
                lon_array = master_data['Lon'].values
                
                # 高速なベクトル計算を実行
                distances = calculate_distance_vectorized(user_lat, user_lon, lat_array, lon_array)
                
                # 最小距離のインデックス（位置）を見つける
                nearest_idx = np.argmin(distances)
                
                # 最も近い地点のデータを取得
                nearest_point = master_data.iloc[nearest_idx]
                min_distance = distances[nearest_idx]

            st.subheader("✅ 検索結果")
            
            # 結果をメトリックで表示
            col1, col2 = st.columns(2)
            # 'キロ程'列が存在するか確認
            if '中心位置キロ程' in nearest_point:
                 col1.metric("最寄りのキロ程", f"{nearest_point['中心位置キロ程']:.1f} m")
            else:
                 col1.metric("最寄りのキロ程", "情報なし")
            
            col2.metric("現在地からの距離", f"{min_distance:.1f} m")
            
            # その他の詳細情報を表示
            st.write("---")
            st.write("**最寄り地点の詳細情報:**")
            
            # 表示したい列を定義（存在しない列は無視される）
            display_columns = [
                '踏切名', '線名', '支社名', '箇所名（系統名なし）', '踏切種別'
            ]
            # nearest_pointから存在する列のみを抽出
            details_to_show = {col: nearest_point.get(col, "情報なし") for col in display_columns if col in nearest_point}

            st.table(pd.DataFrame(details_to_show.items(), columns=['項目', '内容']))
