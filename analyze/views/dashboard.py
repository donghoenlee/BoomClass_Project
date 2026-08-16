import streamlit as st
import streamlit.components.v1 as components
import json
import os
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import matplotlib.pyplot as plt
import base64

# --- [1. 환경 설정 및 폰트] ---
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

# CSS: 스타일링 업데이트
st.markdown("""
    <style>
    .top-btn {
        position: fixed;
        bottom: 20px;
        right: 20px;
        background-color: #4C6EF5;
        color: white !important;
        padding: 10px 15px;
        border-radius: 50px;
        text-decoration: none !important;
        z-index: 9999;
        font-weight: bold;
        box-shadow: 2px 2px 10px rgba(0,0,0,0.2);
    }
    .anchor { display: block; position: relative; top: -100px; visibility: hidden; }
    
    .toggle-container {
        display: flex;
        justify-content: flex-end; 
        align-items: center;
        gap: 5px;
        padding: 4px 10px;
        border: 1px solid rgba(0,0,0,0.1);
        border-radius: 8px;
        background-color: rgba(255,255,255,0.9);
        width: fit-content;
        margin-left: auto;
        margin-right: 235px; 
        margin-bottom: -43px; 
        position: relative;
        z-index: 999;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    
    .toggle-container label {
        font-size: 11px !important;
        font-weight: 600 !important;
        white-space: nowrap;
    }

    div[data-testid="stDataFrame"] {
        width: 100% !important;
    }

    .audio-player-box {
        margin-top: -10px;
        padding: 10px;
        background-color: #fcfcfc;
        border-radius: 0 0 10px 10px;
        border: 1px solid #eee;
    }
    </style>
    <div id="top_anchor"></div>
    <a href="#top_anchor" class="top-btn">TOP ▲</a>
    """, unsafe_allow_html=True)

def get_flute_note_names(start_midi, end_midi):
    notes = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    mapping = {}
    for m in range(int(start_midi), int(end_midi) + 1):
        name = notes[m % 12]
        octave = (m // 12) - 1
        mapping[m] = f"{name}{octave}"
    return mapping

def get_dyn_label(v):
    if v <= 0.2: return "pp"
    elif v <= 0.4: return "p"
    elif v <= 0.6: return "mf"
    elif v <= 0.8: return "f"
    else: return "ff"

def make_pitch_ticks(note_map: dict, mode: str):
    items = sorted(note_map.items(), key=lambda x: x[0])
    if mode == "간단(자연음만)":
        filt = [(m, n) for (m, n) in items if "#" not in n]
    elif mode == "중간(2반음 간격)":
        filt = items[::2]
    else:
        filt = items
    return [m for (m, _) in filt], [n for (_, n) in filt]

# Python에서 미리 Data URI 포맷으로 변환
def to_data_uri(data, mime_type="audio/mp3"):
    if data is None:
        return ""
    
    # 데이터가 이미 문자열(str)인 경우
    if isinstance(data, str):
        # 이미 data URI 형식이면 그대로 반환, 아니면 접두어만 추가
        if data.startswith("data:"):
            return data
        return f"data:{mime_type};base64,{data}"
    
    # 데이터가 바이트(bytes)인 경우 기존 로직 수행
    b64_str = base64.b64encode(data).decode("utf-8")
    return f"data:{mime_type};base64,{b64_str}"

# 파일 읽기 전용 함수 정의
def read_file(filename):
    # 현재 파일(dashboard.py)의 절대 경로를 가져옴
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 상위 폴더(your_project/)로 올라가서 static 폴더 경로를 생성
    project_root = os.path.dirname(current_dir)
    file_path = os.path.join(project_root, "static", "dashboard", filename)
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return ""
        
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def st_time_select(plot_html, audio_uri_a, audio_uri_b, audio_uri_stereo):
    # 웹문서 파일 호출
    html_tpl = read_file("plot_component.html")
    css_content = read_file("plot_style.css")
    js_content = read_file("plot_script.js")

    # ... (기존 replace 로직) ...
    js_content = js_content.replace("{audio_uri_a}", audio_uri_a)
    js_content = js_content.replace("{audio_uri_b}", audio_uri_b)
    js_content = js_content.replace("{audio_uri_stereo}", audio_uri_stereo)

    final_html = html_tpl.replace("{{CUSTOM_CSS}}", css_content)
    final_html = final_html.replace("{{CUSTOM_JS}}", js_content)
    final_html = final_html.replace("{plot_html}", plot_html)

    return components.html(final_html, height=750)


# --- [2. 세션 상태 초기화] ---
if "uploaded_data" not in st.session_state:
    st.session_state["uploaded_data"] = {}
if "active_student" not in st.session_state:
    st.session_state["active_student"] = None
if "selected_time" not in st.session_state:
    st.session_state["selected_time"] = {}

# --- [2-1. 데모용 샘플 데이터 자동 로드] ---
# 배포 환경에는 원본 영상이 없으므로, 저장소에 포함된 샘플 분석 결과를
# 첫 접속 시 자동으로 불러와서 별도 업로드 없이 바로 결과를 볼 수 있게 한다.
if "sample_autoloaded" not in st.session_state:
    st.session_state["sample_autoloaded"] = True
    if not st.session_state["uploaded_data"]:
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "student_analysis.json",
        )
        if os.path.exists(sample_path):
            try:
                with open(sample_path, "r", encoding="utf-8") as f:
                    sample_data = json.load(f)
                sample_name = "샘플 학생 (student_analysis.json)"
                st.session_state["uploaded_data"] = {sample_name: sample_data}
                st.session_state["active_student"] = sample_name
            except Exception:
                pass

