FROM python:3.11-slim

# Рабочая директория в контейнере
WORKDIR /app

# Чтобы Python не писал .pyc и сразу выводил логи
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Установим системные зависимости (если нужны asyncpg/psycopg2)
RUN apt-get update \
    && apt-get install -y gcc libpq-dev build-essential \
    && rm -rf /var/lib/apt/lists/*

# Скопируем только requirements.txt для кеша
COPY requirements.txt /app/
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Копируем весь проект
COPY . /app

# Стандартная команда (можно переопределять в docker-compose.yml)
CMD ["python", "bot.py"]

