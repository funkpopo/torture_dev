FROM python:3.10-slim

WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露API服务端口
EXPOSE 8000

# 设置环境变量
ENV API_HOST=0.0.0.0
ENV API_PORT=8000

# 使用非root用户运行
RUN useradd -m appuser
USER appuser

# 启动命令
CMD ["python", "api.py"] 