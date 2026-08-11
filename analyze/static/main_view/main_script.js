(function() {
    // var tag = document.createElement('script');
    // tag.src = "https://www.youtube.com/iframe_api";
    // var firstScriptTag = document.getElementsByTagName('script')[0];
    // firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

    // 1. API 스크립트 삽입
    var tag = document.createElement('script');
    tag.src = "https://www.youtube.com/iframe_api";
    document.head.appendChild(tag);
    
    let playerA, playerB;
    let readyCount = 0;
    let isSeeking = false;
    
    // 2. API 로딩 완료 후 자동 호출되는 전역 함수
    window.onYouTubeIframeAPIReady = function () {
        playerA = new YT.Player('playerA', {
            videoId: '{id_a}',
            playerVars: {
                controls: 0,
                disablekb: 1,
                rel: 0,
                modestbranding: 1
            },
            events: { onReady: onPlayerReady }
        });

        playerB = new YT.Player('playerB', {
            videoId: '{id_b}',
            playerVars: {
                controls: 0,
                disablekb: 1,
                rel: 0,
                modestbranding: 1
            },
            events: { onReady: onPlayerReady }
        });
    };
    
    function onPlayerReady() {
        readyCount++;
        if (readyCount === 2) {
            const btn = document.getElementById('playBtn');
            btn.innerText = "Play / Pause";
            btn.style.background = "#ff4b4b";
            btn.style.cursor = "pointer";
            btn.disabled = false;
            updateMute();
            setInterval(updateUI, 500);
        }
    }
    
    const playBtn = document.getElementById('playBtn');
    const seekBar = document.getElementById('seekBar');
    const curTime = document.getElementById('curTime');
    
    playBtn.onclick = () => {
        // getPlayerState가 존재하는지 안전하게 확인
        if (playerA && typeof playerA.getPlayerState === "function") {
            const state = playerA.getPlayerState();
            if (state === 1) { // 1은 Playing
                playerA.pauseVideo(); playerB.pauseVideo();
            } else {
                playerA.playVideo(); playerB.playVideo();
            }
        }
    };
    
    function updateUI() {
        if (!isSeeking && playerA && typeof playerA.getCurrentTime === "function") {
            const cur = playerA.getCurrentTime();
            const dur = playerA.getDuration();
            if (dur > 0) {
                seekBar.value = (cur / dur) * 100;
                let m = Math.floor(cur / 60), s = Math.floor(cur % 60);
                curTime.innerText = m + ":" + (s < 10 ? '0' : '') + s;
            }
        }
    }
    
    seekBar.oninput = () => { isSeeking = true; };
    seekBar.onchange = () => {
        if (playerA && playerB && playerA.getDuration) {
            const target = playerA.getDuration() * (seekBar.value / 100);
            playerA.seekTo(target, true);
            playerB.seekTo(target, true);
        }
        isSeeking = false;
    };
    
    function updateMute() {
        if (playerA && playerB && playerA.mute) {
            document.getElementById('cA').checked ? playerA.unMute() : playerA.mute();
            document.getElementById('cB').checked ? playerB.unMute() : playerB.mute();
        }
    };
    
    document.getElementById('cA').onchange = updateMute;
    document.getElementById('cB').onchange = updateMute;

})();
