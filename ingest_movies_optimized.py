# ingest_movies_optimized.py
# 使用批次處理大幅優化資料導入效能

import os
import pandas as pd
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv
import ast
import time

# --- 日誌設定 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- 環境變數與常數設定 ---
load_dotenv(dotenv_path='./.env')

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_rag")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

VECTOR_DB_PATH = "./chroma_db_movies"
COLLECTION_NAME = "movie_plots"
EMBEDDING_MODEL_NAME = 'BAAI/bge-m3'
DEVICE = "cuda" # 或者 "cpu"
BATCH_SIZE = 256 # 設定批次大小，可根據您的 VRAM/RAM 調整

def parse_genres(genres_str):
    try:
        genres_list = ast.literal_eval(genres_str)
        if isinstance(genres_list, list):
            return [g['name'] for g in genres_list if 'name' in g]
        return []
    except (ValueError, SyntaxError):
        return []

def main():
    start_time = time.time()
    logger.info("--- 開始電影資料導入流程 (優化版) ---")

    # 1. 初始化資料庫連線 (保持不變)
    try:
        engine = create_engine(DATABASE_URL)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()
        logger.info("成功連接到 PostgreSQL 資料庫。")
    except Exception as e:
        logger.error(f"連接 PostgreSQL 失敗: {e}", exc_info=True)
        return

    # --- 新增：建立 movies 資料表 (如果不存在) ---
    try:
        create_table_sql = text("""
            CREATE TABLE IF NOT EXISTS movies (
                id INTEGER PRIMARY KEY,
                title TEXT,
                overview TEXT,
                genres TEXT[],
                release_year INTEGER,
                vote_average FLOAT
            );
        """)
        db_session.execute(create_table_sql)
        db_session.commit()
        logger.info("成功檢查/建立 'movies' 資料表。")
    except Exception as e:
        logger.error(f"建立 'movies' 資料表失敗: {e}", exc_info=True)
        db_session.close()
        return

    # 2. 初始化向量資料庫和模型 (保持不變)
    try:
        embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=DEVICE)
        chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        try:
            chroma_client.delete_collection(name=COLLECTION_NAME)
            logger.info(f"已刪除舊的 Chroma 集合: {COLLECTION_NAME}")
        except Exception: pass
        collection = chroma_client.create_collection(name=COLLECTION_NAME)
        logger.info("成功初始化 ChromaDB 和嵌入模型。")
    except Exception as e:
        logger.error(f"初始化 ChromaDB 或模型失敗: {e}", exc_info=True)
        db_session.close()
        return

    # 3. 讀取並處理 CSV 資料 (保持不變)
    try:
        # --- 修改：使用更穩健的路徑建構 ---
        # ingest_movies_optimized.py 位於容器內的 /app/ingest_movies_optimized.py (如果從 entrypoint.sh 執行)
        # 或者在本地執行時，位於專案的根目錄。
        script_dir = os.path.dirname(os.path.abspath(__file__)) # 獲取腳本所在的目錄
        csv_path = os.path.join(script_dir, 'data', 'movies_metadata.csv') # 解析為相對於腳本位置的路徑
        df = pd.read_csv(csv_path, low_memory=False)
        
        df = df[pd.to_numeric(df['id'], errors='coerce').notnull()]
        df['id'] = df['id'].astype(int)
        
        logger.info("正在解析 'genres' 欄位...")
        df['genres_list'] = df['genres'].apply(parse_genres)
        
        df.drop(columns=['genres'], inplace=True)
        logger.info("已刪除原始 'genres' 欄位，避免欄位名稱重複。")

        df['release_date'] = pd.to_datetime(df['release_date'], errors='coerce')
        df.dropna(subset=['release_date'], inplace=True)
        df['release_year'] = df['release_date'].dt.year
        df['vote_average'] = pd.to_numeric(df['vote_average'], errors='coerce').fillna(0)
        df.dropna(subset=['title', 'overview'], inplace=True)
        df = df[df['overview'] != '']
        df.drop_duplicates(subset=['id'], inplace=True)
        
        logger.info(f"成功清理資料，準備處理 {len(df)} 筆電影。")
    except Exception as e:
        logger.error(f"讀取或清理 CSV 檔案時發生錯誤: {e}", exc_info=True)
        db_session.close()
        return

    # --- 主要變更點: 使用批次處理 ---
    logger.info(f"開始批次處理，每批次大小為 {BATCH_SIZE}...")
    
    # 準備執行 SQL 的語句
    sql_insert = text("""
        INSERT INTO movies (id, title, overview, genres, release_year, vote_average)
        VALUES (:id, :title, :overview, :genres, :release_year, :vote_average)
        ON CONFLICT (id) DO NOTHING;
    """)

    # 遍歷 DataFrame 的批次
    for i in range(0, len(df), BATCH_SIZE):
        batch_df = df.iloc[i:i+BATCH_SIZE]
        
        # --- 批次準備 ---
        ids_list = batch_df['id'].astype(str).tolist()
        texts_to_embed = ( "電影標題: " + batch_df['title'] + ". 劇情摘要: " + batch_df['overview']).tolist()
        postgres_records = batch_df.rename(columns={'genres_list': 'genres'}).to_dict('records')
        # --- 修正後的程式碼 ---
        # 我們需要將 id, title, year 都存入元數據
        chroma_meta_df = batch_df[['id', 'title', 'release_year']].copy()
        chroma_meta_df.rename(columns={'release_year': 'year'}, inplace=True)
        # 確保元數據中的 'id' 也是字串，以便和 ChromaDB 的主鍵 ID 進行比對
        chroma_meta_df['id'] = chroma_meta_df['id'].astype(str)
        metadatas_list = chroma_meta_df.to_dict('records')

        # --- 批次執行 ---
        # 1. 一次性為整個批次編碼
        embeddings = embedding_model.encode(
            texts_to_embed, 
            normalize_embeddings=True,
            show_progress_bar=False # 在批次處理中關閉內部進度條
        ).tolist()
        
        # 2. 一次性將整個批次加入 Chroma
        collection.add(ids=ids_list, embeddings=embeddings, metadatas=metadatas_list)
        
        # 3. 一次性將整個批次寫入 PostgreSQL
        db_session.execute(sql_insert, postgres_records)
        
        logger.info(f"已處理 {min(i + BATCH_SIZE, len(df))}/{len(df)} 筆電影...")

    # --- 最終提交 ---
    try:
        logger.info("所有批次處理完畢，正在提交到資料庫...")
        db_session.commit()
        logger.info("成功將所有電影資料提交到 PostgreSQL。")
    except Exception as e:
        logger.error(f"提交資料庫時發生錯誤: {e}", exc_info=True)
        db_session.rollback()
    finally:
        db_session.close()

    end_time = time.time()
    logger.info(f"--- 電影資料導入流程全部完成！成功導入 {collection.count()} 筆電影。---")
    logger.info(f"總耗時: {end_time - start_time:.2f} 秒。")


if __name__ == "__main__":
    main()