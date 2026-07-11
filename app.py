import requests
import pandas as pd
import streamlit as st
import pydeck as pdk
import time
from requests.exceptions import RequestException

# --- [1] 기본 웹앱 화면 설정 ---
st.set_page_config(layout="wide")

st.title("✈️ 실시간 한반도 상공 비행기 추적 대시보드")
st.markdown("OpenSky Network API와 Pydeck을 활용하여 대한민국 상공의 실시간 비행 데이터를 시각화합니다.")

# --- [사이드바 UI 구성] ---
st.sidebar.title("🎮 관제탑 컨트롤러")

if st.sidebar.button("🔄 즉시 새로고침"):
    st.rerun()

auto_refresh = st.sidebar.checkbox("⏱️ 10초마다 자동 새로고침 켜기", value=False)
show_airports = st.sidebar.checkbox("📌 주요 공항 위치 표시하기", value=True)

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
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

# --- [3] 데이터 로딩 및 화면 그리기 ---
with st.spinner("🚀 실시간 한반도 하늘에서 비행기 정보를 수신하는 중..."):
    df_planes = get_opensky_data()

if df_planes is not None:
    if not df_planes.empty:
        
        # 고도 z-score 계산 (통계학적 하위 0.15% 극단적 저공비행 탐지용)
        mean_alt = df_planes['baro_altitude'].mean()
        std_alt = df_planes['baro_altitude'].std()
        df_planes['zscore_altitude'] = (df_planes['baro_altitude'] - mean_alt) / std_alt if std_alt > 0 else 0
        
        # 화살표 기호 각도 설정
        df_planes['true_track'] = df_planes['true_track'].fillna(0)
        df_planes['plane_icon'] = '^'
        df_planes['icon_angle'] = df_planes['true_track']
        
        # 상단 대시보드 메트릭
        st.metric(label="현재 관제 구역 내 비행기 수", value=f"{len(df_planes)} 대")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader("🗺️ 실시간 디지털 관제 지도")
            st.caption("🔵 일반 비행 | 🔴 특별 저공비행 (z-score <= -3.0)")
            
            view_state = pdk.ViewState(
                latitude=36.0,
                longitude=127.5,
                zoom=6.5,
                pitch=0
            )
            
            # 비행기 표시 레이어 (z-score 기준 -3.0 고정)
            layers = [
                pdk.Layer(
                    "TextLayer",
                    df_planes,
                    get_position="[longitude, latitude]",
                    get_text="plane_icon",
                    get_size=35,
                    font_weight="'bold'",
                    get_angle="icon_angle",
                    # 정확히 z-score가 -3 이하일 때만 빨간색, 평소에는 파란색으로 매핑
                    get_color="zscore_altitude <= -3.0 ? [255, 0, 0, 220] : [30, 144, 255, 220]", 
                    pickable=True,
                    opacity=1.0
                )
            ]
            
            # 주요 공항 표시 기능 활성화 시 레이어 추가
            if show_airports:
                # 폰트 깨짐 및 Missing character 오류를 방지하기 위해 순수 영문(ASCII 기호) 코드로 전면 수정!
                airports_data = [
                    {"name": "ICN", "lng": 126.4392, "lat": 37.4692},
                    {"name": "GMP", "lng": 126.8026, "lat": 37.5583},
                    {"name": "PUS", "lng": 128.9387, "lat": 35.1795},
                    {"name": "CJU", "lng": 126.4930, "lat": 33.5113}
                ]
                df_airports = pd.DataFrame(airports_data)
                
                # 공항 노란색 점 레이어
                airport_spots = pdk.Layer(
                    "ScatterplotLayer",
                    df_airports,
                    get_position="[lng, lat]",
                    get_color="[241, 196, 15, 250]", 
                    get_radius=8000,
                    pickable=True
                )
                # 공항 코드 텍스트 레이어 (영어 대문자만 사용하므로 브라우저 에러가 원천 차단됩니다)
                airport_labels = pdk.Layer(
                    "TextLayer",
                    df_airports,
                    get_position="[lng, lat]",
                    get_text="name",
                    get_size=14,
                    get_color="[255, 255, 255, 255]", 
                    font_weight="'bold'",
                    get_alignment_baseline="'top'",
                    get_pixel_offset=[0, 15] 
                )
                layers.extend([airport_spots, airport_labels])
            
            # 툴팁 HTML 내부의 한글을 영어로 변경하여 지도 컴포넌트와의 충돌을 막아줍니다.
            st.pydeck_chart(pdk.Deck(
                layers=layers,
                initial_view_state=view_state,
                tooltip={"html": "<b>Callsign:</b> {callsign}<br><b>Country:</b> {origin_country}<br><b>Heading:</b> {true_track}°<br><b>Altitude:</b> {baro_altitude} m<br><b>z-score:</b> {zscore_altitude}"}
            ))
            
        with col2:
            st.subheader("📊 상세 데이터 표")
            display_cols = ["callsign", "origin_country", "true_track", "baro_altitude", "zscore_altitude", "velocity"]
            st.dataframe(df_planes[display_cols], use_container_width=True, height=480)
            
    else:
        st.info("현재 해당 구역 상공에 탐지된 비행기가 없습니다.")

# --- [4] 자동 새로고침 실행 ---
if auto_refresh:
    time.sleep(10)
    st.rerun()
