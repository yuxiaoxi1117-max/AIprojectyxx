#!/usr/bin/env bash
set -e

echo "=== Open WebUI + Dify 部署向导 ==="

if [ ! -f .env ]; then
    cp .env.example .env
    echo "已生成 .env 文件，请填写以下配置："
    echo ""
    read -rp "Dify 内网地址 (如 http://192.168.1.100): " dify_url
    read -rp "Dify App API Key (app-xxx...): " dify_key
    read -rp "在 Open WebUI 中显示的名称 [Dify]: " app_name
    app_name=${app_name:-Dify}

    sed -i "s|DIFY_BASE_URL=.*|DIFY_BASE_URL=${dify_url}|" .env
    sed -i "s|DIFY_API_KEY=.*|DIFY_API_KEY=${dify_key}|" .env
    sed -i "s|DIFY_APP_NAME=.*|DIFY_APP_NAME=${app_name}|" .env

    echo ""
    echo ".env 已写入配置。"
fi

echo ""
echo "启动服务..."
docker compose up -d

echo ""
echo "✓ 启动完成！"
echo "  访问地址：http://localhost:$(grep OPEN_WEBUI_PORT .env | cut -d= -f2 || echo 3000)"
echo ""
echo "首次使用请注册管理员账号。"
echo "模型列表中选择 'Dify: ${app_name:-Dify}' 即可开始对话。"
