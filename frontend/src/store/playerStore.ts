import { create } from 'zustand';
import type { Script, PlayerState } from '../types';

interface PlayerStore {
  // 状态
  state: PlayerState;
  script: Script | null;
  currentPageIndex: number;
  audioElement: HTMLAudioElement | null;
  isPlaying: boolean;
  progress: number;

  // 动作
  setScript: (script: Script) => void;
  setState: (state: PlayerState) => void;
  play: () => Promise<void>;
  pause: () => void;
  next: () => void;
  prev: () => void;
  seekTo: (pageIndex: number) => void;
  setProgress: (progress: number) => void;
  reset: () => void;
}

export const usePlayerStore = create<PlayerStore>((set, get) => ({
  // 初始状态
  state: 'idle',
  script: null,
  currentPageIndex: 0,
  audioElement: null,
  isPlaying: false,
  progress: 0,

  // 设置脚本
  setScript: (script: Script) => {
    set({
      script,
      currentPageIndex: 0,
      state: 'idle',
      isPlaying: false,
      progress: 0,
    });
  },

  // 设置状态
  setState: (state: PlayerState) => set({ state }),

  // 播放
  play: async () => {
    const { script, currentPageIndex, audioElement, state: currentState } = get();
    if (!script || !script.timeline[currentPageIndex]) {
      set({ state: 'error' });
      return;
    }

    // 关键修复：如果是从暂停状态恢复，直接恢复播放，不重新加载音频
    if (audioElement && currentState === 'paused' && audioElement.src && !audioElement.ended) {
      console.log('[Player] 从暂停位置恢复播放，当前位置:', audioElement.currentTime);
      try {
        await audioElement.play();
        set({ state: 'playing', isPlaying: true });
        return;
      } catch (error) {
        console.error('恢复播放失败:', error);
        set({ state: 'error', isPlaying: false });
        return;
      }
    }

    set({ state: 'loading' });

    try {
      const currentPage = script.timeline[currentPageIndex];
      
      // 创建或重用音频元素
      let audio = audioElement;
      if (!audio) {
        audio = new Audio();
        set({ audioElement: audio });

        // 监听音频事件
        audio.onended = () => {
          const { currentPageIndex, script } = get();
          if (script && currentPageIndex < script.timeline.length - 1) {
            // 自动播放下一页
            const nextIndex = currentPageIndex + 1;
            set({
              currentPageIndex: nextIndex,
              progress: 0,
              state: 'idle',
            });
            // 延迟一点再开始播放，确保状态更新
            setTimeout(() => {
              get().play();
            }, 100);
          } else {
            // 所有页面播放完毕
            set({ isPlaying: false, state: 'idle', progress: 0 });
          }
        };

        audio.ontimeupdate = () => {
          if (!audio) return;
          const progress = (audio.currentTime / audio.duration) * 100 || 0;
          set({ progress });
        };

        audio.onerror = () => {
          set({ state: 'error', isPlaying: false });
        };
      }

      // 设置音频源并播放（只在需要重新加载时执行）
      console.log('[Player] 重新加载音频');
      const voiceId = currentPage.voice_id || 'zh-CN-YunxiNeural';
      const audioUrl = `/api/v1/tts/generate?text=${encodeURIComponent(currentPage.voice_text)}&voice=${voiceId}`;
      audio.src = audioUrl;
      await audio.play();

      set({ state: 'playing', isPlaying: true });
    } catch (error) {
      console.error('播放失败:', error);
      set({ state: 'error', isPlaying: false });
    }
  },

  // 暂停
  pause: () => {
    const { audioElement } = get();
    if (audioElement) {
      audioElement.pause();
      set({ isPlaying: false, state: 'paused' });
    }
  },

  // 下一页
  next: () => {
    const { script, currentPageIndex, audioElement } = get();
    if (!script || currentPageIndex >= script.timeline.length - 1) return;

    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }

    set({
      currentPageIndex: currentPageIndex + 1,
      progress: 0,
      isPlaying: false,
      state: 'idle',
    });
  },

  // 上一页
  prev: () => {
    const { currentPageIndex, audioElement } = get();
    if (currentPageIndex <= 0) return;

    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }

    set({
      currentPageIndex: currentPageIndex - 1,
      progress: 0,
      isPlaying: false,
      state: 'idle',
    });
  },

  // 跳转到指定页
  seekTo: (pageIndex: number) => {
    const { script, audioElement } = get();
    if (!script || pageIndex < 0 || pageIndex >= script.timeline.length) return;

    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }

    set({
      currentPageIndex: pageIndex,
      progress: 0,
      isPlaying: false,
      state: 'idle',
    });
  },

  // 设置进度
  setProgress: (progress: number) => {
    const { audioElement } = get();
    if (audioElement && audioElement.duration) {
      audioElement.currentTime = (progress / 100) * audioElement.duration;
      set({ progress });
    }
  },

  // 重置
  reset: () => {
    const { audioElement } = get();
    if (audioElement) {
      audioElement.pause();
      audioElement.currentTime = 0;
    }

    set({
      state: 'idle',
      script: null,
      currentPageIndex: 0,
      isPlaying: false,
      progress: 0,
    });
  },
}));
