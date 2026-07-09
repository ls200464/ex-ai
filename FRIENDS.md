# 💔 白嫖指南 — 给朋友看的

一句话说明：**导入你和前任的微信/QQ聊天记录，AI 提取 ta 的人格，然后你可以跟 "ta" 聊天。**

---

## 准备工作（只做一次）

### 第 1 步：安装两个环境

| 你需要装什么 | 下载地址 | 注意事项 |
|-------------|---------|---------|
| **Python** | https://www.python.org/downloads/ | 安装时 **勾选**"Add Python to PATH" |
| **Node.js** | https://nodejs.org/ | 下载 **LTS** 版本，一路下一步 |

装完后验证一下（可选）：

```bash
python --version   # 应该显示 Python 3.11 或更高
node --version     # 应该显示 v20 或更高
```

### 第 2 步：获取 AI 的 API Key

免费，新用户送 500 万 token，够你聊很久。

1. 打开 https://platform.deepseek.com/api_keys
2. 注册账号
3. 点「创建 API Key」→ 复制保存好

---

## 一键启动

打开终端（PowerShell 或 CMD），粘贴以下命令：

```bash
git clone https://github.com/ls200464/ex-ai.git
cd ex-ai
setup.bat
```

脚本会问你两个问题：

1. **DeepSeek API Key** → 粘贴第 2 步拿到的 key
2. **随机密钥** → 随便打一串字母数字（用来加密登录密码的）

然后自动安装、启动。看到这行就说明好了：

```
前端启动在:  http://localhost:3000
```

---

## 开始使用

### 打开浏览器 → http://localhost:3000

#### ① 注册账号

点右上角「注册」→ 填邮箱和密码 → 搞定。每个人数据完全独立，互不可见。

#### ② 创建 Persona

点「+ 新建 Persona」→ 起个名字（比如 `yun-meng-ze`、`qian-nv-you`）→ 填个显示名。

#### ③ 上传聊天记录

进入 Persona 详情页 →「📁 源文件」标签 → 上传更多记录。

**怎么导出聊天记录？**

| 平台 | 操作 |
|------|------|
| 微信 | 聊天窗口 → 右上角 `...` → 更多 → 导出聊天记录 → 保存 .txt |
| QQ | 聊天窗口 → 右上角 `≡` → 导出消息记录 → 选 .txt 格式 |

上传后系统自动解析 + AI 提取，等进度条走完就行。

#### ④ 开始对话

状态显示「就绪」后，点「💬 开始对话」。用 ta 的语气、说话方式跟你聊，还会自然提到你们的共同回忆。

---

## 小贴士

| 你想干嘛 | 怎么操作 |
|---------|---------|
| 重新生成不满意的回复 | 鼠标悬停 AI 回复 → 🔄 |
| 删除某条消息 | 鼠标悬停 → ✕ |
| 清除所有记忆重新提取 | Persona 详情页 →「🗑️ 清除并重新提取」 |
| 下次再用 | 重新跑 `setup.bat` |
| 退出 | 关掉命令行窗口 |

---

## 常见问题

**Q: 关掉窗口后下次怎么启动？**

不需要重新安装。打开终端，进到 ex-ai 目录，分别开两个窗口：

```bash
# 窗口 1 - 后端
cd ex-ai/backend
uvicorn app.main:app --port 8000

# 窗口 2 - 前端
cd ex-ai/frontend
npm run dev
```

或者直接再跑一次 `setup.bat`（会跳过已安装的依赖）。

**Q: AI 会编造不存在的事情吗？**

不会。系统告诉 AI：只能从你们的聊天记录里获取事实信息。如果记录里没有，AI 会说「没玩过」「不知道」。

**Q: 我的聊天记录会被上传到别的地方吗？**

不会。所有数据都存在你电脑上（`backend/exskill.db`），对话直接调用 DeepSeek API，没有中间服务器。

**Q: API Key 用完了怎么办？**

去 https://platform.deepseek.com 充值，很便宜。或者编辑 `backend/.env` 换成其他 API（OpenAI / Claude 都支持）。
