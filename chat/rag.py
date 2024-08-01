from operator import itemgetter

from chromadb.config import Settings
from langchain.prompts import ChatPromptTemplate
from langchain_community.embeddings import OllamaEmbeddings
from langchain_community.llms import Ollama
from langchain_community.vectorstores import Chroma
from langchain_core.output_parsers import StrOutputParser

from chat import config


class Rag:
    def __init__(self):

        self.client_settings = Settings(anonymized_telemetry=False, is_persistent=True)

        self.embedding_function = OllamaEmbeddings(
            base_url=config.ollama_server, model=config.embedding_model_name
        )

        self.vectorstore = Chroma(
            persist_directory=config.vector_database_path,
            embedding_function=self.embedding_function,
            collection_name=config.collection_name,
            client_settings=self.client_settings,
        )

        self.retriever = self.vectorstore.as_retriever(
            search_kwargs={"k": config.number_of_retrieved_sources}
        )

        self.model = Ollama(
            base_url=config.ollama_server,
            model=config.model_name,
            temperature=config.model_temperature,
            num_ctx=8192,
        )

        self.template = config.base_prompt + config.custom_prompt

        self.prompt_template = ChatPromptTemplate.from_template(self.template)

        self.chain = (
            {
                "context": itemgetter("question") | self.retriever | self.format_docs,
                "question": itemgetter("question"),
                "chat_history": itemgetter("chat_history"),
            }
            | self.prompt_template
            | self.model
            | StrOutputParser()
        )

    def format_docs(self, docs):
        final = ""
        for idx, doc in enumerate(docs):
            final += "Document " + str(idx + 1) + ": \n\n" + doc.page_content + "\n\n"
        # print(final)
        return final
