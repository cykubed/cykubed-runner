ARG tag=3.0.0
ARG base=ghcr.io/cykubed/runner-cypress-20:5.0.0
FROM ${base}

USER cykubed
RUN python -m venv .venv
ENV VIRTUAL_ENV=/usr/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/usr/app:.

COPY src/cykubedrunner cykubedrunner
COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install --no-root --only main --no-interaction

ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
