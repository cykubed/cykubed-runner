FROM python:3.10-slim-bullseye

RUN useradd -m cykubed --uid 10000 && chown cykubed:cykubed /usr/app /node /build
USER cykubed

WORKDIR /usr/app

RUN python -m venv .venv
ENV VIRTUAL_ENV=/usr/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV TZ=UTC

RUN pip install poetry==1.3.1

COPY src/cykubedrunner cykubedrunner
COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install --no-root --only main --no-interaction

