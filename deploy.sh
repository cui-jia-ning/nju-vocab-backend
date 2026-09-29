#!/bin/bash
set -e

echo "=== NJU Vocab Filter 后端部署脚本 ==="

# 1. 安装 Python 和依赖
echo "[1/5] 安装系统依赖..."
if command -v apt &> /dev/null; then
    sudo apt update && sudo apt install -y python3 python3-pip python3-venv nginx
elif command -v yum &> /dev/null; then
    sudo yum install -y python3 python3-pip nginx
fi

# 2. 创建项目目录
APP_DIR=/opt/nju-vocab-backend
echo "[2/5] 创建项目目录 $APP_DIR ..."
sudo mkdir -p $APP_DIR
sudo cp -r ./* $APP_DIR/
cd $APP_DIR

# 3. 创建虚拟环境并安装依赖
echo "[3/5] 创建 Python 虚拟环境..."
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. 创建 .env（如果不存在）
if [ ! -f .env ]; then
    SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    cat > .env <<EOF
DATABASE_URL=sqlite:///./vocab.db
SECRET_KEY=$SECRET
ACCESS_TOKEN_EXPIRE_MINUTES=43200
EOF
    echo "   已生成 .env（含随机 SECRET_KEY）"
fi

# 5. 配置 systemd 服务
echo "[4/5] 配置系统服务..."
sudo tee /etc/systemd/system/nju-vocab.service > /dev/null <<EOF
[Unit]
Description=NJU Vocab Filter Backend
After=network.target

[Service]
User=$USER
WorkingDirectory=$APP_DIR
ExecStart=$APP_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3
Environment=PATH=$APP_DIR/venv/bin:/usr/bin

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable nju-vocab
sudo systemctl start nju-vocab

# 6. 配置 nginx 反向代理
echo "[5/5] 配置 Nginx..."
SERVER_IP=$(hostname -I | awk '{print $1}')

sudo tee /etc/nginx/sites-available/nju-vocab > /dev/null <<EOF
server {
    listen 80;
    server_name $SERVER_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/nju-vocab /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl restart nginx

echo ""
echo "=== 部署完成 ==="
echo "访问地址: http://$SERVER_IP"
echo ""
echo "常用命令:"
echo "  查看状态: sudo systemctl status nju-vocab"
echo "  查看日志: sudo journalctl -u nju-vocab -f"
echo "  重启服务: sudo systemctl restart nju-vocab"
