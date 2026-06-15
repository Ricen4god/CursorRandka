FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN test -d seed_data \
    && test -f seed_data/genders.json \
    && test -f seed_data/photos.json \
    || (echo "ERROR: Commit seed_data/genders.json and seed_data/photos.json to GitHub (folder seed_data/, not repo root)." >&2; exit 1)

CMD ["python", "main.py"]
