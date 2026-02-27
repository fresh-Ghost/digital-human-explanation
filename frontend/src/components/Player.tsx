import { usePlayerStore } from '../store/playerStore';
import { FaPlay, FaPause, FaStepBackward, FaStepForward } from 'react-icons/fa';
import './Player.css';

export default function Player() {
  const {
    script,
    currentPageIndex,
    isPlaying,
    state,
    progress,
    play,
    pause,
    next,
    prev,
  } = usePlayerStore();

  if (!script) {
    return (
      <div className="player-panel">
        <div className="empty-state">
          <div className="empty-icon">
            <span className="icon icon-player" />
          </div>
          <h3>暂无脚本</h3>
          <p>请先在左侧生成讲解脚本</p>
        </div>
      </div>
    );
  }

  const currentPage = script.timeline[currentPageIndex];
  const totalPages = script.timeline.length;

  return (
    <div className="player-panel">
      <div className="panel-header">
        <h2 className="panel-title">
          <span className="icon icon-player" /> 播放器
        </h2>
        <span className="page-indicator">
          {currentPageIndex + 1} / {totalPages}
        </span>
      </div>

      <div className="script-display">
        <h3 className="script-title">{script.meta.title}</h3>
        <div className="script-content">
          <p className="content-text">{currentPage.voice_text}</p>
        </div>
        <div className="duration-badge">
          预计时长: {Math.round(currentPage.duration_ms / 1000)} 秒
        </div>
      </div>

      <div className="progress-section">
        <div className="progress-bar">
          <div 
            className="progress-fill"
            style={{ width: `${progress}%` }}
          />
        </div>
        <span className="progress-text">{Math.round(progress)}%</span>
      </div>

      <div className="player-controls">
        <button
          onClick={prev}
          disabled={currentPageIndex === 0 || state === 'loading'}
          className="control-btn"
          title="上一页"
        >
          <FaStepBackward size={16} />
        </button>

        <button
          onClick={isPlaying ? pause : play}
          disabled={state === 'loading'}
          className="control-btn play-btn"
          title={isPlaying ? '暂停' : '播放'}
        >
          {state === 'loading' ? (
            <span className="loading-dots">...</span>
          ) : isPlaying ? (
            <FaPause size={20} />
          ) : (
            <FaPlay size={20} />
          )}
        </button>

        <button
          onClick={next}
          disabled={currentPageIndex === totalPages - 1 || state === 'loading'}
          className="control-btn"
          title="下一页"
        >
          <FaStepForward size={16} />
        </button>
      </div>

      {state === 'error' && (
        <div className="error-message">
          播放出错，请重试
        </div>
      )}
    </div>
  );
}
