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

# [기능 3-4] 자동 새로고침 스위치 만들기
col_btn1, col_btn2 = st.columns([1, 4])
with col_btn1:
    if st.button("🔄 즉시 새로고침"):
        st.rerun()
with col_btn2:
    # 체크박스를 켜면 auto_refresh 변수가 True가 됩니다.
    auto_refresh = st.checkbox("⏱️ 10초마다 자동 새로고침 켜기")

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

# --- [3] 함수 실행 및 화면에 그리기 ---
df_planes = get_opensky_data()

if df_planes is not None:
    if not df_planes.empty:
        
        # 고도 z-score 계산
        mean_alt = df_planes['baro_altitude'].mean()
        std_alt = df_planes['baro_altitude'].std()
        df_planes['zscore_altitude'] = (df_planes['baro_altitude'] - mean_alt) / std_alt
        
        # [기능 1-1] 비행기 아이콘과 회전 각도 준비하기
        # 빈 방향 데이터(NaN)는 0도로 채워줍니다.
        df_planes['true_track'] = df_planes['true_track'].fillna(0)
        # 지도에 그릴 비행기 이모지 생성
        df_planes['plane_icon'] = '✈'
        # 비행기 이모지(✈)는 기본적으로 45도(우상단)를 바라보고 있어서, 실제 비행 방향에 맞추기 위해 45도를 빼줍니다.
        df_planes['icon_angle'] = df_planes['true_track'] - 45
        
        st.metric(label="현재 한반도 상공 비행기 수", value=f"{len(df_planes)} 대")
        
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader("🗺️ 실시간 비행기 이동 방향 (빨간색: 하위 16% 저공비행)")
            
            view_state = pdk.ViewState(
                latitude=36.0,
                longitude=127.5,
                zoom=6.5,
                pitch=0
            )
            
            # ScatterplotLayer에서 TextLayer로 변경하여 비행기 모양을 띄웁니다!
            layer = pdk.Layer(
                "TextLayer",
                df_planes,
                get_position="[longitude, latitude]",
                get_text="plane_icon",
                get_size=25, # 비행기 크기
                get_angle="icon_angle", # 계산해둔 각도대로 비행기를 회전시킵니다.
                get_color="zscore_altitude <= -1 ? [255, 0, 0, 200] : [30, 144, 255, 200]", 
                pickable=True,
                opacity=1.0
            )
            
            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"html": "<b>편명:</b> {callsign}<br><b>국적:</b> {origin_country}<br><b>방향:</b> {true_track} 도<br><b>고도:</b> {baro_altitude} m<br><b>속도:</b> {velocity} m/s"}
            ))
            
        with col2:
            st.subheader("📊 상세 데이터 표")
            display_cols = ["callsign", "origin_country", "true_track", "longitude", "latitude", "baro_altitude", "velocity"]
            st.dataframe(df_planes[display_cols], use_container_width=True, height=450)
            
    else:
        st.info("현재 해당 구역 상공에 탐지된 비행기가 없습니다.")

# --- [4] 자동 새로고침 실행 ---
# 화면을 다 그린 후, 맨 마지막에 실행됩니다.
if auto_refresh:
    time.sleep(10) # 10초를 기다립니다.
    st.rerun()     # 화면을 처음부터 다시 실행합니다!
