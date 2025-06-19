// frontend/src/AskModal.js
import React, { useState } from 'react';

// 這個元件會接收三個 props:
// movie: 被選中的電影物件
// onClose: 一個用來關閉 Modal 的函式
// isOpen: 控制 Modal 是否顯示
function AskModal({ movie, onClose, isOpen }) {
  const [question, setQuestion] = useState(''); // 使用者輸入的問題
  const [answer, setAnswer] = useState('');   // LLM 回傳的答案
  const [isAsking, setIsAsking] = useState(false); // 是否正在詢問中

  if (!isOpen || !movie) {
    return null; // 如果沒打開或沒選中電影，就不渲染任何東西
  }

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!question.trim()) return;

    setIsAsking(true);
    setAnswer('');
    
    // --- 新增這一行，立即清空輸入框 ---
    const currentQuestion = question; // 先將當前問題存起來
    setQuestion(''); // 清空輸入框
    // ------------------------------------

    try {
      // 將存起來的 currentQuestion 送到 API
      const response = await fetch(`http://127.0.0.1:8000/ask/${movie.id}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: currentQuestion }), 
      });

      if (!response.ok) {
        throw new Error('API request failed');
      }

      const data = await response.json();
      setAnswer(data.answer);

    } catch (error) {
      setAnswer(`發生錯誤: ${error.message}`);
    } finally {
      setIsAsking(false);
    }
};

  return (
    <div className="modal-overlay">
      <div className="modal-content">
        <button className="modal-close" onClick={onClose}>&times;</button>
        <h2>問我關於《{movie.title}》的問題</h2>
        
        <div className="modal-context">
          <h4>劇情摘要參考：</h4>
          <p>{movie.overview}</p>
        </div>

        <form onSubmit={handleSubmit}>
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="請在這裡輸入您的問題..."
            disabled={isAsking}
          />
          <button type="submit" disabled={isAsking}>
            {isAsking ? '思考中...' : '送出問題'}
          </button>
        </form>

        {answer && (
          <div className="modal-answer">
            <h4>AI 回答：</h4>
            <p>{answer}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default AskModal;