# --- [3. 사이드바 구성] ---
with st.sidebar:
    st.header("👨‍🏫 선생님 기준 음원")
    teacher_audio_placeholder = st.empty()
    st.caption("선생님 시범 연주")
    st.markdown("---")
    st.header("📋 학생 목록 ")

    if not st.session_state["uploaded_data"]:
        st.info("하단에서 JSON 파일을 업로드해주세요.")
    else:
        for s_name in list(st.session_state["uploaded_data"].keys()):
            is_active = (st.session_state["active_student"] == s_name)
            btn_type = "primary" if is_active else "secondary"

            if st.button(f"👤 {s_name}", use_container_width=True, type=btn_type, key=f"btn_{s_name}"):
                st.session_state["active_student"] = None if is_active else s_name
                st.session_state["selected_time"] = {} 
                st.rerun()   

            if is_active:
                curr_student = st.session_state["uploaded_data"][s_name]
                try:
                    teacher_audio_placeholder.audio(base64.b64decode(curr_student['audio_bin_a']), format='audio/mp3')
                except:
                    teacher_audio_placeholder.error("음원 복원 실패")
                st.audio(base64.b64decode(curr_student['audio_bin_b']), format='audio/mp3')
                st.caption("학생 연주")
                st.audio(base64.b64decode(curr_student['audio_bin_stereo']), format='audio/mp3')
                st.caption("비교 음원 (왼쪽: 기준 | 오른쪽: 이용자)")
                st.markdown("---")

    st.sidebar.markdown("<br>" * -1, unsafe_allow_html=True)
    with st.sidebar.expander("📂 데이터 업로드 (JSON)", expanded=not bool(st.session_state["uploaded_data"])):
        uploaded_files = st.file_uploader("파일 선택", type=["json"], accept_multiple_files=True, label_visibility="collapsed")
        if uploaded_files:
            new_temp_data = {}
            for i, file in enumerate(uploaded_files):
                try:
                    file.seek(0)
                    data = json.load(file)
                    new_temp_data[f"학생 {i+1} ({file.name})"] = data
                except: continue
            if new_temp_data != st.session_state["uploaded_data"]:
                st.session_state["uploaded_data"] = new_temp_data
                st.rerun()

