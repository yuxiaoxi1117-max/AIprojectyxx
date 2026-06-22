# Open WebUI + Dify 集成部署

将 [Open WebUI](https://github.com/open-webui/open-webui) 接入已有的 Dify 服务，通过 [Open WebUI Pipelines](https://github.com/open-webui/pipelines) 桥接两者的 API 格式差异。

## 架构

```
浏览器
  └─▶ Open WebUI (3000)
          └─▶ Pipelines (9099)          ← dify_pipeline.py 运行于此
                  └─▶ Dify 内网服务
```

Dify 的 API 格式与 OpenAI 不同，Pipelines 负责将 Open WebUI 发出的 OpenAI 格式请求转换为 Dify 的 `/v1/chat-messages` 格式，并将 Dify 的 SSE 流转换回 OpenAI 流式格式。

## 快速开始

**方式一：交互式向导（推荐）**

```bash
git clone https://github.com/yuxiaoxi1117-max/aiprojectyxx.git
cd aiprojectyxx
chmod +x setup.sh
./setup.sh
```

**方式二：手动配置**

```bash
git clone https://github.com/yuxiaoxi1117-max/aiprojectyxx.git
cd aiprojectyxx
cp .env.example .env
# 编辑 .env，填写 DIFY_BASE_URL 和 DIFY_API_KEY
docker compose up -d
```

## 配置说明

编辑 `.env` 文件：

| 变量 | 说明 | 示例 |
|------|------|------|
| `DIFY_BASE_URL` | Dify 服务地址（不含 `/v1`） | `http://192.168.1.100` |
| `DIFY_API_KEY` | Dify App API Key | `app-xxx...` |
| `DIFY_APP_NAME` | Open WebUI 中显示的模型名 | `我的助手` |
| `OPEN_WEBUI_PORT` | 访问端口（默认 3000） | `3000` |
| `WEBUI_SECRET_KEY` | 安全密钥（请修改） | 随机字符串 |

### 获取 Dify API Key

1. 登录 Dify 控制台
2. 进入目标应用 → **API 访问**
3. 复制 API 密钥（格式：`app-xxx...`）

## 目录结构

```
.
├── docker-compose.yml         # 服务编排
├── pipelines/
│   └── dify_pipeline.py       # Dify ↔ OpenAI API 桥接管道
├── .env.example               # 配置模板
├── .env                       # 实际配置（不提交到 Git）
├── setup.sh                   # 交互式部署脚本
└── README.md
```

## 常用命令

```bash
# 启动
docker compose up -d

# 查看日志
docker compose logs -f

# 查看 Pipeline 日志
docker compose logs -f pipelines

# 停止
docker compose down

# 更新镜像
docker compose pull && docker compose up -d
```

## 使用方式

1. 访问 `http://localhost:3000`，首次注册管理员账号
2. 在对话界面的模型下拉框中选择 `Dify: <你配置的名称>`
3. 开始对话，每个会话的 Dify `conversation_id` 会自动维护

## 注意事项

- 确保运行 Docker 的机器可以访问 Dify 内网地址
- 如果 Dify 和 Docker 在同一台机器，`DIFY_BASE_URL` 填 `http://host.docker.internal`
- `.env` 文件包含密钥，已通过 `.gitignore` 排除，不会提交到 Git
