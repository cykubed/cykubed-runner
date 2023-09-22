FROM us-docker.pkg.dev/cykubed/public/base-node-14-chrome:2.0.2

USER cykubed

WORKDIR /usr/app
COPY --chown=cykubed:cykubed --from=us-docker.pkg.dev/cykubed/public/base-runner:3.18.1 /usr/app .
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
