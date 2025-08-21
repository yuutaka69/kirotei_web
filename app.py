import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import math
import os

# --- 1. 基本設定とヘルパー関数の定義 ---

# ページ設定
st.set_page_config(layout="wide", page_title="GPS連携マッピングアプリ")

# データが格納されているフォルダのパス
DATA_DIR = "data"

# Haversine公式で2点間の距離を計算する関数 (メートル)
def calculate_distance(lat1, lon1, lat2, lon2):
    """2点の緯度経度から距離を計算する"""
    R = 6371e3  # 地球の半径 (メートル)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * \
        math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- 2. StreamlitアプリのUIとメイン処理 ---

st.title("🗺️ GPS連携マッピングアプリ")
st.write(f"リポジトリ内の`{DATA_DIR}`フォルダにあるCSVファイルを選択して、地図に表示します。")

# --- ファイル選択ロジック ---
try:
    # サーバーにクローンされたdataディレクトリの中身からCSVファイルのみをリストアップ
    all_csv_files = [f for f in os.listdir(DATA_DIR) if f.endswith('.csv')]
except FileNotFoundError:
    st.error(f"'{DATA_DIR}' フォルダが見つかりません。リポジトリのルートに`{DATA_DIR}`フォルダを作成し、CSVを格納してください。")
    all_csv_files = []

if all_csv_files:
    selected_files = st.multiselect(
        "表示するマスターデータを選択してください（複数選択可）",
        options=all_csv_files,
        default=all_csv_files[0] if all_csv_files else [] # デフォルトで最初のファイルを選択
    )
    
    # --- データ読み込みと結合 ---
    if selected_files:
        all_data_frames = []
        with st.spinner("選択されたデータを読み込み中..."):
            for file_name in selected_files:
                file_path = os.path.join(DATA_DIR, file_name)
                try:
                    df = pd.read_csv(file_path)
                    # 緯度・経度(Lat, Lon)列の存在と型を確認
                    if 'Lat' in df.columns and 'Lon' in df.columns:
                        df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
                        df['Lon'] = pd.to_numeric(df['Lon'], errors='coerce')
                        df.dropna(subset=['Lat', 'Lon'], inplace=True)
                        all_data_frames.append(df)
                    else:
                        st.warning(f"ファイル '{file_name}' には 'Lat' または 'Lon' 列がありません。スキップします。")
                except Exception as e:
                    st.warning(f"ファイル '{file_name}' の読み込みに失敗しました: {e}")
        
        # --- 地図表示とGPS連携 ---
        if all_data_frames:
            master_data = pd.concat(all_data_frames, ignore_index=True)
            st.success(f"{len(selected_files)}個のファイルから合計 {len(master_data)}件のデータを読み込みました。")
            
            location = streamlit_geolocation()
            
            # 地図の中心を決定
            if location['latitude'] and location['longitude']:
                center_lat, center_lon, zoom_start = location['latitude'], location['longitude'], 15
            else:
                center_lat, center_lon, zoom_start = master_data['Lat'].mean(), master_data['Lon'].mean(), 12
                st.info("GPS情報を取得中です... ブラウザの許可を確認してください。")

            m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start)

            # マーカーを地図に追加
            for _, row in master_data.iterrows():
                popup_html = f"<b>Line:</b> {row.get('Line', 'N/A')}<br><b>Distance:</b> {row.get('Distance', 'N/A')}"
                folium.CircleMarker(
                    [row['Lat'], row['Lon']],
                    radius=3,
                    color='red',
                    fill=True,
                    fill_color='darkred',
                    popup=folium.Popup(popup_html, max_width=200)
                ).add_to(m)

            # GPS位置が取得できたら、最寄り地点を計算・表示
            if location['latitude'] and location['longitude']:
                user_lat, user_lon = location['latitude'], location['longitude']
                
                # ユーザーの現在地マーカー
                folium.Marker(
                    [user_lat, user_lon], 
                    popup="あなたの現在地", 
                    icon=folium.Icon(color='blue', icon='user', prefix='fa')
                ).add_to(m)
                
                # 最も近いポイントを計算
                master_data['distance_to_user'] = master_data.apply(
                    lambda row: calculate_distance(user_lat, user_lon, row['Lat'], row['Lon']), axis=1
                )
                nearest_point = master_data.loc[master_data['distance_to_user'].idxmin()]
                
                st.subheader("🛰️ 最寄りのポイント情報")
                col1, col2, col3 = st.columns(3)
                col1.metric("Line", f"{nearest_point.get('Line', 'N/A')}")
                col2.metric("Distance", f"{nearest_point.get('Distance', 'N/A')}")
                col3.metric("現在地からの距離", f"{nearest_point['distance_to_user']:.1f} m")

            # 地図を表示
            st_folium(m, width='100%', height=600, returned_objects=[])

            # データテーブル表示 (任意)
            with st.expander("データテーブルを表示"):
                st.dataframe(master_data)
        else:
            st.warning("有効なデータを含むファイルが選択されていません。")
else:
    st.info(f"`{DATA_DIR}`フォルダにCSVファイルが見つかりません。GitHubリポジトリにデータをアップロードしてください。")
