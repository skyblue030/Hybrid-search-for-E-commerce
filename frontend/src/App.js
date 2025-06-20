// frontend/src/App.js
import React, { useState } from 'react';
import './App.css';
import AskModal from './AskModal'; 

function App() {
  // --- State Management ---
  // 使用 useState 來管理所有會變動的資料
  const [query, setQuery] = useState('a story about friendship'); // 搜尋關鍵字
  const [genre, setGenre] = useState('Comedy'); // 類型篩選
  const [minRating, setMinRating] = useState(7.5); // 評分篩選
  const [movies, setMovies] = useState([]); // 搜尋結果
  const [isLoading, setIsLoading] = useState(false); // 是否正在載入
  const [error, setError] = useState(null); // 錯誤訊息

  // --- 新增給 RAG 問答用的 State ---
  const [isModalOpen, setIsModalOpen] = useState(false); // Modal 是否開啟
  const [selectedMovie, setSelectedMovie] = useState(null); // 當前選中的電影

  // --- 新增處理 Modal 開關的函式 ---
  const handleOpenModal = (movie) => {
    setSelectedMovie(movie);
    setIsModalOpen(true);
  };

  const handleCloseModal = () => {
    setIsModalOpen(false);
    setSelectedMovie(null);
  };
  // --- API Call ---
  // 處理搜尋按鈕點擊事件的函式
  const handleSearch = async (event) => {
    event.preventDefault(); // 防止表單預設的重新載入頁面行為
    setIsLoading(true); // 開始搜尋，顯示載入中
    setError(null); // 清除舊的錯誤訊息
    setMovies([]); // 清除舊的結果

    try {
      // 準備要傳送給 FastAPI 的請求資料
      const requestBody = {
        query: query,
        filters: {
          genre: genre || null, // 如果 genre 是空字串，就傳送 null
          min_rating: parseFloat(minRating) || null,
        },
        top_k: 12
      };

      // 使用 fetch API 呼叫後端
      const response = await fetch('http://127.0.0.1:8000/search/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody),
      });

      if (!response.ok) {
        // 嘗試解析後端可能回傳的錯誤訊息
        const errorData = await response.json().catch(() => null); // 如果回應不是 JSON，則忽略
        const errorMessage = errorData?.detail || `HTTP error! status: ${response.status}`;
        throw new Error(errorMessage);
      }

      const data = await response.json();
      setMovies(data.results); // 更新電影結果狀態

    } catch (err) {
      setError(err.message); // 更新錯誤狀態
    } finally {
      setIsLoading(false); // 搜尋結束，隱藏載入中
    }
  };

  // --- Rendering ---
  // JSX: 描述 UI 長什麼樣子
  return (
    <div className="App">
      <header className="App-header">
        <h1>智慧電影搜尋引擎</h1>
        <form className="search-form" onSubmit={handleSearch}>
          <input
            type="text"
            className="search-input"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="輸入劇情描述..."
          />
          <input
            type="text"
            value={genre}
            onChange={(e) => setGenre(e.target.value)}
            placeholder="類型 (如 Comedy)"
          />
          <input
            type="number"
            step="0.1"
            value={minRating}
            onChange={(e) => setMinRating(e.target.value)}
            placeholder="最低評分"
          />
          <button type="submit" disabled={isLoading}>
            {isLoading ? '搜尋中...' : '搜尋'}
          </button>
        </form>
      </header>
      
      <main className="results-container">
        {error && <p className="error-message">錯誤: {error}</p>}
        
        <div className="movie-grid">
          {movies.map((movie) => (
            <div key={movie.id} className="movie-card">
              <h3>{movie.title} ({movie.release_year})</h3>
              <p className="movie-rating">評分: {movie.vote_average}</p>
              <p className="movie-genres">類型: {movie.genres.join(', ')}</p>
              <p className="movie-overview">{movie.overview}</p>
              <button className="ask-button" onClick={() => handleOpenModal(movie)}>
                智慧問答
              </button>
            </div>
          ))}
        </div>
      </main>

      {/* --- 3. 根據狀態渲染 Modal --- */}
      <AskModal
        isOpen={isModalOpen}
        onClose={handleCloseModal}
        movie={selectedMovie}
      />
    </div>
  );
}

export default App;