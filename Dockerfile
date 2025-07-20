FROM python:3.9-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libx11-6 \
    libxcomposite1 \
    libxdamage1 \
    libxext6 \
    libxfixes3 \
    libxrandr2 \
    libxcb1 \
    libxkbcommon0 \
    libfontconfig1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

# 安装Playwright依赖
RUN playwright install-deps

# 安装Playwright浏览器
RUN playwright install chromium

# 复制项目文件
COPY . .

# 启动命令
CMD ["python", "spider.py"]