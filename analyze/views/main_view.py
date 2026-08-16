import streamlit as st
import streamlit.components.v1 as components

import librosa

import numpy as np
from scipy.signal import medfilt, windows
from scipy.ndimage import convolve1d
import matplotlib.pyplot as plt
import pandas as pd

from pathlib import Path
import os
import io
import re

import plotly.graph_objects as go
import json  # 추가
import base64 # 음원 데이터 인코딩

from process.audioprocess import make_audio_process

import time  # 시간 측정용
from concurrent.futures import ProcessPoolExecutor # 병렬 처리용

# --- [1. 환경 설정 및 경로] ---
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False

VIDEO_P3 = "./input/flute_comp_1_a.mp4"
VIDEO_P3_URL = "https://youtu.be/v9FI5QF0YaM"

VIDEO_USER = "./input/flute_comp_1_c.mp4"
VIDEO_USER_URL = "https://youtu.be/o6Pi0MEjXS8"

# 분석용 샘플링 레이트 (속도 향상을 위해 22050으로 하향 조정)
ANALYSIS_SR = 16000 #22050 
ORIGINAL_SR = 44100

def encode_bytes(b_data):
    # bytes -> base64 string 변환
    if b_data and isinstance(b_data, bytes):
        return base64.b64encode(b_data).decode('utf-8')
    return None

# --- [추가 유틸리티: JSON 변환 함수] ---
def convert_to_json(v_data):
    times, ref, u_pitch, u_rms, t_errors, df_err, pitch_acc, rms_acc, timing_acc, total_score, audio_bin_a, audio_bin_b, audio_bin_stereo, video_a_url, video_b_url = v_data
    data_dict = {
        "times": times.tolist(),
        "ref_pitch": ref['pitch'].tolist(),
        "ref_rms": ref['rms'].tolist(),
        "u_pitch": u_pitch.tolist(),
        "u_rms": u_rms.tolist(),
        "t_errors": t_errors.tolist(),
        "df_err": df_err.to_dict(orient='records'),
        "pitch_acc": float(pitch_acc),
        "rms_acc": float(rms_acc),
        "timing_acc": float(timing_acc),
        "total_score": float(total_score),
        "audio_bin_a" : encode_bytes(audio_bin_a),
        "audio_bin_b" : encode_bytes(audio_bin_b),
        "audio_bin_stereo" : encode_bytes(audio_bin_stereo),
        "video_a_url": video_a_url,
        "video_b_url": video_b_url
    }
    return json.dumps(data_dict)

# 파일 읽기 전용 함수 정의
def read_file(filename):
    # 현재 파일(dashboard.py)의 절대 경로를 가져옴
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 상위 폴더(your_project/)로 올라가서 static 폴더 경로를 생성
    project_root = os.path.dirname(current_dir)
    file_path = os.path.join(project_root, "static", "main_view", filename)
    
    if not os.path.exists(file_path):
        print(f"Error: File not found at {file_path}")
        return ""
        
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def st_time_select(video_id_a, video_id_b):
    # 웹문서 파일 호출
    html_tpl = read_file("main_component.html")
    js_content = read_file("main_script.js")

    js_content = js_content.replace("{id_a}", video_id_a)
    js_content = js_content.replace("{id_b}", video_id_b)

    final_html = html_tpl.replace("{{CUSTOM_JS}}", js_content)

    components.html(final_html, height=550)

def play_synced_youtube(url_a, url_b):
    def extract_id(url):
        regex = r"(?:v=|\/|be\/)([0-9A-Za-z_-]{11})"
        match = re.search(regex, url)
        return match.group(1) if match else None

    id_a = extract_id(url_a)
    id_b = extract_id(url_b)

    if not id_a or not id_b:
        return "유효한 유튜브 URL을 입력해 주세요."

    st_time_select(id_a, id_b)


