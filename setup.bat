@echo off
chcp 65001 >nul
title ex-skill 安装

echo.
echo   💔 ex-skill — 把前任蒸馏成 AI
echo   ================================
echo.

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 请先安装 Python 3.11+: https://www.python.org/downloads/
    echo   安装时记得勾选 "Add Python to PATH"
    pause
    exit /b 1
)

:: Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo   [错误] 请先安装 Node.js: https://nodejs.org/
    echo   下载 LTS 版本安装即可
    pause
    exit /b 1
)

echo   [1/4] 配置环境变量...

:: Create .env if not exists
if not exist backend\.env (
    echo 请先创建 backend\.env 文件，填入你的 DeepSeek API Key
    echo.
    echo 获取 API Key: https://platform.deepseek.com/api_keys
    echo 注册就送500万token，够用很久
    echo.
    set /p DEEPSEEK_KEY="请输入你的 DeepSeek API Key: "
    echo.
    set /p JWT_SECRET="请输入一个随机密钥（随便打一串字母数字）: "

    echo DATABASE_URL=sqlite+aiosqlite:///./exskill.db > backend\.env
    echo LLM_PROVIDER=deepseek >> backend\.env
    echo LLM_MODEL=deepseek-chat >> backend\.env
    echo LLM_TEMPERATURE=0.7 >> backend\.env
    echo LLM_MAX_TOKENS=4096 >> backend\.env
    echo DEEPSEEK_API_KEY=!DEEPSEEK_KEY! >> backend\.env
    echo DEEPSEEK_BASE_URL=https://api.deepseek.com/v1 >> backend\.env
    echo EMBEDDING_PROVIDER=openai >> backend\.env
    echo EMBEDDING_MODEL=text-embedding-3-small >> backend\.env
    echo JWT_SECRET_KEY=!JWT_SECRET! >> backend\.env
    echo JWT_ALGORITHM=HS256 >> backend\.env
    echo ACCESS_TOKEN_EXPIRE_MINUTES=1440 >> backend\.env
    echo CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000 >> backend\.env

    echo   [OK] 配置已创建
) else (
    echo   [OK] .env 已存在，跳过
)

echo   [2/4] 安装后端依赖...
cd backend
pip install -r requirements.txt -q
cd ..

echo   [3/4] 安装前端依赖...
cd frontend
call npm install --silent
cd ..

echo   [4/4] 启动！
echo.
echo   ================================
echo   后端启动在:  http://localhost:8000
echo   前端启动在:  http://localhost:3000
echo   ================================
echo.
echo   前端窗口关闭后后端也会停止。
echo.

:: Start backend in background
start "ex-skill 后端" cmd /c "cd /d %cd%\backend && uvicorn app.main:app --port 8000"

:: Wait for backend
echo   等待后端启动...
timeout /t 3 /nobreak >nul

:: Start frontend
echo   启动前端...
cd frontend
call npm run dev
