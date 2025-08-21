import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from streamlit_geolocation import streamlit_geolocation
import math
import requests
import re

# --- 1. 基本設定とヘルパー関数の定義 ---

st.set_page_config(layout="wide", page_title="Multi-CSV GPS Mapper")

# GitHubリポジトリのdataフォルダからCSVファイルの一覧を取得
@st.cache_data(ttl=600) # 10分間結果をキャッシュ
def get_csv_files_from_github(repo_url):
    """GitHubリポジトリのdataフォルダ内にあるCSVファイルの一覧を取得する"""
    match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
    if not match:
        st.error("有効なGitHubリポジトリのURLではありません。例: https://github.com/owner/repo")
        return []
    
    owner, repo = match.groups()
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contents/data"
    
    try:
        response = requests.get(api_url)
        response.raise_for_status() # エラーがあれば例外を発生
        contents = response.json()
        
        csv_files = [file['name'] for file in contents if file['name'].endswith('.csv')]
        return csv_files
    except requests.exceptions.RequestException as e:
        st.error(f"GitHub APIからのファイル一覧の取得に失敗しました: {e}")
        return []

# Haversine公式で2点間の距離を計算する関数 (メートル)
def calculate_distance(lat1, lon1, lat2, lon2):
    R = 6371e3
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

# --- 2. StreamlitアプリのUIとメイン処理 ---

st.title("🗺️ マルチCSV対応 GPS連携マッピングアプリ")
st.write("GitHubリポジトリの`data`フォルダ内にある複数のCSVファイルを選択して地図に表示します。")

# ユーザーからの入力
repo_url = st.text_input(
    "GitHubリポジトリのURLを入力してください",
    "https://github.com/USERNAME/REPO" # あなたのリポジトリURLをここに入れる
)

if repo_url and "USERNAME" not in repo_url:
    csv_files = get_csv_files_from_github(repo_url)
    
    if csv_files:
        selected_files = st.multiselect(
            "表示するマスターデータを選択してください（複数選択可）",
            options=csv_files,
            default=csv_files[0] if csv_files else []
        )
        
        if selected_files:
            all_data_frames = []
            with st.spinner("選択されたデータを読み込み中..."):
                for file_name in selected_files:
                    # rawコンテンツのURLを構築
                    raw_url_match = re.search(r"github\.com/([^/]+)/([^/]+)", repo_url)
                    owner, repo = raw_url_match.groups()
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/data/{file_name}"
                    
                    try:
                        df = pd.read_csv(raw_url)
                        df['Lat'] = pd.to_numeric(df['Lat'], errors='coerce')
                        df['Lon'] = pd.to_numeric(df['Lon'], errors='coerce')
                        df.dropna(subset=['Lat', 'Lon'], inplace=True)
                        all_data_frames.append(df)
                    except Exception as e:
                        st.warning(f"ファイル '{file_name}' の読み込みに失敗しました: {e}")
            
            if all_data_frames:
                master_data = pd.concat(all_data_frames, ignore_index=True)
                st.success(f"{len(selected_files)}個のファイルから合計{len(master_data)}件のデータを読み込みました。")
                
                # --- 地図表示とGPS連携 ---
                location = streamlit_geolocation()
                
                if location['latitude'] and location['longitude']:
                    center_lat, center_lon, zoom_start = location['latitude'], location['longitude'], 15
                else:
                    center_lat, center_lon, zoom_start = master_data['Lat'].mean(), master_data['Lon'].mean(), 12
                    st.info("GPS情報を取得中です... ブラウザの許可を確認してください。")

                m = folium.Map(location=[center_lat, center_lon], zoom_start=zoom_start)

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

                if location['latitude'] and location['longitude']:
                    user_lat, user_lon = location['latitude'], location['longitude']
                    folium.Marker(
                        [user_lat, user_lon], 
                        popup="あなたの現在地", 
                        icon=folium.Icon(color='blue', icon='user', prefix='fa')
                    ).add_to(m)
                    
                    master_data['distance_to_user'] = master_data.apply(
                        lambda row: calculate_distance(user_lat, user_lon, row['Lat'], row['Lon']), axis=1
                    )
                    nearest_point = master_data.loc[master_data['distance_to_user'].idxmin()]
                    
                    st.subheader("🛰️ 最寄りのポイント情報")
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Line", f"{nearest_point.get('Line', 'N/A')}")
                    col2.metric("Distance", f"{nearest_point.get('Distance', 'N/A')}")
                    col3.metric("現在地からの距離", f"{nearest_point['distance_to_user']:.1f} m")

                st_folium(m, width='100%', height=600)

                with st.expander("データテーブルを表示"):
                    st.dataframe(master_data)
