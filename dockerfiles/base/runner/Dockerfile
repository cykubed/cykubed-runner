FROM python:3.10-slim-bullseye

WORKDIR /usr/app

RUN python -m venv .venv
ENV VIRTUAL_ENV=/usr/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV TZ=UTC

RUN pip install poetry==1.3.1

COPY src/cykubedrunner cykubedrunner
COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install --no-root --only main --no-interaction
