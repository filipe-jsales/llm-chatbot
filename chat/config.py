import os
from os import environ

website_url = environ.get("WEBSITE_URL", "https://agetechcollaborative.org/")
base_storage_path = environ.get("BASE_STORAGE_PATH", "storage")
data_path = environ.get("DATA_PATH", f"{base_storage_path}/data")
database_path = environ.get("DATABASE_PATH", f"{base_storage_path}/database")
vector_database_path = environ.get(
    "VECTOR_DATABASE_PATH", f"{base_storage_path}/vector-database/"
)
chunk_size = int(environ.get("CHUNK_SIZE", "1000"))
chunk_overlap = int(environ.get("CHUNK_OVERLAP", "100"))
embedding_model_name = environ.get("EMBEDDING_MODEL_NAME", "nomic-embed-text")
model_name = environ.get("MODEL_NAME", "mistral")
ollama_server = environ.get("OLLAMA_SERVER", "http://10.50.0.11:11434")
model_temperature = float(environ.get("MODEL_TEMPERATURE", "0"))
collection_name = environ.get("COLLECTION_NAME", "vector_db")
number_of_retrieved_sources = int(environ.get("NUMBER_OF_RETRIEVED_SOURCES", "2"))
url_ignire_list = environ.get(
    "URL_IGNORE_LIST", "login, signin, sign-up, register, auth"
)
page_load_timeout = int(environ.get("PAGE_LOAD_TIMEOUT", "45"))
extra_urls = environ.get("EXTRA_URLS", "")
base_prompt_file = base_storage_path + "/base_prompt.txt"
if os.path.exists(base_prompt_file):
    with open(base_prompt_file, "r") as file:
        base_prompt = file.read()
else:
    base_prompt = ""

custom_prompt_file = base_storage_path + "/custom_prompt.txt"
if os.path.exists(custom_prompt_file):
    with open(custom_prompt_file, "r") as file:
        custom_prompt = file.read()
else:
    custom_prompt = ""
