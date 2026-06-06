@echo off
echo ============================================
echo   小说转剧本 - AI 辅助剧本创作工具
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    pause
    exit /b 1
)

REM 检查 Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Node.js，请先安装 Node.js 18+
    pause
    exit /b 1
)

REM 设置 Hugging Face 镜像（加速模型下载）
set HF_ENDPOINT=https://hf-mirror.com

REM 安装 Python 依赖
echo [1/3] 安装 Python 依赖...
cd backend
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [错误] Python 依赖安装失败
    pause
    exit /b 1
)
cd ..

REM 安装前端依赖
echo [2/3] 安装前端依赖...
call npm install
if %errorlevel% neq 0 (
    echo [错误] 前端依赖安装失败
    pause
    exit /b 1
)

REM 检查 .env
if not exist backend\.env (
    echo [提示] 未找到 backend\.env，从 .env.example 复制...
    copy backend\.env.example backend\.env
    echo [提示] 请编辑 backend\.env 填入你的 LLM API Key
)

echo [3/3] 启动服务...
echo.
echo 后端服务: http://localhost:8000
echo 前端页面: http://localhost:5173
echo.

REM 启动后端（新窗口）
start "Novel-to-Script Backend" cmd /c "cd backend && python main.py"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 启动前端
call npm run dev

pause
