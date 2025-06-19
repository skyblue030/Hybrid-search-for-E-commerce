# (管理資料庫連線)
# app/database.py
import os
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sentence_transformers import SentenceTransformer
import chromadb
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path='./.env')

DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "your_password")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "ecommerce_rag")
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# --- 更新為電影資料庫的設定 ---
# 智慧地計算出專案根目錄，並組合出絕對路徑
# 這讓路徑設定不再受執行指令時的所在位置影響
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
VECTOR_DB_PATH = os.path.join(PROJECT_ROOT, "chroma_db_movies")
# -------------------------
COLLECTION_NAME = "movie_plots"
EMBEDDING_MODEL_NAME = 'BAAI/bge-m3'
DEVICE = "cuda"

try:
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    logger.info("成功初始化 PostgreSQL 連線池。")

    chroma_client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
    collection = chroma_client.get_collection(name=COLLECTION_NAME)
    logger.info("成功連接到現有的 ChromaDB 集合。")

    embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=DEVICE)
    logger.info("成功載入嵌入模型。")
except Exception as e:
    logger.error(f"初始化資料庫或模型時發生錯誤: {e}", exc_info=True)
    raise e

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()