# --- [2. 분석 엔진 함수: 속도 최적화] ---
def analyze_features_core(audio_bin):
    wav_file_like = io.BytesIO(audio_bin)
    # 16kHz로 로드하여 데이터 포인트 최소화
    y, sr = librosa.load(wav_file_like, sr=ANALYSIS_SR, mono=True)
    
    # HPSS 생략 가능 (속도를 위해 원본 y 사용 고려, 여기서는 margin 조절)
    y_harmonic, _ = librosa.effects.hpss(y, margin=4.0) 
    
    # [핵심] pyin 파라미터 경량화
    # hop_length=1024: 연산 지점 절반 감소
    # n_thresholds=20: 탐색 정밀도 조정 (속도 향상)
    f0, voiced_flag, voiced_probs = librosa.pyin(
        y_harmonic, 
        fmin=librosa.note_to_hz('C4'), 
        fmax=librosa.note_to_hz('C8'), 
        sr=sr,
        hop_length=1024,
        n_thresholds=20
    )
    
    pitch_midi = librosa.hz_to_midi(f0)
    pitch_midi[voiced_probs < 0.4] = np.nan
    
    # 보간법을 'linear'로 변경 (cubic보다 빠름)
    pitch_series = pd.Series(pitch_midi).interpolate(method='linear').ffill().bfill()
    
    # 필터 크기 축소 (데이터 포인트가 줄었으므로 kernel_size도 낮춤)
    pitch_med = medfilt(pitch_series.values, kernel_size=21) 
    gauss_win = windows.gaussian(15, std=5)
    pitch_final = convolve1d(pitch_med, gauss_win/gauss_win.sum(), mode='nearest')
    
    # RMS 연산에도 동일한 hop_length 적용
    rms = librosa.feature.rms(y=y_harmonic, hop_length=1024)[0]
    rms = (rms - np.min(rms)) / (np.max(rms) - np.min(rms) + 1e-6)
    
    return {
        "pitch": pitch_final, 
        "rms": rms, 
        "times": np.arange(len(pitch_final)) * (1024 / sr), 
        "y": y, 
        "sr": sr
    }

@st.cache_data
def run_parallel_analysis(bin_a, bin_b):
    """두 음원을 동시에 분석하여 시간 단축"""
    with ProcessPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(analyze_features_core, bin_a)
        future_b = executor.submit(analyze_features_core, bin_b)
        return future_a.result(), future_b.result()

# --- [3. UI 구성 및 메인 로직] ---
st.title("🎶 플루트 연주 구간별 통합 분석 대시보드")

if not (os.path.exists(VIDEO_P3) and os.path.exists(VIDEO_USER)):
    st.info(
        "🎥 이 배포 환경에는 용량 문제로 원본 비교 영상이 포함되어 있지 않습니다.\n\n"
        "분석 결과 데모는 왼쪽 메뉴의 **Dashboard** 페이지에서 확인하실 수 있습니다."
    )
    st.stop()

if st.button("🚀 구간별 정밀 분석 시작"):
    start_time = time.time() # 전체 분석 시작 시간 측정
    with st.spinner("데이터 분석 중..."):
        audio_bin_a, audio_bin_b, audio_bin_stereo = make_audio_process(VIDEO_P3, VIDEO_USER, ANALYSIS_SR)

        ref = analyze_features_core(audio_bin_a)
        user = analyze_features_core(audio_bin_b)

        if ref and user:
            D, wp = librosa.sequence.dtw(X=ref['pitch'], Y=user['pitch'], metric='euclidean')
            path = wp[::-1]
            ref_idx, user_idx = path[:, 0], path[:, 1]
            
            u_pitch_raw = np.array([np.mean(user['pitch'][user_idx[ref_idx == i]]) if np.any(ref_idx == i) else 0 for i in range(len(ref['pitch']))])
            u_rms = np.array([np.mean(user['rms'][user_idx[ref_idx == i]]) if np.any(ref_idx == i) else 0 for i in range(len(ref['pitch']))])
            
            u_pitch = u_pitch_raw.copy()
            for i in range(len(u_pitch)):
                diff = u_pitch[i] - ref['pitch'][i]
                if abs(diff) > 6: u_pitch[i] -= (round(diff / 12) * 12)
            u_pitch = u_pitch - np.mean(u_pitch - ref['pitch'])

            timing_errors = []
            for i in range(len(ref['pitch'])):
                m_frames = user_idx[ref_idx == i]
                timing_errors.append((np.mean(m_frames) - i) * (512 / ANALYSIS_SR) if len(m_frames) > 0 else 0)
            timing_errors = medfilt(timing_errors, kernel_size=31)
            times = ref['times']

            pitch_acc = 100 - (np.mean(np.abs(np.round(u_pitch) - np.round(ref['pitch']))) * 20)
            rms_acc = max(0, 100 - np.mean(np.abs(u_rms - ref['rms'])) * 100)
            # sigma가 0.04(40ms)라면 음악적으로 꽤 엄격한 기준입니다.
            sigma = 0.04 
            # 정확도 계산 (가우시안 함수 적용)
            acc_array = 100 * np.exp(-(timing_errors**2) / (2 * (sigma**2)))
            # 3. 전체 평균 정확도 산출
            timing_acc = np.mean(acc_array)


            # 전체 구간으로 변경
            errors = []
            for start_t in np.arange(0, times[-1], 5.0):
                mask = (times >= start_t) & (times < start_t + 5.0)
                if not np.any(mask): continue
                if np.any(np.abs(np.round(u_pitch[mask]) - np.round(ref['pitch'][mask])) >= 1.0) or \
                   np.any(np.abs(u_rms[mask] - ref['rms'][mask]) > 0.20) or \
                   np.any(np.abs(timing_errors[mask]) > 0.1):
                    items = []
                    if np.any(np.abs(np.round(u_pitch[mask]) - np.round(ref['pitch'][mask])) >= 1.0): items.append("🎹 음정")
                    if np.any(np.abs(u_rms[mask] - ref['rms'][mask]) > 0.20): items.append("🔊 세기")
                    if np.any(np.abs(timing_errors[mask]) > 0.03): items.append("⏱️ 박자")
                    errors.append({"구간": f"{round(start_t, 1)}s ~ {round(start_t + 5.0, 1)}s", "중심시간": round(start_t + 2.5, 1), "항목": ", ".join(items), "코칭": f"{', '.join(items)} 불일치 지점"})

            st.session_state['v_data'] = (
                times, 
                ref, 
                u_pitch, 
                u_rms, 
                timing_errors, 
                pd.DataFrame(errors), 
                pitch_acc,
                rms_acc,
                timing_acc,
                (pitch_acc*0.4 + rms_acc*0.2 + timing_acc*0.4), 
                audio_bin_a,
                audio_bin_b,
                audio_bin_stereo,
                VIDEO_P3_URL,
                VIDEO_USER_URL,
            )

            end_time = time.time()
            duration = round(end_time - start_time, 2)
            st.success(f"✅ 분석 완료! (총 소요 시간: {duration}초)")

