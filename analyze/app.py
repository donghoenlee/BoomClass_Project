import streamlit as st

# 1. 페이지 객체 생성
# views 폴더 안에 있는 파일들을 연결합니다.
main_page = st.Page(
    "views/main_view.py", 
    title="Main", 
    icon="🏠", 
    default=True
)

dashboard_page = st.Page(
    "views/dashboard.py", 
    title="Dashboard", 
    icon="📊"
)


# 2. 네비게이션 구성 (상단/측면 메뉴바 생성)
pg = st.navigation([main_page, dashboard_page])

# 3. 공통 설정 (로고나 타이틀 등)
st.set_page_config(page_title="음원 비교 시스템", layout="wide")

# 4. 선택된 페이지 실행
pg.run()