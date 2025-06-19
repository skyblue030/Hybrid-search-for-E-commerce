# 智慧電影搜尋與問答系統 (Hybrid Search for Movie & RAG Response)

![Python](https://img.shields.io/badge/Python-3.11+-blue?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![React](https://img.shields.io/badge/React-18.2.0-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker)

這是一個功能完整的全端應用程式，旨在展示如何結合傳統資料庫與現代 AI 技術，打造一個強大的智慧搜尋與問答系統。使用者不僅可以透過模糊的語意來搜尋電影，還能針對特定的電影進行深入的對話式問答。

## 核心功能

* **混合搜尋 (Hybrid Search)**：結合了 PostgreSQL 的結構化篩選（如類型、年份、評分）和 ChromaDB 的向量語意搜尋（理解劇情描述的意義），提供精準且人性化的搜尋體驗。
* **RAG 智慧問答 (Retrieval-Augmented Generation)**：使用者可以針對搜尋到的任一電影，提出具體問題。系統會利用該電影的劇情摘要作為上下文，呼叫大型語言模型 (Google Gemini) 來產生基於事實的、可靠的回答。

## 專案架構

本專案採用前後端分離的架構，並透過雙資料庫模式實現複雜的 AI 搜尋功能。

```
+-----------------+      (HTTP API)      +---------------------+
|  React 前端      |--------------------->|  FastAPI 後端      |
| (用戶介面)       |                      |  (業務邏輯)         |
+-----------------+                      +----------┬----------+
                                                    │
                           ┌────────────────────────┴──────────────────────┐
                           │                                               │
               (精準篩選、儲存元數據)                                   (語意搜尋、儲存向量)
                           ▼                                               ▼
+---------------------------------------+       +------------------------------------+
|  PostgreSQL (關聯式資料庫)             |        |  ChromaDB (向量資料庫)              |
| - 儲存電影的詳細資料 (ID, 標題, 類型等)  |        | - 儲存劇情摘要的語意向量             |
+---------------------------------------+        +------------------------------------+
                           ▲                                               │ (RAG 上下文)
                           │ (檢索電影資料)                                 │
                           │                                               ▼
                           └─────────────────────┐               +-----------------------+
                                                 │ (Prompt)      | Google Gemini API     |
                                                 └──────────────>| (大型語言模型)         |
                                                                 +-----------------------+
```

## 技術棧 (Technology Stack)

* **後端**: Python 3.11+, FastAPI, Uvicorn
* **前端**: React, JavaScript (ES6+), CSS
* **資料庫**:
    * **結構化資料**: PostgreSQL
    * **向量資料**: ChromaDB
* **AI & ML**:
    * **文字嵌入模型**: `BAAI/bge-m3` (from Hugging Face)
    * **語言生成模型**: Google Gemini Pro
* **核心 Python 函式庫**: `sqlalchemy`, `psycopg2-binary`, `sentence-transformers`, `google-generativeai`, `pandas`

## 專案設定與啟動指南

#### 1. 前置需求

* Python 3.10 或以上版本
* Node.js 16 或以上版本 (包含 npm)
* PostgreSQL 資料庫服務已安裝並正在運行
* Git

#### 2. 後端設定

1.  **複製專案**：
    ```bash
    git clone [https://github.com/skyblue030/Hybrid-search-for-E-commerce.git](https://github.com/skyblue030/Hybrid-search-for-E-commerce.git)
    cd Hybrid-search-for-E-commerce
    ```

2.  **建立虛擬環境並安裝依賴**：
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS / Linux
    # source .venv/bin/activate

    pip install -r requirements.txt
    ```
    > **注意**: 如果您還沒有 `requirements.txt` 檔案，請在您的虛擬環境中執行 `pip freeze > requirements.txt` 來產生它。

3.  **設定環境變數**：
    * 將 `.env.example` 檔案（如果沒有請手動建立）複製為 `.env`。
    * 在 `.env` 檔案中填入您的 PostgreSQL 連線資訊和 Google Gemini API 金鑰。
    ```
    DB_USER="your_postgres_user"
    DB_PASSWORD="your_postgres_password"
    DB_HOST="localhost"
    DB_PORT="5432"
    DB_NAME="ecommerce_rag" # 您建立的資料庫名稱
    GOOGLE_API_KEY="your_gemini_api_key"
    ```

4.  **設定資料庫並導入資料**：
    * 手動在您的 PostgreSQL 中建立一個新的資料庫 (例如 `ecommerce_rag`)。
    * 連線到該資料庫，並執行 `ingest_movies_optimized.py` 中 `CREATE TABLE` 的 SQL 指令來建立 `movies` 資料表。
    * 下載專案所需的資料集 (如 `movies_metadata.csv`) 並放置在 `./data/` 資料夾下。
    * 執行資料導入腳本：
        ```bash
        python ingest_movies_optimized.py
        ```

5.  **啟動後端伺服器**：
    ```bash
    # 從專案根目錄執行
    uvicorn app.main:app --reload
    ```
    伺服器將運行在 `http://127.0.0.1:8000`。

#### 3. 前端設定

1.  **進入前端資料夾並安裝依賴**：
    ```bash
    cd frontend
    npm install
    ```

2.  **啟動前端開發伺服器**：
    ```bash
    npm start
    ```
    前端頁面將會自動在瀏覽器中打開 `http://localhost:3000`。

## API 端點說明

* `POST /search/`: 執行混合搜尋。接收一個包含 `query` 和 `filters` 的 JSON 主體。
* `POST /ask/{movie_id}`: 對指定的電影進行 RAG 問答。接收一個包含 `question` 的 JSON 主體。

## 未來可行的優化方向

* **容器化**: 使用 Docker 和 Docker Compose 將所有服務（FastAPI, React, PostgreSQL, Redis）打包，實現一鍵啟動與部署。
* **快取機制**: 引入 Redis，為熱門的搜尋結果增加快取，降低延遲並減少資料庫負載。
* **背景任務**: 將 RAG 問答的 LLM 請求改為使用 Celery 在背景執行，避免 API 長時間等待，提升前端使用者體驗。
* **生產級部署**: 使用 NGINX 作為反向代理，Gunicorn 管理 FastAPI 的多個 Worker，實現負載平衡與高併發處理。

---