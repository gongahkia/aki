FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

WORKDIR /app

COPY requirements.txt ./

RUN pip install --no-cache-dir pre-commit && \
    pip install --no-cache-dir -r requirements.txt && \
    pre-commit install && \
    pre-commit autoupdate

COPY . .

RUN pre-commit run --all-files

CMD ["python3", "src/main.py"]
