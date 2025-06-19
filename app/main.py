# (FastAPI 主程式)
# app/main.py
import logging
from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List

from . import database, models

app = FastAPI(
    title="智慧電影搜尋 API",
    description="結合精準篩選 (PostgreSQL) 和語意搜尋 (ChromaDB) 的混合搜尋引擎。",
    version="1.0.0",
)

logger = logging.getLogger(__name__)

@app.post("/search/", response_model=models.SearchResponse)
def hybrid_search(request: models.SearchRequest, db: Session = Depends(database.get_db)):
    """
    執行混合搜尋：
    1.  **預篩選 (PostgreSQL)**：根據類型、年份、評分等條件篩選候選電影。
    2.  **語意排序 (ChromaDB)**：在候選電影中，根據使用者查詢進行語意相似度搜尋與排序。
    3.  **結果獲取 (PostgreSQL)**：獲取排序後的完整電影資訊。
    """
    # --- 1. 預篩選 (PostgreSQL) ---
    where_clauses = []
    params = {}

    if request.filters:
        if request.filters.genre:
            # 使用 @> 運算子來檢查陣列是否包含某個元素
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