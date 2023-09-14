FROM ${region}-docker.pkg.dev/cykubed/public/${base_image}

USER cykubed

COPY pyproject.toml poetry.lock ./
RUN poetry config installer.max-workers 10
RUN poetry install --no-root --without=dev --no-interaction

COPY src/cykubedrunner cykubedrunner
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]