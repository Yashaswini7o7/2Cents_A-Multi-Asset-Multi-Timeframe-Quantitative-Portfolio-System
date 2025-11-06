FROM python:3.10-slim
WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y build-essential git

# copy and install
COPY pyproject.toml poetry.lock* /app/
RUN pip install --upgrade pip
RUN pip install poetry && poetry config virtualenvs.create false || true
RUN poetry install --no-root

COPY . /app
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "src.__main__"]
