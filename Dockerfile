FROM python:3.12-slim AS builder
WORKDIR /wheels
COPY requirements.txt .
RUN pip wheel --no-cache-dir --disable-pip-version-check -r requirements.txt -w /wheels

FROM python:3.12-slim AS runtime
WORKDIR /app
RUN --mount=type=bind,from=builder,source=/wheels,target=/wheels pip install --no-cache-dir --disable-pip-version-check /wheels/*.whl
COPY main.py db.py ./
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