# --- [4. 결과 표시 영역: 기존 기능 완전 유지] ---
if 'v_data' in st.session_state:
    times, ref, u_pitch, u_rms, t_errors, df_err, pitch_acc, rms_acc, timing_acc, total_score, enc_audio_bin_a, enc_audio_bin_b, enc_audio_bin_stereo, VIDEO_P3_URL, VIDEO_USER_URL = st.session_state['v_data']

    col_score, col_download = st.columns([4, 1])

    with col_score:
        st.subheader(f"📊 종합 분석 점수: {round(total_score, 1)} / 100")

    with col_download:
        st.write("")
        st.write("")
        st.write("")
        st.write("")
        json_data = convert_to_json(st.session_state['v_data'])
        st.download_button(
            label="💾 분석 결과 JSON으로 다운로드",
            data=json_data,
            file_name="student_analysis.json",
            mime="application/json"
        )

    st.markdown('<hr style="margin-top: -10px; border: 1px solid #eee;">', unsafe_allow_html=True)

    

    st.subheader(f"🎵 음원 비교")
    ac1, ac2 = st.columns(2)
    with ac1: 
        st.write("🎯 **정답 연주 (Reference)**")
        st.audio(enc_audio_bin_a, format='audio/mp3')
    with ac2: 
        st.write("✨ **동기화된 나의 연주 (Reduced Phasiness)**")
        st.audio(enc_audio_bin_b, format='audio/mp3')


    _, col2, _ = st.columns([1, 2, 1])
    with col2:
    # 텍스트 스타일 정의 및 중앙 정렬
        st.markdown(
            """
            <div style='text-align: center; margin-bottom: 10px;'>
                <p style='font-size: 18px; font-weight: bold; margin-bottom: 5px;'>
                    🎧 비교 음원 (왼쪽: 기준 | 오른쪽: 이용자)
                </p>
                <p style='font-size: 14px; color: #ff4b4b; font-weight: normal;'>
                    ⚠️ 정확한 비교를 위해 반드시 <b>이어폰이나 헤드셋</b>을 착용해 주세요.
                </p>
            </div>
            """, 
            unsafe_allow_html=True
        )
        
        # 오디오 플레이어 배치
        st.audio(enc_audio_bin_stereo, format='audio/mp3')
    
    st.markdown("---")
    st.subheader(f"🎬 영상 비교")
    play_synced_youtube(VIDEO_P3_URL, VIDEO_USER_URL)
    
    