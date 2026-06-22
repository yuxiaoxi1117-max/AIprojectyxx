# Open WebUI + Dify 集成

使用 Docker Compose 将 [Open WebUI](https://github.com/open-webui/open-webui) 接入已有的 Dify 服务。

## 前提条件

- Docker & Docker Compose 已安装
- Dify 服务已在内网部署并可访问
- 已在 Dify 中创建 App 并获取 API Key

## 快速开始

**1. 克隆项目**

```bash
git clone https://github.com/yuxiaoxi1117-max/aiprojectyxx.git
cd aiprojectyxx
```

**2. 配置环境变量**

```bash
cp .env.example .env
```

编辑 `.env`，填写您的 Dify 内网地址和 API Key：

```env
DIFY_API_BASE_URL=http://192.168.1.100   # 替换为您的 Dify 内网地址
DIFY_API_KEY=app-xxxxxxxxxxxxxxxxxxxx    # 替换为您的 Dify App API Key
WEBUI_NAME=Open WebUI + Dify
```

**3. 启动服务**

```bash
docker compose up -d
```

**4. 访问 Open WebUI**

打开浏览器访问：`http://localhost:3000`

首次访问需注册管理员账号。

## 获取 Dify API Key

1. 登录 Dify 控制台
2. 进入目标 App → **API 访问**
3. 复制 **API 密钥**（格式：`app-xxx...`）

## 目录结构

```
.
├── docker-compose.yml   # 服务编排配置
├── .env.example         # 环境变量模板
├── .env                 # 实际配置（不提交到 Git）
└── README.md
```

## 常用命令

```bash
# 启动
docker compose up -d

# 查看日志
docker compose logs -f

# 停止
docker compose down

# 更新镜像
docker compose pull && docker compose up -d
```
