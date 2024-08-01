## Local Development

```bash
source $(poetry env info --path)/bin/activate
poetry install
export WEBSITE_URL="https://webera.com/"
export STORAGE="storage"
export DATABASE_PATH="${STORAGE}/database"
export VECTOR_DATABASE_PATH="${STORAGE}/vector-database"
export DATA_PATH="${STORAGE}/data"
[ -d ${DATABASE_PATH} ] || mkdir -p ${DATABASE_PATH}
[ -d ${VECTOR_DATABASE_PATH} ] || mkdir -p ${VECTOR_DATABASE_PATH}
[ -d ${DATA_PATH} ] || mkdir -p ${DATA_PATH}
[ -n "$(ls -A $DATA_PATH)" ] || python chat/scripts/scrape.py
[ -n "$(ls -A $VECTOR_DATABASE_PATH)" ] || python chat/scripts/embed.py
[ -n "$(ls -A $DATABASE_PATH)" ] || python chat/scripts/create_sql_database.py
chainlit run chat/app.py
```
