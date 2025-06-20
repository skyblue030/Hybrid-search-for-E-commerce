#!/bin/sh
set -e

# 應用程式模組實際所在的目錄 (絕對路徑)
ACTUAL_APP_ABSOLUTE_DIR="/app/app"

# Check if the 'movies' table exists using the application's database URL logic
echo "Checking if 'movies' table exists..."
# 使用 Python 腳本檢查資料表是否存在，並利用 app.database 中的 DATABASE_URL 邏輯
if ! /app/.venv/bin/python <<EOF
import sys
import os
import psycopg2
from dotenv import load_dotenv

# .env 檔案在容器內的 /app/.env
load_dotenv(dotenv_path='/app/.env')

DB_USER_val = os.getenv("DB_USER", "postgres")
DB_PASSWORD_val = os.getenv("DB_PASSWORD", "your_password")
# DB_HOST 應由 Docker Compose 的 environment 設定為 'db'
DB_HOST_val = os.getenv("DB_HOST", "db") 
DB_PORT_val = os.getenv("DB_PORT", "5432")
DB_NAME_val = os.getenv("DB_NAME", "ecommerce_rag")
DATABASE_URL_val = f"postgresql://{DB_USER_val}:{DB_PASSWORD_val}@{DB_HOST_val}:{DB_PORT_val}/{DB_NAME_val}"

try:
    conn = psycopg2.connect(DATABASE_URL_val)
    cur = conn.cursor()
    cur.execute("SELECT 1 FROM pg_tables WHERE tablename='movies'")
    if cur.fetchone() is None:
        sys.exit(1) # 資料表不存在
    else:
        sys.exit(0) # 資料表存在
except Exception as e:
    print(f'Database check failed: {e}')
    sys.exit(1) # 檢查失敗
EOF
then
    echo "'movies' table does not exist or check failed. Running ingestion script..."
    # Run the ingestion script
    # 確保使用虛擬環境中的 python 執行腳本
    /app/.venv/bin/python /app/ingest_movies_optimized.py
    echo "Ingestion script finished."
else
    echo "'movies' table already exists. Skipping ingestion."
    # 如果資料表已存在，但 ChromaDB 集合可能被刪除或未初始化，
    # 應用程式啟動時 database.py 中的初始化邏輯會處理 ChromaDB 的連接。
    # 這裡不需要額外操作。
fi

if [ "$APP_ENV" = "production" ]; then
    echo "--- Starting Gunicorn in production mode... ---"
    # 移除偵錯用的 ls 指令，保持日誌簡潔
    echo "Current directory: $(pwd)"
    echo "Listing contents of /app:"
    ls -la /app
    echo "Attempting to chdir to '$ACTUAL_APP_ABSOLUTE_DIR' and list contents:"
    # 驗證目標目錄是否存在且可訪問
    ls -la "$ACTUAL_APP_ABSOLUTE_DIR"
    exec gunicorn --chdir "$ACTUAL_APP_ABSOLUTE_DIR" -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:8000
else
    # 移除偵錯用的 ls 指令
    echo "--- Starting Uvicorn in development mode with reload... ---"
    exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload --app-dir "$ACTUAL_APP_ABSOLUTE_DIR"
fi