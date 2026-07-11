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

# 익명 모드에서는 너무 잦은 새로고침 시 서버가 차단하므로 주의 메시지를 띄웁니다.
auto_refresh = st.sidebar.checkbox("⏱️ 10초마다 자동 새로고침 켜기", value=False)
if auto_refresh:
    st.sidebar.warning("⚠️ 익명 모드에서는 너무 자주 새로고침하면 서버가 일시적으로 차단할 수 있습니다.")

show_airports = st.sidebar.checkbox("📌 주요 공항 위치 표시하기", value=True)

# --- [2] 데이터를 가져오는 함수 정의하기 ---
def get_opensky_data():
    # 🌟 [보안 업데이트] 아이디, 비밀번호, 토큰 발급 코드를 싹 다 지우고 익명 접속으로 변경!
    try:
        # 익명 전용 OpenSky API 주소 (인증서 헤더가 필요 없습니다)
        api_url = "https://opensky-network.org/api/states/all"
        params = {"lamin": 33.0, "lomin": 124.0, "lamax": 39.0, "lomax": 132.0}
        
        # 바로 데이터 요청하기
        data_response = requests.get(api_url, params=params, timeout=30)
        
        # 만약 너무 자주 요청해서 차단당했다면 친절하게 안내창 띄우기
        if data_response.status_code == 429:
            st.error("🛑 OpenSky 서버가 너무 바쁩니다! (익명 요청 횟수 초과) 1~2분 뒤에 새로고침 해주세요.")
            return pd.DataFrame()
            
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
            
            # 비행기 표시 레이어
            layers = [
                pdk.Layer(
                    "TextLayer",
                    df_planes,
                    get_position="[longitude, latitude]",
                    get_text="plane_icon",
                    get_size=35,
                    font_weight="'bold'",
                    get_angle="icon_angle",
                    get_color="zscore_altitude <= -3.0 ? [255, 0, 0, 220] : [30, 144, 255, 220]", 
                    pickable=True,
                    opacity=1.0
                )
            ]
            
            # 주요 공항 표시 기능
            if show_airports:
                airports_data = [
                    {"name": "ICN", "lng": 126.4392, "lat": 37.4692},
                    {"name": "GMP", "lng": 126.8026, "lat": 37.5583},
                    {"name": "PUS", "lng": 128.9387, "lat": 35.1795},
                    {"name": "CJU", "lng": 126.4930, "lat": 33.5113}
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
                    get_size=14,
                    get_color="[255, 255, 255, 255]", 
                    font_weight="'bold'",
                    get_alignment_baseline="'top'",
                    get_pixel_offset=[0, 15] 
                )
                layers.extend([airport_spots, airport_labels])
            
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
