# Docker 建構避坑與建構指南 (基於本次經驗)

這份指南總結了在本次專案建構 Docker 環境過程中遇到的常見問題與解決方法，希望能幫助您在未來的專案中更順利地進行 Docker 化。

---

## 一、環境設定與依賴管理 (Python 後端)

### 1. 明確依賴項 (`pyproject.toml` 或 `requirements.txt`)
* **避坑**：不要將 Python 內建標準函式庫（如 `json`, `os`, `sys`）列為專案依賴。套件管理工具 (如 `pip`, `uv`) 會嘗試從 PyPI 尋找這些套件而導致錯誤。
* **指南**：
    * 仔細檢查 `pyproject.toml` 的 `[project].dependencies` 或 `requirements.txt`，確保只包含需要從外部安裝的套件。
    * 所有運行時必要的套件（如 `fastapi`, `gunicorn`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `sentence-transformers`, `chromadb`, `google-generativeai`, `pandas`, `python-dotenv`）都應明確列出。

### 2. 鎖定檔案 (`uv.lock` 或 `requirements.txt` 的版本鎖定)
* **避坑**：當 `pyproject.toml` 修改後，如果 `uv.lock` 沒有相應更新，`uv sync --locked` 仍會使用舊的鎖定檔案，導致依賴不一致或錯誤。
* **指南**：
    * 修改 `pyproject.toml` 中的依賴後，務必在本地端執行 `uv lock` (或 `uv pip compile pyproject.toml -o uv.lock`) 來重新產生 `uv.lock` 檔案。
    * 如果使用 `requirements.txt`，建議固定版本號 (例如 `package==1.2.3`) 以確保建置的一致性。
    * 在 `Dockerfile` 中，如果使用 `uv.lock`，透過 `--mount=type=bind,source=uv.lock,target=uv.lock` 掛載本地的鎖定檔案，可以確保建置時使用的是最新的版本。

### 3. Python 版本一致性
* **避坑**：在 Docker 多階段建置中，如果 builder 階段和 final/runtime 階段使用的 Python 基礎映像版本不一致，可能會導致虛擬環境或已編譯套件不相容。
* **指南**：確保 `Dockerfile` 中所有階段的 Python 基礎映像版本（例如 `python:3.13-slim-bookworm`）保持一致。

### 4. 環境變數 (`.env` 與 Docker Compose)
* **避坑**：容器內的服務（如 FastAPI 後端）連接其他服務（如 PostgreSQL 資料庫）時，不能使用 `localhost` 或 `127.0.0.1` 作為主機名稱。
* **指南**：
    * 在 Docker Compose 網路中，應使用服務名稱 (例如 `db`) 作為主機名稱。
    * 在 `docker-compose.yml` 中，為需要連接資料庫的服務（如 `backend`）明確設定環境變數 `DB_HOST=db`。這樣設定的優先級高於 `env_file` 中的設定。
    * `env_file: - ./.env` 會將 `.env` 檔案中的變數載入到容器環境中，適用於 API 金鑰、資料庫憑證等。

---

## 二、Dockerfile 與映像建置

### 1. 工作目錄 (WORKDIR) 與檔案複製 (COPY)
* **避坑**：不清楚 `WORKDIR` 和 `COPY` 如何影響容器內的檔案結構，容易導致腳本找不到檔案 (如 `FileNotFoundError`) 或模組找不到 (如 `ModuleNotFoundError`)。
* **指南**：
    * 明確規劃容器內的檔案結構。例如，將應用程式程式碼統一放在 `/app` 下。
    * `COPY . /app` 會將建置上下文的內容複製到容器的 `/app` 目錄。如果您的應用程式在本地有一個 `app` 子目錄 (例如 `your_project/app/main.py`)，那麼在容器內它會變成 `/app/app/main.py`。
    * 在腳本 (如 `entrypoint.sh` 或 Python 腳本) 中引用檔案路徑時，要考慮到容器內的實際路徑。使用絕對路徑或基於 `os.path.dirname(os.path.abspath(__file__))` 的相對路徑通常更穩健。

### 2. 腳本執行權限與換行符
* **避坑**：從 Windows 系統複製到 Linux 容器的 shell 腳本 (`.sh`) 可能因為包含 `\r\n` 換行符而執行失敗或行為異常。
* **指南**：在 `Dockerfile` 中，執行 `ENTRYPOINT` 或 `CMD` 指定的 shell 腳本之前，務必使用以下指令來移除 `\r` 並賦予執行權限：
  ```bash
  RUN sed -i 's/\r$//' /path/to/your/script.sh && chmod +x /path/to/your/script.sh
  ```

### 3. 多階段建置
* **指南**：使用多階段建置 (如 `Dockerfile.backend` 中的 `builder` 和 `final` 階段) 是個好習慣。它可以減小最終映像的大小，只包含運行時必要的檔案和依賴。
    * 在 builder 階段安裝編譯工具和建置時依賴。
    * 在 final 階段從 builder 階段 `COPY --from=builder` 必要的產物 (如虛擬環境、應用程式碼)。

### 4. 虛擬環境
* **指南**：在 Docker 映像中為 Python 應用程式建立虛擬環境 (例如使用 `uv venv .venv` 或 `python -m venv .venv`)，並將其 `bin` 目錄加入到 `PATH` 環境變數 (`ENV PATH="/app/.venv/bin:$PATH"`)，可以隔離依賴並確保使用的是正確的 Python 和套件版本。

---

## 三、Docker Compose 設定

