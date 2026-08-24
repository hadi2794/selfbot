FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# ffmpeg لازمِ .فشرده‌سازی/.تبدیل (صدا و ویدیو)، fonts-dejavu-core برای متنِ
# .واترمارک، و tesseract-ocr (+ بسته‌های زبانِ فارسی/انگلیسی) برای .استخراج‌متن
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg fonts-dejavu-core \
        tesseract-ocr tesseract-ocr-fas tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY . .

CMD ["sh", "-c", "python -m alembic upgrade head && exec python main.py"]
