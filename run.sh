#!/usr/bin/env bash

source .venv/bin/activate

export STORAGE="storage"
export DATABASE_PATH="${STORAGE}/database"
export VECTOR_DATABASE_PATH="${STORAGE}/vector-database"
export DATA_PATH="${STORAGE}/data"

[ -d ${DATABASE_PATH} ] || mkdir -p ${DATABASE_PATH}
[ -d ${VECTOR_DATABASE_PATH} ] || mkdir -p ${VECTOR_DATABASE_PATH}
[ -d ${DATA_PATH} ] || mkdir -p ${DATA_PATH}

[ -n "$(ls -A $DATA_PATH)" ] || python chat/bootstrap.py
[ -n "$(ls -A $VECTOR_DATABASE_PATH)" ] || python chat/embed.py

chainlit run chat/app.py -h 
