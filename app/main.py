# (FastAPI 主程式)
# app/main.py (修改後，支援直接執行)

# --- 新增：路徑修正 ---
# 這是實現直接執行的關鍵。
# 它會將專案的根目錄 (Hybrid-search-for-E-commerce) 加入到 Python 的搜尋路徑中。
import sys
import os
import json

# 將 'app' 資料夾的上一層目錄 (也就是專案根目錄) 加入到 sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# -------------------------

import logging
import uvicorn # <--- 新增 uvicorn 的導入
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
import google.generativeai as genai

# --- 變更：從相對導入改成絕對導入 ---
# 因為我們已經將專案根目錄加入路徑，現在可以用 'app' 作為起點來導入
from app import database, models 
# ------------------------------------

# --- Gemini 設定 (保持不變) ---
try:
    genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
    llm_model = genai.GenerativeModel('gemini-1.5-flash-002')
    logging.info("成功設定 Gemini API。")
except Exception as e:
    llm_model = None
    logging.error(f"設定 Gemini API 失敗: {e}")
# -------------------------

app = FastAPI(
    title="智慧電影搜尋與問答 API",
    description="結合精準篩選、語意搜尋與 RAG 問答的智慧引擎。",
    version="1.1.0",
)

logger = logging.getLogger(__name__)

# --- CORS 設定 (保持不變) ---
origins = ["http://localhost", "http://localhost:3000"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# -------------------------

# --- API 端點 (保持不變) ---
@app.post("/search/", response_model=models.SearchResponse)
def hybrid_search(request: models.SearchRequest, db: Session = Depends(database.get_db)):
    # ... (這個函式的內部邏輯完全不用變)
    # --- 1. 預篩選 (PostgreSQL) ---
    where_clauses = []
    params = {}

    if request.filters:
        if request.filters.genre:
            where_clauses.append("genres @> ARRAY[:genre]")
            params["genre"] = request.filters.genre
        if request.filters.min_year:
            where_clauses.append("release_year >= :min_year")
            params["min_year"] = request.filters.min_year
        if request.filters.min_rating:
            where_clauses.append("vote_average >= :min_rating")
            params["min_rating"] = request.filters.min_rating
    
    sql_query = "SELECT id FROM movies"
    if where_clauses:
        sql_query += " WHERE " + " AND ".join(where_clauses)
    
    filtered_ids_result = db.execute(text(sql_query), params)
    filtered_ids = [str(row[0]) for row in filtered_ids_result]

    if not filtered_ids:
        return models.SearchResponse(count=0, results=[])

    # --- 2. 語意排序 (ChromaDB) ---
    query_embedding = database.embedding_model.encode(
        request.query, normalize_embeddings=True
    ).tolist()

    chroma_results = database.collection.query(
        query_embeddings=[query_embedding],
        n_results=min(request.top_k, len(filtered_ids)),
        where={"id": {"$in": filtered_ids}}
    )
    
    sorted_ids = [int(id_str) for id_str in chroma_results['ids'][0]]

    if not sorted_ids:
        return models.SearchResponse(count=0, results=[])

    # --- 3. 獲取最終結果 (PostgreSQL) ---
    final_products_result = db.execute(
        text("SELECT * FROM movies WHERE id IN :ids"), 
        {"ids": tuple(sorted_ids)}
    ).mappings().all()
    
    products_map = {p['id']: p for p in final_products_result}
    final_ordered_products = [models.Movie.model_validate(products_map[pid]) for pid in sorted_ids if pid in products_map]

    return models.SearchResponse(count=len(final_ordered_products), results=final_ordered_products)

@app.post("/ask/{movie_id}", response_model=models.AskResponse, tags=["Q&A"])
def ask_about_movie(movie_id: int, request: models.AskRequest, db: Session = Depends(database.get_db)):
    """
    對單一電影進行 RAG 問答 (採用 MCP 思想)。
    """
    if not llm_model:
        raise HTTPException(status_code=500, detail="LLM 服務未成功初始化")

    # 1. 檢索 (Retrieval) - 這一步不變
    movie = db.execute(text("SELECT title, overview FROM movies WHERE id = :id"), {"id": movie_id}).first()
    if not movie:
        raise HTTPException(status_code=404, detail="找不到該 ID 的電影")

    # 2. 增強 (Augmentation) - 採用 MCP 結構來建立 Prompt
    #   首先，建立一個代表 MCP 的 Python 字典
    mcp_data = {
        "instructions": [
            "You are a helpful movie expert.",
            "Please answer the user's question concisely in Traditional Chinese, based *only* on the information provided in the 'context' block.",
            "If the answer is not found within the context, you must respond with '根據提供的摘要，我無法回答這個問題。'"
        ],
        "context": {
            "Movie Title": movie.title,
            "Plot Summary": movie.overview
        },
        "conversation": [
            {"role": "human", "content": request.question}
        ]
    }

    #   然後，將這個結構化的字典轉換成一個清晰的、給 LLM 閱讀的字串
    #   我們用 YAML-like 的格式來呈現，可讀性最好
    prompt_string = f"""
                    INSTRUCTIONS:
                    {chr(10).join(f'- {i}' for i in mcp_data["instructions"])}

                    CONTEXT:
                    ---
                    {json.dumps(mcp_data['context'], ensure_ascii=False, indent=2)}
                    ---

                    CONVERSATION:
                    Human: {mcp_data['conversation'][0]['content']}
                    Assistant:
                    """

    # 3. 生成 (Generation) - 這一步不變
    try:
        # 將格式化後的 prompt 字串發送給 Gemini
        response = llm_model.generate_content(prompt_string)
        answer = response.text
    except Exception as e:
        logger.error(f"呼叫 Gemini API 時發生錯誤: {e}")
        raise HTTPException(status_code=500, detail="生成回答時發生錯誤")

    return models.AskResponse(
        movie_id=movie_id,
        question=request.question,
        answer=answer
    )
# -------------------------

# --- 新增：主程式啟動入口 ---
if __name__ == "__main__":
    # 這段程式碼只有在 main.py 被「直接執行」時才會觸發
    # 它會以程式化的方式啟動 Uvicorn 伺服器
    logger.info("以直接執行模式啟動伺服器...")
    uvicorn.run(app, host="127.0.0.1", port=8000)
# -------------------------