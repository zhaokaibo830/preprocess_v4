# 使用非 slim，确保兼容 Wine + LibreOffice + XeLaTeX
# rebuild context 20250601
FROM python:3.13

RUN sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources && \
    sed -i 's|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' \
        /etc/apt/sources.list.d/debian.sources

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        pandoc \
        libreoffice \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        wine \
        && dpkg --add-architecture i386 \
        && apt-get update \
        && apt-get install -y --no-install-recommends \
            wine32:i386 \
            libgl1:i386 \
        xvfb \
        xauth \
        winbind \
        cabextract \
        fonts-noto-cjk \
        texlive-xetex \
        texlive-latex-base \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-lang-chinese \
        texlive-latex-recommended \
        texlive-fonts-extra \
        lmodern \
        wget \
        curl \
        unzip \
        libxrender1 \
        libxext6 \
        libxinerama1 \
        libxtst6 \
        libfontconfig1 \
        # ===== 新增：OpenCV 运行依赖 =====
        libgl1 \
        libglib2.0-0 \
        libsm6 \
        libgomp1 \
        vim \
        && rm -rf /var/lib/apt/lists/*




# 复制 Python 依赖
COPY requirements.txt .

# 安装 Python 包
RUN pip install --no-cache-dir -r requirements.txt

RUN mineru-models-download --model_type all --source modelscope
# 复制所有源代码
COPY . .

# 指定入口
CMD ["python", "run.py"]
