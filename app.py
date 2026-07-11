import requests
import pandas as pd
import streamlit as st
import pydeck as pdk
from requests.exceptions import RequestException

# --- [1] 기본 웹앱 화면 설정 ---
# 페이지 레이아웃을 넓게 설정합니다.
st.set_page_config(layout="wide")

st.title("✈️ 실시간 한반도 상공 비행기 추적 대시보드")
st.markdown("OpenSky Network API와 Pydeck을 활용하여 대한민국 상공의 실시간 비행 데이터를 시각화합니다.")

# 데이터를 새로고침할 수 있는 버튼을 만듭니다.
if st.button("🔄 실시간 데이터 새로고침"):
    st.rerun()

# --- [2] 데이터를 가져오는 함수 정의하기 ---
def get_opensky_data():
    # 금고(st.secrets) 대신 발급받은 키를 직접 입력합니다 (하드코딩).
    client_id = "10725jaewoo-api-client"
    client_secret = "xNlSQVEJF4zJGaAD53YZs6sHEzG2v1WX"
    
    token_url = "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token"
    token_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    try:
        # 1. OAuth2 토큰 받기
        token_response = requests.post(token_url, data=token_data, timeout=30)
        token_response.raise_for_status() 
        access_token = token_response.json()["access_token"]
        
        # 2. 한반도 영역 데이터 요청 (위도 33~39, 경도 124~132)
        api_url = "https://opensky-network.org/api/states/all"
        headers = {"Authorization": f"Bearer {access_token}"}
        params = {"lamin": 33.0, "lomin": 124.0, "lamax": 39.0, "lomax": 132.0}
        
        data_response = requests.get(api_url, headers=headers, params=params, timeout=30)
        data_response.raise_for_status()
        raw_data = data_response.json()
        
        # 3. 데이터프레임 변환 및 정제
        if raw_data["states"] is not None:
            columns = [
                "icao24", "callsign", "origin_country", "time_position", 
                "last_contact", "longitude", "latitude", "baro_altitude", 
                "on_ground", "velocity", "true_track", "vertical_rate", 
                "sensors", "geo_altitude", "squawk", "spi", "position_source"
            ]
            df = pd.DataFrame(raw_data["states"], columns=columns)
            
            # 지도에 그리기 위해 위도, 경도 값이 비어있는 데이터는 지워줍니다.
            df = df.dropna(subset=['longitude', 'latitude'])
            # 편명 뒤에 붙은 공백을 깔끔하게 잘라냅니다.
            df['callsign'] = df['callsign'].str.strip()
            return df
        else:
            return pd.DataFrame()
            
    except RequestException as e:
        st.error(f"API 호출 중 오류 발생: {e}")
        return None

# --- [3] 함수 실행 및 화면에 그리기 ---
# 데이터를 가져와서 변수에 담습니다.
df_planes = get_opensky_data()

# 데이터가 무사히 도착했다면 화면에 그려줍니다.
if df_planes is not None:
    if not df_planes.empty:
        
        # [데이터 분석] 고도를 기준으로 z-score 계산하기
        mean_alt = df_planes['baro_altitude'].mean()
        std_alt = df_planes['baro_altitude'].std()
        df_planes['zscore_altitude'] = (df_planes['baro_altitude'] - mean_alt) / std_alt
        
        # 상단에 상큼하게 현재 탐지된 비행기 수를 숫자로 보여줍니다.
        st.metric(label="현재 한반도 상공 비행기 수", value=f"{len(df_planes)} 대")
        
        # 좌우로 화면을 분할하여 왼쪽엔 지도, 오른쪽엔 표를 띄웁니다.
        col1, col2 = st.columns([3, 2])
        
        with col1:
            st.subheader("🗺️ 실시간 위치 지도 (빨간 점: 하위 16% 저공비행)")
            
            # 지도의 중심점(대한민국 중심)과 줌 레벨을 설정합니다.
            view_state = pdk.ViewState(
                latitude=36.0,
                longitude=127.5,
                zoom=6.5,
                pitch=0
            )
            
            # 비행기 위치를 표시하는 레이어입니다.
            layer = pdk.Layer(
                "ScatterplotLayer",
                df_planes,
                get_position="[longitude, latitude]",
                # z-score가 -1 이하(하위 16%)면 빨간색, 아니면 파란색으로 칠합니다.
                get_color="zscore_altitude <= -1 ? [255, 0, 0, 200] : [30, 144, 255, 200]", 
                get_radius=6000,
                pickable=True,
                opacity=0.8
            )
            
            # 마우스를 올렸을 때 보여줄 정보(툴팁)를 설정하고 지도를 화면에 그립니다.
            st.pydeck_chart(pdk.Deck(
                layers=[layer],
                initial_view_state=view_state,
                tooltip={"html": "<b>편명:</b> {callsign}<br><b>국적:</b> {origin_country}<br><b>고도:</b> {baro_altitude} m<br><b>속도:</b> {velocity} m/s<br><b>고도 z-score:</b> {zscore_altitude}"}
            ))
            
        with col2:
            st.subheader("📊 상세 데이터 표")
            # z-score가 포함된 표를 그려줍니다.
            display_cols = ["callsign", "origin_country", "longitude", "latitude", "baro_altitude", "zscore_altitude", "velocity"]
            st.dataframe(df_planes[display_cols], use_container_width=True, height=450)
            
    else:
        st.info("현재 해당 구역 상공에 탐지된 비행기가 없습니다.")
