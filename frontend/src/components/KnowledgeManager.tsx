import { useState, useEffect } from 'react';
import { api } from '../api';
import { FaPlus, FaDatabase, FaFile, FaTimes } from 'react-icons/fa';
import './KnowledgeManager.css';

interface UploadedFile {
  file_id: string;
  filename: string;
  upload_time: number;
  size: number;
}

interface KnowledgeBaseFile {
  filename: string;
  chunk_count: number;
}

interface KnowledgeBaseInfo {
  id: string;
  name: string;
  collection_name: string;
  total_documents: number;
  uploaded_files: KnowledgeBaseFile[];
  is_active: boolean;
  created_at?: number;
}

interface KnowledgeBase {
  id: string;
  name: string;
  is_active: boolean;
  total_documents?: number | string;
  created_at?: number;
}

export default function KnowledgeManager() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [kbInfo, setKbInfo] = useState<KnowledgeBaseInfo | null>(null);
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searching, setSearching] = useState(false);
  const [showCreateKB, setShowCreateKB] = useState(false);
  const [newKBName, setNewKBName] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [filesRes, kbRes, kbListRes] = await Promise.all([
        api.getFilesList(),
        api.getKnowledgeBaseInfo(),
        api.getKnowledgeBasesList(),
      ]);
      
      setFiles(filesRes.data.files || []);
      setKbInfo(kbRes.data);
      setKnowledgeBases(kbListRes.data.knowledge_bases || []);
    } catch (error) {
      console.error('加载数据失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = event.target.files;
    if (!selectedFiles || selectedFiles.length === 0) return;

    const activeKB = knowledgeBases.find(kb => kb.is_active);
    const targetKbId = activeKB?.id || 'default';
    const targetKbName = activeKB?.name || '默认知识库';

    setUploading(true);
    setMessage('');

    try {
      for (const file of Array.from(selectedFiles)) {
        await api.uploadFile(file, targetKbId);
        setMessage(`文件 "${file.name}" 已上传到「${targetKbName}」并向量化`);
      }
      await loadData();
    } catch (error) {
      console.error('上传失败:', error);
      setMessage('上传失败，请重试');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;

    setSearching(true);
    try {
      const response = await api.ragSearch(searchQuery, 10);
      setSearchResults(response.data.results || []);
    } catch (error) {
      console.error('搜索失败:', error);
      setSearchResults([]);
    } finally {
      setSearching(false);
    }
  };

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const formatTime = (timestamp: number) => {
    return new Date(timestamp * 1000).toLocaleString('zh-CN');
  };

  const handleDeleteFile = async (fileId: string, filename: string) => {
    if (!confirm(`确定要删除文件 "${filename}" 吗？`)) return;

    setLoading(true);
    try {
      const response = await api.deleteFile(fileId);
      if (response.data.success) {
        setMessage(`文件已删除`);
        await loadData();
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('删除失败:', error);
      setMessage('删除失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleClearKnowledgeBase = async () => {
    if (!confirm('确定要清空整个知识库吗？此操作将删除所有向量化数据！')) return;
    if (!confirm('最后确认：真的要清空知识库吗？')) return;

    setLoading(true);
    try {
      const response = await api.clearKnowledgeBase();
      if (response.data.success) {
        setMessage(`知识库已清空`);
        await loadData();
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('清空失败:', error);
      setMessage('清空失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateKB = async () => {
    if (!newKBName.trim()) {
      setMessage('请输入知识库名称');
      return;
    }

    setLoading(true);
    try {
      const response = await api.createKnowledgeBase(newKBName.trim());
      if (response.data.success) {
        setMessage(`知识库「${newKBName}」已创建`);
        setNewKBName('');
        setShowCreateKB(false);
        await loadData();
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('创建失败:', error);
      setMessage('创建失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleSwitchKB = async (kbId: string, kbName: string) => {
    setLoading(true);
    try {
      const response = await api.switchKnowledgeBase(kbId);
      if (response.data.success) {
        const { total_documents } = response.data;
        // 更新本地知识库列表状态
        setKnowledgeBases(prev => prev.map(kb => ({
          ...kb,
          is_active: kb.id === kbId,
          total_documents: kb.id === kbId ? (total_documents || 0) : kb.total_documents
        })));
        // 重新加载当前知识库详细信息（包含文档列表）
        const kbInfoRes = await api.getKnowledgeBaseInfo();
        setKbInfo(kbInfoRes.data);
        setMessage(`已切换到知识库「${kbName}」(${total_documents || 0} 个分块)`);
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('切换失败:', error);
      setMessage('切换失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteKB = async (kbId: string, kbName: string) => {
    if (!confirm(`确定要删除知识库「${kbName}」吗？`)) return;

    setLoading(true);
    try {
      const response = await api.deleteKnowledgeBase(kbId);
      if (response.data.success) {
        setMessage(`知识库已删除`);
        await loadData();
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('删除失败:', error);
      setMessage('删除失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleRenameKB = async (kbId: string, oldName: string) => {
    const newName = prompt(`请输入新的知识库名称：`, oldName);
    if (!newName || newName === oldName) return;

    setLoading(true);
    try {
      const response = await api.renameKnowledgeBase(kbId, newName.trim());
      if (response.data.success) {
        setMessage(`知识库已重命名为「${newName}」`);
        await loadData();
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('重命名失败:', error);
      setMessage('重命名失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteDocFromKB = async (filename: string) => {
    if (!confirm(`确定要从知识库中删除文档「${filename}」吗？`)) return;

    setLoading(true);
    try {
      const response = await api.deleteDocumentFromKB(filename);
      if (response.data.success) {
        setMessage(`文档「${filename}」已从知识库中删除`);
        await loadData();
      } else {
        setMessage(`${response.data.message}`);
      }
    } catch (error) {
      console.error('删除文档失败:', error);
      setMessage('删除文档失败，请重试');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="knowledge-manager">
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner">
            <div className="spinner-ring"></div>
            <p>加载中...</p>
          </div>
        </div>
      )}

      <div className="panel-header">
        <h2 className="panel-title">
          <FaDatabase className="header-icon" /> 知识库管理
        </h2>
      </div>

      <div className="kb-main-layout">
        <div className="kb-left-panel">
          <div className="kb-list-section">
            <div className="kb-list-header">
              <h3>我的知识库 ({knowledgeBases.length})</h3>
              <button className="btn-primary-small" onClick={() => setShowCreateKB(true)}>
                <FaPlus /> 创建
              </button>
            </div>

            {showCreateKB && (
              <div className="create-kb-form">
                <input
                  type="text"
                  placeholder="请输入知识库名称"
                  value={newKBName}
                  onChange={(e) => setNewKBName(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleCreateKB()}
                />
                <button className="btn-confirm" onClick={handleCreateKB}>
                  确认
                </button>
                <button className="btn-cancel" onClick={() => { setShowCreateKB(false); setNewKBName(''); }}>
                  取消
                </button>
              </div>
            )}

            {knowledgeBases.length > 0 ? (
              <div className="kb-list">
                {knowledgeBases.map((kb) => (
                  <div key={kb.id} className={`kb-item ${kb.is_active ? 'active' : ''}`}>
                    <div className="kb-item-header">
                      <span className="kb-name">
                        {kb.is_active && <span className="active-dot" />}
                        {kb.name}
                      </span>
                      <div className="kb-actions">
                        {!kb.is_active && (
                          <button
                            className="btn-switch"
                            onClick={() => handleSwitchKB(kb.id, kb.name)}
                            title="切换"
                          >
                            切换
                          </button>
                        )}
                        <button
                          className="btn-rename"
                          onClick={() => handleRenameKB(kb.id, kb.name)}
                          title="重命名"
                        >
                          重命名
                        </button>
                        {kb.id !== 'default' && !kb.is_active && (
                          <button
                            className="btn-delete-kb"
                            onClick={() => handleDeleteKB(kb.id, kb.name)}
                            title="删除"
                          >
                            删除
                          </button>
                        )}
                      </div>
                    </div>
                    <div className="kb-item-info">
                      <span className="kb-doc-count">
                        {typeof kb.total_documents === 'number' ? `${kb.total_documents} 个分块` : kb.total_documents === '未加载' ? '未加载' : '0 个分块'}
                      </span>
                      {kb.created_at && (
                        <span className="kb-create-time">
                          {new Date(kb.created_at * 1000).toLocaleDateString('zh-CN')}
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty-state">
                <p>暂无知识库，请创建一个</p>
              </div>
            )}
          </div>

          {files.length > 0 && (
            <div className="files-section">
              <h3>历史上传文件 ({files.length})</h3>
              <div className="files-list">
                {files.map((file) => (
                  <div key={file.file_id} className="file-item">
                    <FaFile className="file-icon" />
                    <div className="file-info">
                      <div className="file-name" title={file.filename}>{file.filename}</div>
                      <div className="file-time">
                        {formatTime(file.upload_time)} · {formatFileSize(file.size)}
                      </div>
                    </div>
                    <button 
                      className="btn-delete"
                      onClick={() => handleDeleteFile(file.file_id, file.filename)}
                      title="删除"
                    >
                      <FaTimes />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="kb-right-panel">
          <div className="kb-current-section">
            {kbInfo ? (
              <>
                <div className="kb-current-header">
                  <h3>当前知识库：{knowledgeBases.find(kb => kb.is_active)?.name || '默认知识库'}</h3>
                  <div className="kb-current-actions">
                    <label className="upload-button-inline">
                      <input
                        type="file"
                        accept=".txt,.md,.pdf,.docx"
                        multiple
                        onChange={handleFileUpload}
                        disabled={uploading}
                        style={{ display: 'none' }}
                      />
                      <span className="button-content">
                        {uploading ? '上传中...' : '上传素材'}
                      </span>
                    </label>
                    
                    {kbInfo.is_active && (
                      <button 
                        className="btn-danger-small" 
                        onClick={handleClearKnowledgeBase}
                        title="清空知识库"
                      >
                        清空
                      </button>
                    )}
                  </div>
                </div>

                <div className="kb-status-card">
                  <div className="kb-status-item">
                    <span className="kb-label">状态</span>
                    <span className={`kb-status ${kbInfo.is_active ? 'active' : 'inactive'}`}>
                      {kbInfo.is_active ? '已激活' : '未激活'}
                    </span>
                  </div>
                  <div className="kb-status-item">
                    <span className="kb-label">知识库ID</span>
                    <span className="kb-value">{kbInfo.collection_name}</span>
                  </div>
                  <div className="kb-status-item">
                    <span className="kb-label">总文档数</span>
                    <span className="kb-value">{kbInfo.total_documents} 个分块</span>
                  </div>
                  {kbInfo.uploaded_files.length > 0 && (
                    <div className="kb-files-in-vector">
                      <span className="kb-label">已向量化文件</span>
                      <div className="kb-files-list">
                        {kbInfo.uploaded_files.map((file, idx) => (
                          <div key={idx} className="kb-file-tag">
                            <span className="file-info">
                              {file.filename}
                              <span className="chunk-count">({file.chunk_count} 块)</span>
                            </span>
                            <button 
                              className="btn-delete-doc"
                              onClick={() => handleDeleteDocFromKB(file.filename)}
                              title="删除"
                            >
                              ×
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {message && (
                  <div className={`upload-message ${message.includes('已') ? 'success' : 'error'}`}>
                    {message}
                  </div>
                )}
              </>
            ) : (
              <div className="empty-state">
                <p>正在加载知识库信息...</p>
              </div>
            )}
          </div>

          <div className="search-section">
            <h3>语义搜索</h3>
            <p className="description">测试知识库的检索能力</p>
            
            <div className="search-bar">
              <input
                type="text"
                placeholder="输入搜索内容..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              />
              <button onClick={handleSearch} disabled={searching || !searchQuery.trim()}>
                {searching ? '搜索中...' : '搜索'}
              </button>
            </div>

            {searchResults.length > 0 && (
              <div className="search-results">
                <h4>搜索结果</h4>
                {searchResults.map((result, index) => (
                  <div key={index} className="result-item">
                    <div className="result-header">
                      <div className="result-score">
                        相似度: {(result.score * 100).toFixed(1)}%
                        {result.article && (
                          <span className="result-article"> | 条款: 第{result.article}条</span>
                        )}
                      </div>
                      <div className="result-source">来源: {result.source}</div>
                    </div>
                    <div className="result-content">{result.content}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="tips-section">
        <h3>使用提示</h3>
        <ul>
          <li>上传的文本文件会自动进行向量化，用于 RAG 检索</li>
          <li>生成脚本时会自动检索相关知识，生成更准确的讲解内容</li>
          <li>建议上传产品说明书、技术文档等结构化内容</li>
          <li>文件名应具有描述性，便于后续管理</li>
          <li>当前知识库中的文档会用于所有策展生成</li>
        </ul>
      </div>
    </div>
  );
}
