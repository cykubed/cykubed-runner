FROM ${region}-docker.pkg.dev/cykubed/public/${base_image}

USER cykubed

WORKDIR /usr/app
COPY --chown=cykubed:cykubed --from=${region}-docker.pkg.dev/cykubed/public/base-runner:${tag} /usr/app .
ENV PYTHONPATH=/usr/app:.
ENTRYPOINT ["poetry", "run", "python", "cykubedrunner/main.py"]
