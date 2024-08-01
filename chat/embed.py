import logging
import os

import config
from langchain.docstore.document import Document
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from logs import configure_logging
from chromadb.config import Settings


def load_documents_from_folder(folder_path):
    logging.info(f"Loading documents from folder: {folder_path}")
    files = os.listdir(folder_path)
    documents = []
    for file_name in files:
        file_path = os.path.join(folder_path, file_name)
        try:
            with open(file_path, "r") as file:
                document_content = file.read()
            documents.append(Document(page_content=document_content))
            logging.info(f"Loaded document: {file_name}")
        except Exception as e:
            logging.error(f"Error loading document {file_name}: {e}")

    return documents


def main():
    configure_logging()
    try:
        logging.info("Starting document loading process.")
        documents = load_documents_from_folder(config.data_path)
        logging.info(f"Loaded {len(documents)} documents.")

        logging.info("Creating vector database.")

        embedding = OllamaEmbeddings(
            base_url=config.ollama_server, model=config.embedding_model_name
        )
        logging.info("Embedding model loaded successfully.")
        client_settings= Settings( anonymized_telemetry=False, is_persistent=True )
        Chroma.from_documents(
            documents=documents,
            embedding=embedding,
            persist_directory=config.vector_database_path,
            collection_name=config.collection_name,
            client_settings=client_settings
        )
        logging.info("Vector database created successfully.")
    except Exception as e:
        logging.error(f"Error creating vector database: {e}")


if __name__ == "__main__":
    main()
