(function() {
    // Plotly 객체 찾기       
    const plotDiv = document.querySelector('.js-plotly-plot');
    if (!plotDiv) {
        console.error("Plotly graph div not found");
        return;
    }

    // 로드 전: 그래프 영역을 흐리게 만들고 클릭 방지
    plotDiv.style.pointerEvents = 'none'; // 클릭/드래그 차단
    plotDiv.style.opacity = '0.5';       // 시각적 비활성화 표시


    // 오디오 속성 가져오기
    const selected_time = document.getElementById("sel_t");
    const audioA = document.getElementById('audio_a');
    const audioB = document.getElementById('audio_b');
    const audioStereo = document.getElementById('audio_stereo');
    
    const audios = [audioA, audioB, audioStereo];
    
    // 소스 할당
    audioA.src = "{audio_uri_a}";
    audioB.src = "{audio_uri_b}";
    audioStereo.src = "{audio_uri_stereo}";
    
    // 오디오 초기 로드
    audios.forEach(audio => {
        audio.load()
    });
    audioA.muted = true;
    audioB.muted = false;
    audioStereo.muted = true;
    
    // 오디오 구간 적용 및 UI 업데이트 함수
    function applyAudioRange() {
        if (!isNaN(audioA.duration)) {
            audio_cont_btn.disabled = false;
            audio_cont_btn.classList.remove('btn-adjusting');

            resetAudioButton(); // 일시정지 상태로 초기화

            // 위치 이동 및 루프 설정
            audios.forEach(audio => {
                audio.currentTime = start;
            });
            setupLoopPlayback();
        }

        selected_time.textContent = start.toFixed(2);
        // console.log(`반복 구간 설정 완료: ${start}s ~ ${end}s`);
    }

    audioA.addEventListener('loadedmetadata', () => {
        duration = audioA.duration;
        // console.log("로드된 duration:", duration);

        // 초기값 설정
        start = 0;
        end = duration;
        updateRangeUI();

        // 로드 완료: 원래 상태로 복구
        plotDiv.style.pointerEvents = 'auto';
        plotDiv.style.opacity = '1';

        // Plotly 이벤트 리스너
        plotDiv.on('plotly_relayout', function(eventData) {
            const isSliderAction = eventData['xaxis.range'] !== undefined ||
                eventData['xaxis.range[0]'] !== undefined ||
                eventData['xaxis.autorange'] !== undefined;

            if (!isSliderAction) return;

            // UI 잠금 및 일시정지 (드래그 중 소리 겹침 방지)
            audios.forEach(audio => audio.pause());

            // 범위 값 업데이트
            if (eventData['xaxis.range']) {
                start = Math.max(0, eventData['xaxis.range'][0]);
                end = Math.min(eventData['xaxis.range'][1], duration);
            } else if (eventData['xaxis.range[0]']) {
                start = Math.max(0, eventData['xaxis.range[0]']);
                end = Math.min(eventData['xaxis.range[1]'], duration);
            }

            gap = end - start;

            // [수정] 타이머 없이 변경된 값을 즉시 적용
            applyAudioRange();
            updateRangeUI();
        });
    });

    plotDiv.on('plotly_doubleclick', function() {
        console.log("그래프가 더블클릭 되었습니다!");
        
        // 예: 더블클릭 시 start, end 구간을 초기화
        start = 0;
        end = duration; 
        
        // 그래프와 UI 업데이트
        Plotly.relayout(plotDiv, {
            'xaxis.range': [start, end]
        });
        updateRangeUI();
        
        // 기본 동작(오토줌)을 막고 싶다면 false 반환 (상황에 따라 다름)
        return false; 
    });

    // 음원 길이
    let duration;
    
    // 반복 구간의 시작점과 끝점
    let start, end;
    
    // 시간 간격 (end-start)
    let gap;

    // 초기값
    // 볼륨: 0.8
    // 배속: 1.0

    // 볼륨 조절 속성
    const vol = document.getElementById('vol');
    const volVal = document.getElementById('vol_val');
    
    // 배속 조절 속성
    const rate = document.getElementById('rate');
    const rateVal = document.getElementById('rate_val');


    // 커스텀 프로그레스바 제어 요소
    const rangeHighlight = document.getElementById('rangeHighlight');
    const progress = document.getElementById('progressBar');
    const currentTimeText = document.getElementById('currentTime');

    function updateRangeUI() {
        if (!duration) return;

        // 전체 길이에 대한 start와 end의 비율 계산
        const startPercent = (start / duration) * 100;
        const endPercent = (end / duration) * 100;
        const widthPercent = endPercent - startPercent;

        // 하이라이트 요소의 위치와 너비 설정
        rangeHighlight.style.left = `${startPercent}%`;
        rangeHighlight.style.width = `${widthPercent}%`;
    }

    // 위치 계산 및 UI 업데이트 공통 함수
    function handleProgressChange(e) {
        if (!duration) return;

        const rect = progressContainer.getBoundingClientRect();
        let clickX = e.clientX - rect.left; // 컨테이너 왼쪽 끝으로부터의 거리
        const containerWidth = rect.width;

        // 범위를 0 ~ 100% 사이로 제한 (바 밖으로 나가는 것 방지)
        let ratio = clickX / containerWidth;
        ratio = Math.max(0, Math.min(1, ratio));

        const targetTime = ratio * duration;

        // 선택 범주에 따른 그래프 구간 평행이동
        // targetTime < start
        if (targetTime < start) {
            start = targetTime;
            end = Math.min(duration, targetTime + gap);
            Plotly.relayout(plotDiv, {
                'xaxis.range': [start, end]
            });

            // UI 업데이트 및 실제 오디오 시간 변경
            updateProgressUI(targetTime);
            updateRangeUI();
            applyAudioRange();
            seekTo(targetTime);
        }
        // start <= targetTime <= end
        else if (start <= targetTime && targetTime <= end) {
            // no range change 
            updateProgressUI(targetTime);
            seekTo(targetTime);
        }
        // end < targetTime
        else {
            start = Math.max(0, targetTime - gap);
            end = targetTime;
            // end = Math.min(duration, targetTime + gap);
            Plotly.relayout(plotDiv, {
                'xaxis.range': [start, end]
            });

            // UI 업데이트 및 실제 오디오 시간 변경
            updateProgressUI(targetTime);
            updateRangeUI();
            applyAudioRange();
            seekTo(targetTime);
        }
    }

    let isDragging = false;
    // 클릭한 위치에 해당하는 음원 시간으로 이동하는 함수
    // 1. 마우스를 눌렀을 때
    progressContainer.addEventListener('mousedown', (e) => {
        isDragging = true;
        handleProgressChange(e); // 클릭한 지점으로 즉시 이동
    });

    // 2. 마우스를 움직일 때 (드래그 중일 때만 동작)
    window.addEventListener('mousemove', (e) => {
        if (isDragging) {
            handleProgressChange(e);
        }
    });

    // 3. 마우스를 뗐을 때
    window.addEventListener('mouseup', () => {
        if (isDragging) {
            isDragging = false;
            // 드래그가 끝난 시점에만 오디오 시간을 확정하고 싶다면 여기서 audio.currentTime 설정
        }
    });

    // 시간 텍스트와 바의 너비를 업데이트하는 함수
    function updateProgressUI(time) {
        // 프로그레스 바 너비 업데이트
        const progressPercent = (time / duration) * 100;
        progress.style.width = `${progressPercent}%`;

        // 시간 텍스트 업데이트 (m:ss 형식)
        const minutes = Math.floor(time / 60);
        const seconds = Math.floor(time % 60);
        const formattedSeconds = seconds < 10 ? `0${seconds}` : seconds;
        
        currentTimeText.innerText = `${minutes}:${formattedSeconds}`;
    }




    
    // 오디오 제어 버튼 속성
    const btn_audio_a = document.getElementById('btn_audio_a')
    const btn_audio_b = document.getElementById('btn_audio_b')
    const btn_audio_stereo = document.getElementById('btn_audio_stereo')

    // 재생/정지 버튼 (초기에 정지상태)
    const audio_cont_btn = document.getElementById('main_toggle_btn')
    const toggle_icon = document.getElementById('toggle_icon');
    const toggle_text = document.getElementById('toggle_text');

    // 공통 토글 및 뮤트 함수
    function toggleAudio(btn, audio) {
        const isActive = btn.classList.toggle('active');
        audio.muted = !isActive; // 활성 상태면 소리가 나게(muted = false)
    }

    // 기준 음원(A) 버튼 이벤트
    btn_audio_a.addEventListener('click', () => {
        // 스테레오가 켜져 있다면 끄기 (선택 사항: 기획에 따라 조정 가능)
        btn_audio_stereo.classList.remove('active');
        audio_stereo.muted = true;

        toggleAudio(btn_audio_a, audio_a);
    });

    // 학생 음원(B) 버튼 이벤트
    btn_audio_b.addEventListener('click', () => {
        btn_audio_stereo.classList.remove('active');
        audio_stereo.muted = true;

        toggleAudio(btn_audio_b, audio_b);
    });

    // 스테레오 버튼 이벤트
    btn_audio_stereo.addEventListener('click', () => {
        const isStereoActive = btn_audio_stereo.classList.toggle('active');
        audio_stereo.muted = !isStereoActive;

        // 스테레오 활성화 시 A와 B를 강제로 비활성화 및 Mute
        if (isStereoActive) {
            btn_audio_a.classList.remove('active');
            btn_audio_b.classList.remove('active');
            audio_a.muted = true;
            audio_b.muted = true;
        }
    });

    // 버튼 상태를 초기화하는 공통 함수
    function resetAudioButton() {
        audio_cont_btn.classList.add('paused');
        toggle_icon.textContent = '▶'; 
        toggle_text.textContent = '재생';
    }

    // 재생/일시정지 제어 버튼
    audio_cont_btn.addEventListener('click', () => {
        // 현재 paused 클래스가 있는지 확인 (정지 상태인지 확인)
        const isPaused = audio_cont_btn.classList.contains('paused');

        if (isPaused) { // 음원의 끝에 도달했을때도 변화할 필요
            // [현재 정지 -> 재생 상태로 변경]
            audio_cont_btn.classList.remove('paused');
            toggle_icon.textContent = '⏸'; // 일시정지 아이콘
            toggle_text.textContent = '일시정지';

            // 모든 오디오 재생 시작
            audios.forEach(audio => {
                audio.play().catch(e => console.log("재생 오류:", e));
            });
        } else {
            // [현재 재생 -> 정지 상태로 변경]
            resetAudioButton(); // 공통 함수 사용으로 코드 중복 제거
            audios.forEach(audio => {
                audio.pause();
            });
        }
    });

    // --- 음량 조절 로직 추가 ---
    vol.oninput = () => {
        const val = vol.value;
        volVal.innerText = `${val}%`;
        const volumeLevel = val / 100; // 0.0 ~ 1.0 범위로 변환

        audios.forEach(audio => {
            audio.volume = volumeLevel;
        });
    };

    // --- 배속 조절 로직 추가 ---
    function setRateFromSlider() {
        const raw = parseInt(rate.value || "100", 10);        // 50~200
        const r = Math.max(50, Math.min(200, raw)) / 100.0;   // 0.5~2.0

        rateVal.textContent = r.toFixed(2) + "x";

        audios.forEach(audio => {
            audio.playbackRate = r;
        });
    }
    rate.addEventListener("input", setRateFromSlider);



    // ===== shape 관리(이름으로 교체) =====
    function setNamedShape(name, shapeObjOrNull) {
        const gd = plotDiv;
        const prev = (gd.layout && gd.layout.shapes) ? gd.layout.shapes : [];
        const kept = prev.filter(s => s && s.name !== name);
        const next = shapeObjOrNull ? [...kept, { ...shapeObjOrNull, name }] : kept;
        Plotly.relayout(gd, { shapes: next });
    }

    // ===== 실시간 재생 바(playhead) =====
    let lastPlayheadX = null;
    function setPlayheadLine(x) {
        if (lastPlayheadX !== null && Math.abs(lastPlayheadX - x) < 0.02) return;
        lastPlayheadX = x;
        setNamedShape("playhead_line", {
        type: "line",
        xref: "x",
        yref: "paper",
        x0: x, x1: x,
        y0: 0, y1: 1,
        line: { color: "#FF7A00", width: 2 }
        });
    }



    let rafId = null;
    // 부드러운 이동을 위한 RAF 루프
    function rafLoop() {
        // 세 오디오 중 하나라도 재생 중인지 확인
        const isPlaying = audios.some(audio => !audio.paused && !audio.ended);

        if (isPlaying) {
            // 기준이 되는 오디오(예: 첫 번째 오디오)의 현재 시간을 전달
            // 모든 오디오가 싱크되어 있다고 가정하므로 audios[0]을 기준으로 합니다.
            setPlayheadLine(audios[0].currentTime);
            rafId = requestAnimationFrame(rafLoop);
        } else {
            cancelAnimationFrame(rafId);
            rafId = null;
        }
    }

    // 모든 오디오 객체에 이벤트 리스너 등록
    audios.forEach(audio => {
        // 재생 시작 시 RAF 실행
        audio.addEventListener("play", () => {
            if (!rafId) rafId = requestAnimationFrame(rafLoop);
        });

        // 일시정지 시 체크 (모든 오디오가 정지 상태일 때만 RAF 중단)
        audio.addEventListener("pause", () => {
            const anyPlaying = audios.some(a => !a.paused && !a.ended);
            if (!anyPlaying && rafId) {
                cancelAnimationFrame(rafId);
                rafId = null;
            }
        });

        // 백업: 시간 정보 업데이트 시 실행
        audio.addEventListener("timeupdate", () => {
            updateProgressUI(audio.currentTime);
            // RAF가 동작 중이지 않을 때만(예: 탐색 시) 직접 업데이트
            if (!rafId) {
                setPlayheadLine(audio.currentTime);
            }
        });
    });

    // ===== seek =====
    function clampTime(t) {
        // 세 음원의 길이가 같으므로 기준이 되는 audio_a의 길이를 사용합니다.
        const duration = audio_a.duration;

        try {
            // duration이 정상적인 숫자인지, 그리고 0보다 큰지 확인
            if (isFinite(duration) && duration > 0) {
                // 0보다 작으면 0으로, 전체 길이보다 길면 (전체 길이 - 0.05초)로 제한
                // 0.05초를 빼는 이유는 오디오 끝부분에서 발생할 수 있는 버그를 방지하기 위함입니다.
                return Math.max(0, Math.min(t, duration - 0.05));
            }
        } catch (e) {
            console.error("duration 참조 중 오류 발생:", e);
        }

        // 로딩 전이거나 문제가 있을 경우 최소한 0보다는 크게 반환
        return Math.max(0, t);
    }

    // 공통 탐색(Seek) 함수
    function seekTo(t) {
        const target = clampTime(t);
        if (selected_time) selected_time.textContent = target.toFixed(2);

        audios.forEach(audio => {
            // 모든 음원의 시간을 동일하게 설정
            audio.currentTime = target;
            
            // 브라우저의 currentTime 지연을 방지하기 위한 보정 (필요시)
            if (Math.abs(audio.currentTime - target) > 0.1) {
                audio.currentTime = target;
            }
        });
    }

    // 반복 재생을 관리하는 함수
    function setupLoopPlayback() {
        audios.forEach(audio => {
            // 기존에 등록된 이벤트가 중복 쌓이지 않도록 제거 후 등록 (권장)
            audio.removeEventListener('timeupdate', handleTimeUpdate);
            audio.addEventListener('timeupdate', handleTimeUpdate);
        });
    }

    function handleTimeUpdate() {
        const master = audios[0]; // 기준 음원
        
        // 기준 음원이 종료 지점(end)에 도달했는지 확인
        if (master.currentTime >= end) {
            console.log("루프 구간 도달: 처음으로 이동");
            
            audios.forEach(audio => {
                audio.currentTime = start;
                
                // 현재 일시정지 상태이든 아니든, 루프 중에는 무조건 다시 재생
                // 브라우저가 끝에 도달해서 자동으로 멈췄을 수도 있기 때문
                audio.play().catch(e => console.log("재생 오류 방지:", e)); 
            });
            return; // 루프 동작 시 동기화 로직은 건너뜀
        }

        // 음원 간의 시간 차이가 벌어졌을 때 강제 동기화 (0.1초 이상 차이 날 때)
        audios.forEach((audio, index) => {
            if (index === 0) return; // 기준 음원은 건너뜀
            
            const diff = Math.abs(audio.currentTime - master.currentTime);
            if (diff > 0.1) { // 0.1초 이상 차이가 나면 기준에 맞춤
                audio.currentTime = master.currentTime;
            }
        });
    }

    // ===== 클릭 -> 선택선 + 점프 =====
    plotDiv.on('plotly_click', function(ev) {
        if (!ev || !ev.points || !ev.points.length) return;
        const p = ev.points[0];
        const x = (typeof p.x === "number") ? p.x : parseFloat(p.x);
        if (!isFinite(x)) return;

        setPlayheadLine(x);
        seekTo(x);
    });

    // 재생선 생성
    setPlayheadLine(0); 
})();