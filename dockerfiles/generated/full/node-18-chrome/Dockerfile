FROM us-docker.pkg.dev/cykubed/public/base-node-18-chrome:2.0.3

USER cykubed

WORKDIR /usr/app
COPY --chown=cykubed:cykubed --from=us-docker.pkg.dev/cykubed/public/base-runner:3.20.40 /usr/app .
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