### 1. 服務名稱解析
* **指南**：Docker Compose 會自動為同一網路中的服務設定 DNS 解析，讓你可以使用服務名稱 (例如 `db`, `backend`) 作為主機名稱在服務間通訊。

### 2. 端口映射 (ports)
* **避坑**：忘記或錯誤設定端口映射，導致無法從主機訪問容器內的服務。
* **指南**：使用 `ports: - "HOST_PORT:CONTAINER_PORT"` (例如 `ports: - "8000:8000"`) 將容器的端口映射到主機。

### 3. 健康檢查 (healthcheck) 與服務依賴 (depends_on)
* **指南**：為資料庫等關鍵服務設定 `healthcheck`，並讓依賴它的服務 (如 `backend`) 使用 `depends_on` 的 `condition: service_healthy`，可以確保在主服務健康之前，依賴服務不會啟動，避免因服務未就緒導致的連接錯誤。

### 4. Volume 掛載 (volumes)
* **指南**：
    * 對於資料庫數據，使用命名卷 (named volumes) (例如 `postgres_data:/var/lib/postgresql/data/`) 來持久化數據，避免容器移除時數據遺失。
    * 對於開發環境的前端程式碼，使用綁定掛載 (bind mounts) (例如 `./frontend:/app`) 可以實現本地程式碼修改後，容器內即時同步，方便開發和熱重載。但要注意檔案系統事件傳遞可能存在的延遲。
    * 對於 `node_modules`，使用匿名卷 (`/app/node_modules`) 可以防止本地的 `node_modules` 覆蓋容器內由 `npm install` 產生的 `node_modules`。

### 5. GPU 支援 (如果需要)
* **指南**：如果應用程式需要 GPU (例如運行 PyTorch CUDA 模型)：
    * 確保主機已安裝 NVIDIA 驅動和 NVIDIA Container Toolkit。
    * 在 `docker-compose.yml` 的相關服務中，使用 `deploy.resources.reservations.devices` 來請求 GPU 資源。
    * 在應用程式程式碼中，將 PyTorch 等函式庫的運算裝置設定為 `"cuda"`。

---

## 四、前端與後端通訊

### 1. API 端點 URL
* **避坑**：前端 `fetch` 請求的 URL 不正確，例如使用了相對路徑 `/api/...` 而沒有設定代理，導致請求發向了前端開發伺服器本身 (通常是 `localhost:3000`) 而不是後端 API (`http://127.0.0.1:8000`)。
* **指南**：在前端的 `fetch` 呼叫中，明確使用後端 API 的完整 URL (例如 `http://127.0.0.1:8000/search/`)。或者，在開發環境中，為前端開發伺服器設定代理 (proxy) 將特定路徑 (如 `/api`) 的請求轉發到後端。

### 2. CORS (Cross-Origin Resource Sharing)
* **避坑**：後端沒有正確設定 CORS，導致瀏覽器阻止跨域請求。
* **指南**：
    * 在 FastAPI 後端，使用 `CORSMiddleware` 並正確設定 `allow_origins` (例如 `["http://localhost:3000", "http://localhost"]`)、`allow_methods`、`allow_headers` 和 `allow_credentials`。
    * **注意**：如果後端因為內部錯誤返回 500 Internal Server Error，並且沒有機會執行 CORS 中介軟體，瀏覽器仍然會報 CORS 錯誤。此時應先解決後端的 500 錯誤。

---

## 五、偵錯技巧

### 1. 日誌是你的朋友
* **後端**：`docker logs <backend_container_name>`。仔細查看 Gunicorn/Uvicorn 的啟動訊息、FastAPI 應用程式的日誌 (包括您自己添加的 `logger` 訊息) 以及任何 Python 錯誤堆疊。
* **前端**：瀏覽器開發者工具 (F12) 的 "Console" 和 "Network" 分頁。"Console"：查看 JavaScript 錯誤、CORS 錯誤。"Network"：查看 API 請求的 URL、方法、標頭、狀態碼和回應內容。

### 2. 逐步驗證
* 先確保資料庫服務健康。
* 再確保後端服務能連接資料庫並成功啟動。
* 然後測試後端 API 端點 (例如使用 `curl` 或 Postman)。
* 最後測試前端與後端的整合。

### 3. 簡化問題
如果遇到複雜問題，嘗試簡化設定。例如，暫時移除某些依賴、註解掉部分程式碼，以縮小問題範圍。

### 4. Docker 快取與本地檔案同步
* **避坑**：修改本地程式碼後，Docker 容器內的開發伺服器可能因為快取或檔案同步延遲而沒有使用最新的程式碼。
* **指南**：
    * 對於綁定掛載的程式碼，修改後嘗試硬性刷新瀏覽器 (Ctrl+Shift+R)。
    * 如果無效，執行 `docker-compose restart <service_name>` (例如 `docker-compose restart frontend`) 來強制服務重新載入。
    * 在建置映像時，如果懷疑是 Docker 建置快取導致的問題，可以使用 `docker-compose build --no-cache <service_name>`。

### 5. `entrypoint.sh` 腳本
* **指南**：
    * 在 `entrypoint.sh` 中加入 `echo` 和 `ls -la` 等指令來打印目前目錄、檢查檔案是否存在及其權限，有助於診斷路徑問題。
    * 對於需要在應用程式啟動前執行的初始化任務（如資料庫遷移、資料導入），可以在 `entrypoint.sh` 中，於啟動主應用程式 (Gunicorn/Uvicorn) 之前執行這些任務。為了避免重複執行，可以加入檢查邏輯 (例如，檢查特定資料表是否存在)。