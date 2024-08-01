FROM webera/python 

ENV ACCESS_LOG=${ACCESS_LOG:-/proc/1/fd/1}
ENV ERROR_LOG=${ERROR_LOG:-/proc/1/fd/2}


WORKDIR /app

RUN poetry config virtualenvs.in-project true
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="${VIRTUAL_ENV}/bin:${PATH}"

COPY pyproject.toml ./
RUN poetry install --no-dev

COPY public ./public

COPY chat ./chat
RUN pip install .
COPY prompts/base_prompt.txt ./storage/base_prompt.txt
COPY run.sh ./

#Install Chrome
RUN apt-get update && apt-get install -y wget unzip ffmpeg
RUN wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb && \
    apt-get install -y ./google-chrome-stable_current_amd64.deb && \
    rm google-chrome-stable_current_amd64.deb && \
    apt-get clean

ENTRYPOINT [ "bash", "run.sh" ]
