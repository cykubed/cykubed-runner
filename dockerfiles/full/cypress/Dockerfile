ARG region=us
ARG base=cypress-node-16:1.0.0
FROM ${region}-docker.pkg.dev/cykubed/public/${base}
ARG region=us
ARG runner_tag=1.0.0

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
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
