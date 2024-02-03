ARG region=europe
ARG tag=3.0.0
ARG base=cypress-node-base-20:1.0.0
FROM ${region}-docker.pkg.dev/cykubed/public/runner/${base}

USER cykubed
RUN python -m venv .venv
ENV VIRTUAL_ENV=/usr/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"
ENV PYTHONPATH=/usr/app:.

COPY src/cykubedrunner cykubedrunner
COPY ["pyproject.toml", "poetry.lock", "./"]

RUN poetry install --no-root --only main --no-interaction

ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
