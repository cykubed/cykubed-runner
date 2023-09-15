FROM us-docker.pkg.dev/cykubed/public/base-node-14-edge:2.0.1

USER cykubed

COPY pyproject.toml poetry.lock ./
RUN poetry config installer.max-workers 10
RUN poetry install --no-root --without=dev --no-interaction

COPY src/cykubedrunner cykubedrunner
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
