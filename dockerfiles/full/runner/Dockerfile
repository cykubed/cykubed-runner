ARG region=us
ARG tag=3.0.0
FROM ${region}-docker.pkg.dev/cykubed/public/runner/app-base:${tag} as app

ARG base=cypress-node-20:1.0.0
ARG region=us
FROM ${region}-docker.pkg.dev/cykubed/public/runner/${base}

USER cykubed

WORKDIR /usr/app
COPY --chown=cykubed:cykubed --from=app /usr/app .
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
