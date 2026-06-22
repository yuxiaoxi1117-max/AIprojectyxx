# AI 助手平台 — Open WebUI + Dify 集成

自定义门户 + [Open WebUI Pipelines](https://github.com/open-webui/pipelines) 将多个 Dify 应用集成到统一界面。

## 界面预览

```
┌──────────────────────────────────────────────────────┐
│ ✨ AI 平台                                            │
│                                                      │
│  💬 对话   ←── 主页，与默认 Dify App 对话             │
│  🛠️ 工具   ←── 多个 Dify App 卡片，点击打开独立对话   │
│                                                      │
└──────────────────────────────────────────────────────┘
```

## 架构

```
浏览器
  └─▶ nginx 门户 (:80)
        ├── / → 自定义前端（对话 + 工具页签）
        └── /api/ → Pipelines (:9099)  [注入 API Key]
                        └── dify_pipeline.py
                                └── Dify 内网各 App API
```

Pipelines 服务器自动加载 `pipelines/dify_pipeline.py`，读取 `dify_apps.json` 将多个 Dify 应用注册为独立模型。

## 快速开始

```bash
git clone https://github.com/yuxiaoxi1117-max/aiprojectyxx.git
cd aiprojectyxx

# 1. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 DIFY_BASE_URL

# 2. 配置 Dify 应用列表
# 编辑 dify_apps.json，填写各 App 的 api_key

# 3. 启动
docker compose up -d

# 4. 访问
# 自定义门户：http://localhost
# Open WebUI：http://localhost:3000（可选）
```

## 配置 Dify 应用

编辑 `dify_apps.json`：

```json
[
  {
    "id": "general-chat",
    "name": "通用助手",
    "description": "主页默认对话助手",
    "api_key": "app-xxx",
    "icon": "🤖",
    "default": true
  },
  {
    "id": "customer-service",
    "name": "客服助手",
    "description": "处理客户咨询问题",
    "api_key": "app-yyy",
    "icon": "💬"
  }
]
```

- `default: true` 的 App 出现在**对话**主页
- 其余 App 出现在**工具**页签的卡片中
- 每个 App 的 `api_key` 在 Dify 控制台 → 应用 → API 访问 中获取

## 环境变量（.env）

| 变量 | 说明 |
|------|------|
| `DIFY_BASE_URL` | Dify 服务内网地址（不含 `/v1`） |
| `PORTAL_PORT` | 门户访问端口（默认 80） |
| `OPEN_WEBUI_PORT` | Open WebUI 端口（默认 3000，可选） |
| `PIPELINES_API_KEY` | 内部认证密钥（保持默认即可） |
| `WEBUI_SECRET_KEY` | Open WebUI 安全密钥（请修改） |

## 目录结构

```
.
├── docker-compose.yml          # 服务编排
├── nginx.conf.template         # nginx 配置模板（envsubst 注入 API Key）
├── dify_apps.json              # Dify 应用列表配置
├── portal/
│   ├── index.html              # 门户主页
│   ├── style.css               # 暗色主题样式
│   └── app.js                  # 流式对话逻辑
├── pipelines/
│   └── dify_pipeline.py        # OpenAI API ↔ Dify API 桥接
├── .env.example                # 环境变量模板
└── README.md
```

## 常用命令

```bash
docker compose up -d            # 启动
docker compose logs -f          # 查看日志
docker compose logs -f pipelines  # 查看 Pipeline 日志
docker compose down             # 停止
docker compose pull && docker compose up -d  # 更新镜像
```

## 注意事项

- Dify 同机部署时 `DIFY_BASE_URL` 填 `http://host.docker.internal`
- `.env` 和 `dify_apps.json` 中的 API Key 不会提交到 Git（`.gitignore` 已配置）
- 工具页签会显示所有 `default` 字段不为 `true` 的 App
