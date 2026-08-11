from pydub import AudioSegment

import subprocess
import io

import librosa

import numpy as np
from array import array

# 시작/끝점 탐색
def get_audio_bounds(path, sample_rate, top_db=30):
    """
    영상/음원 파일 경로를 입력받아 음의 시작과 끝 시간을 반환합니다.
    
    Args:
        path (str): 파일 경로 (mp4, wav 등)
        top_db (int): 무음으로 간주할 기준 데시벨. 
                      값이 낮을수록(예: 30) 더 엄격하게(작은 소리도 무음 처리) 자릅니다.
    
    Returns:
        tuple: (시작 시간(초), 끝 시간(초), 전체 유효 길이(초))
    """
    # 1. 파일 로드 (sr=None으로 설정하여 원본 샘플링 레이트 유지)
    y, sr = librosa.load(path, sr=sample_rate)
    
    # 2. 유효 구간 탐색 (trim 함수 사용)
    # y_trimmed: 잘려진 데이터, index: [시작 샘플 인덱스, 끝 샘플 인덱스]
    _, index = librosa.effects.trim(y, top_db=top_db)
    
    # 3. 샘플 인덱스를 시간(초) 단위로 변환
    start_time = index[0] / sr
    end_time = index[1] / sr
    duration = end_time - start_time
    
    return start_time, end_time, duration

def calculate_speed_rate(dur_a, dur_b):
    """
    영상 B를 영상 A의 길이에 맞추기 위한 배속값을 계산합니다.
    """
    # 예시 1: A는 10초, B는 12초일 때 (B를 빠르게 만들어야 함)
    # rate = 12 / 10 = 1.2 (1.2배속)

    # 예시 2: A는 10초, B는 8초일 때 (B를 느리게 만들어야 함)
    # rate = 8 / 10 = 0.8 (0.8배속)

    if dur_a <= 0 or dur_b <= 0:
        raise ValueError("Duration은 0보다 커야 합니다.")
        
    rate = dur_b / dur_a
    
    return rate



# 오디오 추출
def generate_processed_audio_bin(video_path, start_time, end_time, speed_rate, sample_rate):
    """
    (1) 특정 구간 추출, (2) 배속 적용, (3) WAV 이진 데이터 생성
    """
    # 배속 필터 구성 (atempo는 0.5 ~ 2.0 사이만 지원하므로 범위를 벗어날 경우 체이닝 필요)
    def get_atempo_filter(rate):
        if 0.5 <= rate <= 2.0:
            return f"atempo={rate}"
        # 2.0배속을 넘어가면 중첩 (예: 4.0배속 -> atempo=2.0,atempo=2.0)
        filters = []
        temp_rate = rate
        while temp_rate > 2.0:
            filters.append("atempo=2.0")
            temp_rate /= 2.0
        while temp_rate < 0.5:
            filters.append("atempo=0.5")
            temp_rate /= 0.5
        filters.append(f"atempo={temp_rate}")
        return ",".join(filters)

    filter_str = get_atempo_filter(speed_rate)

    # FFmpeg 명령어 구성
    command = [
        'ffmpeg',
        '-ss', str(start_time),    # 시작점 (초)
        '-to', str(end_time),      # 끝점 (초)
        '-i', video_path,          # 입력 영상 (raw data)
        '-vn',                     # 비디오 스트림 제외
        '-filter:a', filter_str,   # 배속 적용 (음정 유지)
        # wav
        # '-acodec', 'pcm_s16le',    # 16비트 PCM (WAV 표준)

        # mp3
        '-acodec', 'libmp3lame',      # MP3 코덱 사용 (LAME)
        '-ab', '192k',                # ★ 비트레이트 192kbps 설정
        
        '-ar', str(sample_rate),   # 샘플링 레이트 설정
        '-ac', '2',                # 스테레오 설정
        # '-f', 'wav',               # 컨테이너 포맷 강제
        '-f', 'mp3',
        'pipe:1'                   # 표준 출력으로 스트리밍
    ]

    # 프로세스 실행 및 바이너리 획득
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()

    if process.returncode != 0:
        raise Exception(f"FFmpeg 에러: {stderr.decode()}")

    return stdout


def merge_to_stereo_mp3_binary(wav_bin_a, wav_bin_b, bitrate="192k"):
    # 1. 오디오 로드
    audio_a = AudioSegment.from_file(io.BytesIO(wav_bin_a)).set_channels(1)
    audio_b = AudioSegment.from_file(io.BytesIO(wav_bin_b)).set_channels(1)

    # 2. 샘플 배열 추출
    samples_a = audio_a.get_array_of_samples()
    samples_b = audio_b.get_array_of_samples()

    # 3. 샘플 개수 강제 일치 (부족한 만큼 0으로 채우거나 자르기)
    len_a = len(samples_a)
    len_b = len(samples_b)
    target_len = max(len_a, len_b) # 더 긴 쪽에 맞춤 (또는 min을 써서 짧은 쪽에 맞춤)

    def adjust_samples(samples, target_length):
        if len(samples) < target_length:
            # 부족하면 0(무음)으로 패딩
            return samples + array(samples.typecode, [0] * (target_length - len(samples)))
        else:
            # 길면 자르기
            return samples[:target_length]

    samples_a = adjust_samples(samples_a, target_len)
    samples_b = adjust_samples(samples_b, target_len)

    # 4. 일치된 샘플로 다시 AudioSegment 생성
    audio_a = audio_a._spawn(samples_a)
    audio_b = audio_b._spawn(samples_b)

    # 5. 이제 샘플 수가 완벽히 동일하므로 에러가 발생하지 않습니다.
    stereo_audio = AudioSegment.from_mono_audiosegments(audio_a, audio_b)

    # 6. 결과 내보내기
    out_buffer = io.BytesIO()
    stereo_audio.export(out_buffer, format="mp3", bitrate=bitrate)
    
    return out_buffer.getvalue()


# 메인에서 해당 함수에 영상파일 경로를 전달하며 호출
def make_audio_process(video_a, video_b, sr):
    # 영상 경계 정보 수집
    s_a, e_a, dur_a = get_audio_bounds(video_a, sr)
    s_b, e_b, dur_b = get_audio_bounds(video_b, sr)

    speed_rate = calculate_speed_rate(dur_a, dur_b)

    audio_bin_a = generate_processed_audio_bin(video_a, s_a, e_a, 1.0, sr)
    audio_bin_b = generate_processed_audio_bin(video_b, s_b, e_b, speed_rate, sr)

    # a_stereo = merge_to_stereo_wav_binary(wav_bin_a, wav_bin_b)
    audio_stereo = merge_to_stereo_mp3_binary(audio_bin_a, audio_bin_b)

    return audio_bin_a, audio_bin_b, audio_stereo