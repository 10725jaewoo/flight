import requests
import pandas as pd
import streamlit as st
import pydeck as pdk
import time
from requests.exceptions import RequestException

# --- [1] 기본 웹앱 화면 설정 ---
st.set_page_config(layout="wide")

st.title("✈️ Real-time Flight Tracker (South Korea)")
st.markdown("Visualizing real-time flight data over the Korean Peninsula using OpenSky Network API and Pydeck.")

# --- [사이드바 UI 구성] ---
st.sidebar.title("🎮 Control Panel")

if st.sidebar.button("🔄 Refresh Data"):
    st.rerun()

auto_refresh = st.sidebar.checkbox("⏱️ Auto Refresh (10s)", value=False)
show_airports = st.sidebar.checkbox("📌 Show Major Airports", value=True)

# --- [2] 데이터를 가져오는 함수 정의하기 ---
def get_opensky_data():
    client_id = "10725jaewoo-api-client"
    client_secret = "xNlSQVEJF4zJGaAD53YZs6sHEzG2v1WX"
    
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    try:
        token_response = requests.post(token_url, data=token_data, timeout=30)
        token_response.raise_for_status() 
        access_token = token_response.json()["access_token"]
        
        api_url = "https://opensky-network.org/api/states/all"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"lamin": 33.0, "lomin": 124.0, "lamax": 39.0, "lomax": 132.0}
        
        data_response = requests.get(api_url, headers=headers, params=params, timeout=30)
        data_response.raise_for_status()
        raw_data = data_response.json()
        
        if raw_data["states"] is not None:
            columns = [
                "icao24", "callsign", "origin_country", "time_position", 
                "last_contact", "longitude", "latitude", "baro_altitude", 
                "on_ground", "velocity", "true_track", "vertical_rate", 
                "sensors", "geo_altitude", "squawk", "spi", "position_source"
            ]
            df = pd.DataFrame(raw_data["states"], columns=columns)
            df = df.dropna(subset=['longitude', 'latitude'])
            df['callsign'] = df['callsign'].str.strip()
            return df
        else:
            return pd.DataFrame()
            
    except RequestException as e:
        st.error(f"API Error: {e}")
        return None

# --- [3] 데이터 로딩 및 화면 그리기 ---
with st.spinner("🚀 Fetching live flight data from OpenSky Network..."):
    df_planes = get_opensky_data()

if df_planes is not None:
    if not df_planes.empty:
        
        # 고도 z-score 계산
        mean_alt = df_planes['baro_altitude'].mean()
        std_alt = df_planes['baro_altitude'].std()
        df_planes['zscore_altitude'] = (df_planes['baro_altitude'] - mean_alt) / std_alt if std_alt > 0 else 0
        
        # 화살표 기호 각도 설정
        df_planes['true_track'] = df_planes['true_track'].fillna(0)
        df_planes['plane_icon'] = '^'
        df_planes['icon_angle'] = df_planes['true_track']
        
        # 상단 대시보드 메트릭
        st.metric(label="Flights in Airspace", value=f"{len(df_planes)} AC")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader("🗺️ Live Radar Map")
            # 영문으로 캡션을 교체하여 한글 폰트 에러를 완전히 지웁니다.
            st.caption("🔵 Normal Altitude | 🔴 Low Altitude (z-score <= -1.0)")
            
            view_state = pdk.ViewState(
                latitude=36.0,
                longitude=127.5,
                zoom=6.5,
                pitch=0
            )
            
            # 비행기 표시 레이어 (테스트를 위해 z-score 기준을 -1.0으로 낮췄어!)
            layers = [
                pdk.Layer(
                    "TextLayer",
                    df_planes,
                    get_position="[longitude, latitude]",
                    get_text="plane_icon",
                    get_size=35,
                    font_weight="'bold'",
                    get_angle="icon_angle",
                    # 고도 z-score가 -1.0 이하(낮은 고도)이면 빨간색, 평범하면 파란색
                    get_color="zscore_altitude <= -1.0 ? [255, 0, 0, 220] : [30, 144, 255, 220]", 
                    pickable=True,
                    opacity=1.0
                )
            ]
            
            # 주요 공항 표시 기능
            if show_airports:
                airports_data = [
                    {"name": "Incheon Airport (ICN)", "lng": 126.4392, "lat": 37.4692},
                    {"name": "Gimpo Airport (GMP)", "lng": 126.8026, "lat": 37.5583},
                    {"name": "Gimhae Airport (PUS)", "lng": 128.9387, "lat": 35.1795},
                    {"name": "Jeju Airport (CJU)", "lng": 126.4930, "lat": 33.5113}
                ]
                df_airports = pd.DataFrame(airports_data)
                
                airport_spots = pdk.Layer(
                    "ScatterplotLayer",
                    df_airports,
                    get_position="[lng, lat]",
                    get_color="[241, 196, 15, 250]", 
                    get_radius=8000,
                    pickable=True
                )
                airport_labels = pdk.Layer(
                    "TextLayer",
                    df_airports,
                    get_position="[lng, lat]",
                    get_text="name",
                    get_size=12,
                    get_color="[255, 255, 255, 255]", 
                    get_alignment_baseline="'top'",
                    get_pixel_offset=[0, 15] 
                )
                layers.extend([airport_spots, airport_labels])
            
            # 툴팁 가이드를 영문으로 매핑하여 인코딩 오류를 방지합니다.
            st.pydeck_chart(pdk.Deck(
                layers=layers,
                initial_view_state=view_state,
                tooltip={"html": "<b>Callsign:</b> {callsign}<br><b>Country:</b> {origin_country}<br><b>Track:</b> {true_track}°<br><b>Altitude:</b> {baro_altitude} m<br><b>z-score:</b> {zscore_altitude}"}
            ))
            
        with col2:
            st.subheader("📊 Flight Data Table")
            display_cols = ["callsign", "origin_country", "true_track", "baro_altitude", "zscore_altitude", "velocity"]
            st.dataframe(df_planes[display_cols], use_container_width=True, height=480)
            
    else:
        st.info("No aircraft detected in this area.")

# --- [4] 자동 새로고침 실행 ---
if auto_refresh:
    time.sleep(10)
    st.rerun()
