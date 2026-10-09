FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=ecom.settings.main

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y libpq5 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.in requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["gunicorn", "ecom.wsgi:application", "-c", "ecom/gunicorn.py"]
