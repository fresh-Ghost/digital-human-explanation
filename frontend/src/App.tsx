import { useState } from 'react';
import CuratorPanel from './components/CuratorPanel';
import Player from './components/Player';
import RuntimePlayer from './components/RuntimePlayer';
import KnowledgeManager from './components/KnowledgeManager';
import './App.css';

type Tab = 'curator' | 'knowledge';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('curator');
  const [useRuntimePlayer, setUseRuntimePlayer] = useState(false);

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-left">
          <h1>灵境 · AI 数字讲解系统</h1>
          <p>基于本地 LLM 的智能策展与自动化讲解</p>
        </div>
        
        <nav className="tab-nav">
          <button 
            className={activeTab === 'curator' ? 'active' : ''}
            onClick={() => setActiveTab('curator')}
          >
            <span className="icon icon-curator" /> 策展与播放
          </button>
          <button 
            className={activeTab === 'knowledge' ? 'active' : ''}
            onClick={() => setActiveTab('knowledge')}
          >
            <span className="icon icon-knowledge" /> 知识库管理
          </button>
        </nav>
      </header>

      <main className="app-main">
        {activeTab === 'curator' ? (
          <>
            <div className="left-panel">
              <CuratorPanel />
            </div>
            <div className="right-panel">
              <div className="player-switch">
                <button 
                  className={!useRuntimePlayer ? 'active' : ''}
                  onClick={() => setUseRuntimePlayer(false)}
                  title="基础播放器"
                >
                  <span className="icon icon-player" /> 基础版
                </button>
                <button 
                  className={useRuntimePlayer ? 'active' : ''}
                  onClick={() => setUseRuntimePlayer(true)}
                  title="增强版播放器（智能打断+RAG问答）"
                >
                  <span className="icon icon-runtime" /> 增强版
                </button>
              </div>
              
              {useRuntimePlayer ? <RuntimePlayer /> : <Player />}
            </div>
          </>
        ) : (
          <div className="full-panel">
            <KnowledgeManager />
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
