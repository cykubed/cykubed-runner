FROM {base} as build

RUN apt-get update
RUN apt-get install -y pip python3-venv lz4

WORKDIR /usr/app

RUN useradd -m cykube && chown cykube /usr/app
USER cykube

RUN mkdir -p /tmp/cykube/build
ENV PATH="/home/cykube/.local/bin:$PATH"

RUN pip install poetry==1.3.1
COPY ../pyproject.toml poetry.lock ./
RUN poetry install --no-root
COPY ../src .

ENTRYPOINT ["poetry", "run", "python", "main.py"]