# --- [4. 메인 화면 구성] ---
selected_name = st.session_state["active_student"]

if not selected_name:
    st.title("🎶 플루트 정밀 분석 시스템")
    st.info("왼쪽 사이드바에서 학생을 선택해주세요.")
else:
    d = st.session_state["uploaded_data"][selected_name]
    times = np.array(d['times'])
    ref_pitch, u_pitch = np.array(d['ref_pitch']), np.array(d['u_pitch'])
    ref_rms, u_rms = np.array(d['ref_rms']), np.array(d['u_rms'])
    t_errors = np.array(d['t_errors'])
    df_err = pd.DataFrame(d['df_err'])

    score_col, title_col = st.columns([1, 4])
    with score_col:
        st.metric(label="✅ 종합 점수", value=f"{round(d['total_score'], 1)} / 100")
    with title_col:
        # st.title(f"📊 {selected_name} 분석 리포트")
        st.title(f"분석 대시보드")

    st.markdown("---")
    
    with st.expander("분석 정보", expanded=True):
        st.caption("학생 상세 정보")
        # 열 너비 비율 설정 (라벨은 좁게, 값은 넓게)
        col_ratio = [1, 3]

        # 1행: 학생명
        row1_1, row1_2 = st.columns(col_ratio)
        with row1_1:
            st.write("**학생명**")
        with row1_2:
            st.write(f"{selected_name}")

        # 2행: 파일명
        row2_1, row2_2 = st.columns(col_ratio)
        with row2_1:
            st.write("**파일명**")
        with row2_2:
            st.write(f"{selected_name}")

        # 3행: 상태
        row3_1, row3_2 = st.columns(col_ratio)
        with row3_1:
            st.write("**상태**")
        with row3_2:
            st.markdown(":green[분석 완료]")

        # 4행: 최종 점수
        row4_1, row4_2 = st.columns(col_ratio)
        with row4_1:
            st.write("**최종 점수**")
        with row4_2:
            # 점수 부분만 조금 더 강조
            st.write(f"**{round(d['total_score'], 1)}** / 100")

    with st.expander("통합 분석 그래프", expanded=True):
        st.markdown("""
            <style>
            /* 특정 컨테이너 안의 버튼만 변경 */
            div.metric-btn-container div.stButton > button {
                width: 100%;
                height: 120px;
                border-radius: 15px;
                border: 2px solid #f0f2f6;
                transition: all 0.3s;
                background-color: #ffffff;
                color: black; /* 텍스트 색상 고정 */
            }
            
            /* 호버 및 활성화 상태 스타일 */
            div.metric-btn-container div.stButton > button:hover {
                border-color: #4C6EF5;
                background-color: #f8f9fa;
            }

            /* 일반 버튼(예: 다른 곳의 버튼)은 영향을 받지 않음 */
            </style>
        """, unsafe_allow_html=True)

        for key in ["pitch_on", "rms_on", "timing_on"]:
            if key not in st.session_state:
                st.session_state[key] = True  # 기본값은 ON

        def toggle_state(key):
            st.session_state[key] = not st.session_state[key]

        st.caption("그래프 하단의 슬라이더를 움직여 원하는 구간을 확대하거나 반복해서 들어보세요.")

        empty_left, col1, col2, col3, empty_right = st.columns([4, 2, 2, 2, 4], gap="medium")

        with col1:
            st.markdown('<div class="metric-btn-container">', unsafe_allow_html=True)
            # 상태에 따른 아이콘 색상 결정 (꺼져있으면 회색)
            p_color = "#007bff" if st.session_state.pitch_on else "#dee2e6"
            p_label = f"### {'🔵' if st.session_state.pitch_on else '⚪'} 음정\n## {round(d['pitch_acc'], 1)}점"
            if st.button(p_label, key="btn_pitch"):
                toggle_state("pitch_on")
                st.rerun()

        with col2:
            st.markdown('<div class="metric-btn-container">', unsafe_allow_html=True)
            r_color = "#28a745" if st.session_state.rms_on else "#dee2e6"
            r_label = f"### {'🟢' if st.session_state.rms_on else '⚪'} 강약\n## {round(d['rms_acc'],1)}점"
            if st.button(r_label, key="btn_rms"):
                toggle_state("rms_on")
                st.rerun()

        with col3:
            st.markdown('<div class="metric-btn-container">', unsafe_allow_html=True)
            t_color = "#dc3545" if st.session_state.timing_on else "#dee2e6"
            t_label = f"### {'🔴' if st.session_state.timing_on else '⚪'} 박자\n## {round(d['timing_acc'], 1)}점"
            if st.button(t_label, key="btn_timing"):
                toggle_state("timing_on")
                st.rerun()

        pitch_tick_mode = st.selectbox(
            "🎼 음정 축 눈금 표시",
            ["간단(자연음만)", "중간(2반음 간격)", "전체(반음 전체)"],
            index=0
        )


        # 1. 기존 변수를 세션 상태 변수로 매핑 (가독성을 위해)
        show_pitch = st.session_state.pitch_on
        show_rms = st.session_state.rms_on
        show_timing = st.session_state.timing_on

        # ✅ 축 기준 승격 로직 (토글 조합에서도 강약/박자 정상 표시)
        if show_pitch:
            base_mode = "pitch"
        elif show_rms:
            base_mode = "rms"
        else:
            base_mode = "timing"

        # Plotly 적용
        fig = go.Figure()

        # 음정 노트(hover/축용)
        valid_pitch = ref_pitch[~np.isnan(ref_pitch)]
        p_min, p_max = (int(np.nanmin(valid_pitch)) - 1, int(np.nanmax(valid_pitch)) + 1) if len(valid_pitch) > 0 else (60, 72)
        note_map = get_flute_note_names(p_min, p_max)

        ref_notes = [note_map.get(int(round(p)), "N/A") if not np.isnan(p) else "N/A" for p in ref_pitch]
        user_notes = [note_map.get(int(round(p)), "N/A") if not np.isnan(p) else "N/A" for p in u_pitch]
        ref_dyns = [get_dyn_label(v) for v in ref_rms]
        user_dyns = [get_dyn_label(v) for v in u_rms]

        # --- trace 추가: base_mode 기준으로 y/y2/y3 재배치 ---
        if base_mode == "pitch":
            if show_pitch:
                fig.add_trace(go.Scatter(x=times, y=ref_pitch, name="🎹 목표 음정",
                                        line=dict(color="#A0A0A0", dash="dash", width=1.5),
                                        customdata=ref_notes, hovertemplate="목표: %{customdata}<extra></extra>",
                                        yaxis="y", legendgroup="pitch"))
                fig.add_trace(go.Scatter(x=times, y=u_pitch, name="🎹 내 연주 음정",
                                        line=dict(color="#4C6EF5", width=3),
                                        customdata=user_notes, hovertemplate="내 연주: %{customdata}<extra></extra>",
                                        yaxis="y", legendgroup="pitch"))
            if show_rms:
                fig.add_trace(go.Scatter(x=times, y=ref_rms, name="🔊 목표 세기",
                                        line=dict(color="#D0D0D0", dash="dot", width=1),
                                        customdata=ref_dyns, hovertemplate="목표 세기: %{customdata}<extra></extra>",
                                        yaxis="y2", legendgroup="rms"))
                fig.add_trace(go.Scatter(x=times, y=u_rms, name="🔊 내 연주 세기",
                                        line=dict(color="#12B886", width=2),
                                        fill='tonexty', fillcolor='rgba(18,184,134,0.08)',
                                        customdata=user_dyns, hovertemplate="내 세기: %{customdata}<extra></extra>",
                                        yaxis="y2", legendgroup="rms"))
            if show_timing:
                fig.add_trace(go.Scatter(x=[times[0], times[-1]], y=[0, 0], name="⏱️ 박자 기준 (0s)",
                                        line=dict(color="#FA9595", width=2, dash="dot"),
                                        hoverinfo="skip", yaxis="y3", legendgroup="timing"))
                fig.add_trace(go.Scatter(x=times, y=t_errors, name="⏱️ 박자 편차",
                                        line=dict(color="#FF4B4B", width=1.5),
                                        hovertemplate="박자 편차: %{y:.3f}s<extra></extra>",
                                        yaxis="y3", legendgroup="timing"))

        elif base_mode == "rms":
            if show_rms:
                fig.add_trace(go.Scatter(x=times, y=ref_rms, name="🔊 목표 세기",
                                        line=dict(color="#D0D0D0", dash="dot", width=1),
                                        customdata=ref_dyns, hovertemplate="목표 세기: %{customdata}<extra></extra>",
                                        yaxis="y", legendgroup="rms"))
                fig.add_trace(go.Scatter(x=times, y=u_rms, name="🔊 내 연주 세기",
                                        line=dict(color="#12B886", width=2),
                                        fill='tonexty', fillcolor='rgba(18,184,134,0.08)',
                                        customdata=user_dyns, hovertemplate="내 세기: %{customdata}<extra></extra>",
                                        yaxis="y", legendgroup="rms"))
            if show_timing:
                fig.add_trace(go.Scatter(x=[times[0], times[-1]], y=[0, 0], name="⏱️ 박자 기준 (0s)",
                                        line=dict(color="#FA9595", width=2, dash="dot"),
                                        hoverinfo="skip", yaxis="y2", legendgroup="timing"))
                fig.add_trace(go.Scatter(x=times, y=t_errors, name="⏱️ 박자 편차",
                                        line=dict(color="#FF4B4B", width=1.5),
                                        hovertemplate="박자 편차: %{y:.3f}s<extra></extra>",
                                        yaxis="y2", legendgroup="timing"))

        else:
            if show_timing:
                fig.add_trace(go.Scatter(x=[times[0], times[-1]], y=[0, 0], name="⏱️ 박자 기준 (0s)",
                                        line=dict(color="#FA9595", width=2, dash="dot"),
                                        hoverinfo="skip", yaxis="y", legendgroup="timing"))
                fig.add_trace(go.Scatter(x=times, y=t_errors, name="⏱️ 박자 편차",
                                        line=dict(color="#FF4B4B", width=1.5),
                                        hovertemplate="박자 편차: %{y:.3f}s<extra></extra>",
                                        yaxis="y", legendgroup="timing"))

        # --- 축 설정 ---
        pos_y = 0.0
        pos_y2 = 0.03
        pos_y3 = 0.06

        pitch_tickvals, pitch_ticktext = make_pitch_ticks(note_map, pitch_tick_mode)

        layout_kwargs = dict(
            # width=1250,
            # height=750,
            autosize=True,
            # margin=dict(t=60, b=40, l=110, r=50),
            margin=dict(t=30, b=40, l=0, r=0),
            template="plotly_white",
            hovermode="x unified",
            dragmode='pan',
            # dragmode=False,
            # selectdirection = 'h'
            uirevision='constant',
            clickmode='event',
            legend=dict(
                orientation="h",
                yanchor="bottom", y=1,
                xanchor="right", x=1,
                bgcolor="rgba(255,255,255,0.8)",
                bordercolor="rgba(0,0,0,0.1)",
                borderwidth=1,
                groupclick="togglegroup"
            ),
            xaxis=dict(
                title="시간 (초)",
                domain=[0.11, 0.98],
                rangeslider=dict(visible=True, thickness=0.04),
                type="linear",
                showgrid=True, 
                fixedrange=False,
                gridcolor="rgba(230,230,230,0.5)"
            ),
        )

        annotations = []
        if base_mode == "pitch":
            if show_pitch:
                annotations.append(dict(x=pos_y, y=1.05, xref='paper', yref='paper', text="<b>음정</b>",
                                        showarrow=False, font=dict(color="#4C6EF5", size=12), xanchor='center'))
            if show_rms:
                annotations.append(dict(x=pos_y2, y=1.05, xref='paper', yref='paper', text="<b>세기</b>",
                                        showarrow=False, font=dict(color="#12B886", size=12), xanchor='center'))
            if show_timing:
                annotations.append(dict(x=pos_y3, y=1.05, xref='paper', yref='paper', text="<b>박자</b>",
                                        showarrow=False, font=dict(color="#FF4B4B", size=12), xanchor='center'))

            layout_kwargs.update(dict(
                yaxis=dict(
                    tickvals=pitch_tickvals, ticktext=pitch_ticktext,
                    side="left", visible=show_pitch,
                    autorange=True, fixedrange=True,
                    tickfont=dict(color="#4C6EF5", size=9),
                    anchor="free", position=pos_y, automargin=True
                ),
                yaxis2=dict(
                    side="left", visible=show_rms,
                    autorange=True, fixedrange=True,
                    tickfont=dict(color="#12B886", size=9),
                    anchor="free", overlaying="y", position=pos_y2
                ),
                yaxis3=dict(
                    side="left", visible=show_timing,
                    autorange=True, fixedrange=True,
                    tickfont=dict(color="#FF4B4B", size=9),
                    anchor="free", overlaying="y", position=pos_y3,
                    zeroline=False, range=[-1.2, 1.2]
                )
            ))

        elif base_mode == "rms":
            if show_rms:
                annotations.append(dict(x=pos_y, y=1.02, xref='paper', yref='paper', text="<b>세기</b>",
                                        showarrow=False, font=dict(color="#12B886", size=12), xanchor='center'))
            if show_timing:
                annotations.append(dict(x=pos_y2, y=1.02, xref='paper', yref='paper', text="<b>박자</b>",
                                        showarrow=False, font=dict(color="#FF4B4B", size=12), xanchor='center'))

            layout_kwargs.update(dict(
                yaxis=dict(
                    side="left", visible=show_rms,
                    autorange=True, fixedrange=True,
                    tickfont=dict(color="#12B886", size=9),
                    anchor="free", position=pos_y, automargin=True
                ),
                yaxis2=dict(
                    side="left", visible=show_timing,
                    autorange=True, fixedrange=True,
                    tickfont=dict(color="#FF4B4B", size=9),
                    anchor="free", overlaying="y", position=pos_y2,
                    zeroline=False, range=[-1.2, 1.2]
                )
            ))

        else:
            if show_timing:
                annotations.append(dict(x=pos_y, y=1.02, xref='paper', yref='paper', text="<b>박자</b>",
                                        showarrow=False, font=dict(color="#FF4B4B", size=12), xanchor='center'))

            layout_kwargs.update(dict(
                yaxis=dict(
                    side="left", visible=show_timing,
                    autorange=True, fixedrange=True,
                    tickfont=dict(color="#FF4B4B", size=9),
                    anchor="free", position=pos_y, automargin=True,
                    zeroline=False, range=[-1.2, 1.2]
                )
            ))

        fig.update_layout(annotations=annotations, **layout_kwargs)


        # --- Plotly를 "inline JS 포함 HTML"로 생성 (CDN 불필요) ---
        plot_html = pio.to_html(
            fig,
            include_plotlyjs="inline",
            full_html=False,
            config={'scrollZoom': True, 'displaylogo': False, 'displayModeBar': False, 'responsive': True}
        )

        audio_uri_a = to_data_uri(d['audio_bin_a'])
        audio_uri_b = to_data_uri(d['audio_bin_b'])
        audio_uri_stereo = to_data_uri(d['audio_bin_stereo'])
        
        st_time_select(plot_html, audio_uri_a, audio_uri_b, audio_uri_stereo)