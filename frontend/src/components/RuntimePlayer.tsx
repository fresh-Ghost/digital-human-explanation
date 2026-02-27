import { useState, useEffect, useRef } from 'react';
import { usePlayerStore } from '../store/playerStore';
import { encodeWAV } from '../utils/wavEncoder';
import { FaPlay, FaPause, FaStepBackward, FaStepForward, FaMicrophone, FaStop } from 'react-icons/fa';
import './RuntimePlayer.css';

type RuntimeState = 'idle' | 'narrating' | 'listening' | 'thinking' | 'answering';

export default function RuntimePlayer() {
  const {
    script,
    currentPageIndex,
    isPlaying,
    play,
    pause,
    next,
    prev,
    audioElement,
  } = usePlayerStore();

  const [runtimeState, setRuntimeState] = useState<RuntimeState>('idle');
  const [isVADActive, setIsVADActive] = useState(false);
  const [answerText, setAnswerText] = useState('');
  const [subtitle, setSubtitle] = useState('');
  
  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const recordingDataRef = useRef<Float32Array[]>([]);
  const vadCheckIntervalRef = useRef<number | null>(null);
  const answerAudioRef = useRef<HTMLAudioElement | null>(null);

  const sessionId = useRef(`session_${Date.now()}`);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/runtime/${sessionId.current}`);
    
    ws.onopen = () => {
      console.log('[WebSocket] 已连接');
    };

    ws.onmessage = (event) => {
      const message = JSON.parse(event.data);
      handleWebSocketMessage(message);
    };

    ws.onerror = (error) => {
      console.error('[WebSocket] 错误:', error);
    };

    ws.onclose = () => {
      console.log('[WebSocket] 已断开');
    };

    wsRef.current = ws;

    return () => {
      ws.close();
      stopVAD();
    };
  }, []);

  const handleWebSocketMessage = (message: any) => {
    const { type } = message;

    if (type === 'control') {
      if (message.command === 'pause') {
        console.log('[RuntimePlayer] 收到暂停指令，当前位置:', audioElement?.currentTime);
        pause();
      } else if (message.command === 'resume') {
        console.log('[RuntimePlayer] 收到恢复指令，当前位置:', audioElement?.currentTime);
        if (audioElement && audioElement.paused && audioElement.src) {
          audioElement.play().catch(e => console.error('恢复播放失败:', e));
        } else {
          play();
        }
      }
    } else if (type === 'status') {
      setRuntimeState(message.state);
    } else if (type === 'subtitle') {
      setSubtitle(message.text);
    } else if (type === 'answer') {
      setAnswerText(message.text);
      if (message.audio_url) {
        playAnswer(message.audio_url);
      }
    } else if (type === 'error') {
      console.error('[WebSocket] 服务端错误:', message.message);
      setSubtitle(message.message);
    }
  };

  const playAnswer = (audioUrl: string) => {
    const fullUrl = audioUrl.startsWith('http') ? audioUrl : `http://localhost:8000${audioUrl}`;
    
    if (answerAudioRef.current) {
      answerAudioRef.current.pause();
    }

    const audio = new Audio(fullUrl);
    answerAudioRef.current = audio;

    audio.onplay = () => setRuntimeState('answering');
    audio.onended = () => {
      setRuntimeState('idle');
      setSubtitle('点击"继续讲解"按钮恢复播放');
    };

    audio.play().catch(e => console.error('播放回答失败:', e));
  };

  const startVAD = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      const audioContext = new AudioContext({ sampleRate: 16000 });
      audioContextRef.current = audioContext;

      const source = audioContext.createMediaStreamSource(stream);
      const analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      analyserRef.current = analyser;

      source.connect(analyser);

      recordingDataRef.current = [];

      const processor = audioContext.createScriptProcessor(4096, 1, 1);
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0);
        recordingDataRef.current.push(new Float32Array(inputData));
      };

      source.connect(processor);
      processor.connect(audioContext.destination);

      setIsVADActive(true);

      vadCheckIntervalRef.current = window.setInterval(() => {
        checkVoiceActivity();
      }, 100);

      wsRef.current?.send(JSON.stringify({
        type: 'vad_event',
        status: 'start'
      }));

      console.log('[VAD] 已启动');
    } catch (error) {
      console.error('[VAD] 启动失败:', error);
      alert('无法访问麦克风，请检查权限');
    }
  };

  const stopVAD = () => {
    if (vadCheckIntervalRef.current) {
      clearInterval(vadCheckIntervalRef.current);
      vadCheckIntervalRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach(track => track.stop());
      streamRef.current = null;
    }

    if (audioContextRef.current) {
      audioContextRef.current.close();
      audioContextRef.current = null;
    }

    if (recordingDataRef.current.length > 0) {
      sendRecordedAudio();
    }

    setIsVADActive(false);
    console.log('[VAD] 已停止');
  };

  const checkVoiceActivity = () => {
    if (!analyserRef.current) return;

    const dataArray = new Uint8Array(analyserRef.current.fftSize);
    analyserRef.current.getByteTimeDomainData(dataArray);

    let sum = 0;
    for (let i = 0; i < dataArray.length; i++) {
      const value = Math.abs(dataArray[i] - 128);
      sum += value;
    }
    const average = sum / dataArray.length;

    const threshold = 5;
    if (average < threshold && recordingDataRef.current.length > 10) {
      console.log('[VAD] 检测到静音，停止录音');
      stopVAD();
    }
  };

  const sendRecordedAudio = () => {
    const totalLength = recordingDataRef.current.reduce((acc, arr) => acc + arr.length, 0);
    const mergedSamples = new Float32Array(totalLength);
    let offset = 0;
    for (const samples of recordingDataRef.current) {
      mergedSamples.set(samples, offset);
      offset += samples.length;
    }

    const audioBlob = encodeWAV(mergedSamples, 16000);

    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = (reader.result as string).split(',')[1];
      
      wsRef.current?.send(JSON.stringify({
        type: 'vad_event',
        status: 'end',
        audio_data: base64,
        kb_id: 'default'
      }));

      console.log('[VAD] 音频已发送');
    };
    reader.readAsDataURL(audioBlob);

    recordingDataRef.current = [];
  };

  const handleResumeNarration = () => {
    wsRef.current?.send(JSON.stringify({
      type: 'control',
      command: 'resume'
    }));
    
    if (audioElement && audioElement.paused && audioElement.src) {
      console.log('[RuntimePlayer] 恢复播放，从位置:', audioElement.currentTime);
      audioElement.play().catch(e => console.error('恢复播放失败:', e));
    } else {
      console.log('[RuntimePlayer] 重新播放');
      play();
    }
    
    setRuntimeState('narrating');
  };

  if (!script) {
    return (
      <div className="runtime-player-panel">
        <div className="empty-state">
          <div className="empty-icon">
            <span className="icon icon-runtime" />
          </div>
          <h3>暂无脚本</h3>
          <p>请先生成讲解脚本</p>
        </div>
      </div>
    );
  }

  const currentPage = script.timeline[currentPageIndex];
  const totalPages = script.timeline.length;

  const getStateLabel = () => {
    switch (runtimeState) {
      case 'idle': return '待机中';
      case 'narrating': return '讲解中';
      case 'listening': return '聆听中';
      case 'thinking': return '思考中';
      case 'answering': return '回答中';
      default: return '待机中';
    }
  };

  return (
    <div className="runtime-player-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="icon icon-runtime" /> 增强版播放器
        </h2>
        <span className="page-indicator">
          {currentPageIndex + 1} / {totalPages}
        </span>
      </div>

      <div className={`state-indicator ${runtimeState}`}>
        <div className="state-wave">
          {runtimeState === 'listening' && <div className="wave listening" />}
          {runtimeState === 'thinking' && <div className="wave thinking" />}
          {runtimeState === 'answering' && <div className="wave answering" />}
          {runtimeState === 'narrating' && <div className="wave narrating" />}
        </div>
        <div className="state-label">{getStateLabel()}</div>
      </div>

      {subtitle && (
        <div className="subtitle-bar">
          {subtitle}
        </div>
      )}

      <div className="script-display">
        <h3 className="script-title">{script.meta.title}</h3>
        <div className="script-content">
          <p className="content-text">{currentPage.voice_text}</p>
        </div>
      </div>

      {answerText && (
        <div className="qa-display">
          <div className="qa-label">智能回答</div>
          <p className="answer-text">{answerText}</p>
        </div>
      )}

      <div className="player-controls">
        <button 
          onClick={prev} 
          disabled={currentPageIndex === 0} 
          className="control-btn"
          title="上一页"
        >
          <FaStepBackward size={16} />
        </button>

        <button 
          onClick={isPlaying ? pause : play} 
          disabled={runtimeState !== 'idle' && runtimeState !== 'narrating'}
          className="control-btn play-btn"
          title={isPlaying ? '暂停' : '播放'}
        >
          {isPlaying ? <FaPause size={20} /> : <FaPlay size={20} />}
        </button>

        <button 
          onClick={next} 
          disabled={currentPageIndex === totalPages - 1} 
          className="control-btn"
          title="下一页"
        >
          <FaStepForward size={16} />
        </button>
      </div>

      <div className="vad-controls">
        {!isVADActive ? (
          <button 
            onClick={startVAD}
            disabled={!isPlaying}
            className="vad-btn"
            title="启动智能打断"
          >
            <FaMicrophone size={14} /> 启动智能打断
          </button>
        ) : (
          <button 
            onClick={stopVAD}
            className="vad-btn active"
          >
            <FaStop size={14} /> 停止监听
          </button>
        )}

        {runtimeState === 'idle' && answerText && (
          <button 
            onClick={handleResumeNarration}
            className="resume-btn"
          >
            <FaPlay size={14} /> 继续讲解
          </button>
        )}
      </div>

      <audio ref={answerAudioRef} style={{ display: 'none' }} />
    </div>
  );
}
