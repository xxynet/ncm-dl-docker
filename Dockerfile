FROM python:3.9-alpine

WORKDIR /app

EXPOSE 5266

RUN mkdir -p /app/playlist /app/ncm /app/scrape

COPY requirements.txt .

RUN pip install --no-cache-dir \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --trusted-host pypi.tuna.tsinghua.edu.cn \
    --timeout=60 \
    --retries=3 \
    -r requirements.txt

COPY . .

CMD ["python", "app.py"]