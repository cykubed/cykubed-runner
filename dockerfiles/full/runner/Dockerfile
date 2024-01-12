ARG region=us
ARG base=cypress-node-20:1.0.0
FROM ${region}-docker.pkg.dev/cykubed/public/runner/${base}

ARG region=us
ARG tag=3.0.0

USER cykubed

WORKDIR /usr/app
COPY --chown=cykubed:cykubed --from=${region}-docker.pkg.dev/cykubed/public/runner/app-base:${tag} /usr/app .
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
