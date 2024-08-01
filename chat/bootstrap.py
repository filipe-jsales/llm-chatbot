import logging
import os
import sqlite3
from time import sleep
from urllib.parse import urljoin, urlparse

import config
import requests
import tldextract
from bs4 import BeautifulSoup
from langchain.chains.summarize import load_summarize_chain
from langchain.prompts import PromptTemplate
from langchain_community.llms import Ollama
from langchain_core.documents import Document
from logs import configure_logging
from PyPDF2 import PdfReader
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


class WebScraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.urls = set()
        self.pdf_urls = set()
        self.visited = set()
        self.session = requests.Session()
        self.domain = self.extract_domain(base_url)
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
            }
        )
        self.pdf_reader = os.getenv("PDF_READER", "false")
        self.ignore_keywords = config.url_ignire_list.split(", ")
        self.service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(
            service=self.service, options=self.set_chrome_options()
        )
        logging.info(f"Initialized WebScraper for domain: {self.domain}")

    def extract_domain(self, url):
        extracted = tldextract.extract(url)
        domain = "{}.{}".format(extracted.domain, extracted.suffix)
        logging.info(f"Extracted domain: {domain}")
        return domain

    def sort_urls(self):
        """Sorts the URLs by their path hierarchy, ensuring the main domain is first."""
        sorted_urls = sorted(
            self.urls, key=lambda url: (len(urlparse(url).path.split("/")), url)
        )
        main_url = self.base_url if self.base_url.endswith("/") else self.base_url + "/"
        if main_url in sorted_urls:
            sorted_urls.remove(main_url)
        sorted_urls.insert(0, main_url)
        self.urls = sorted_urls
        logging.info(f"Sorted URLs: {self.urls}")

    def crawl_urls(self):
        queue = [self.base_url]
        while queue:
            current_url = queue.pop(0)
            if current_url in self.visited:
                continue
            self.visited.add(current_url)
            logging.info(f"Visiting URL: {current_url}")

            response = self.fetch_url(current_url)
            if response:
                soup = BeautifulSoup(response, "lxml")
                for link in soup.find_all("a", href=True):
                    self.process_link(link["href"], current_url, queue)

                # while True:
                #     try:
                #         next_button = self.driver.find_element(
                #             By.XPATH, '//*[@id="pagination-next"]'
                #         )
                #         if next_button.is_enabled():
                #             next_button.click()
                #             sleep(config.page_load_timeout)
                #             next_page_content = self.driver.page_source
                #             logging.info("Clicked next pagination button")
                #             next_soup = BeautifulSoup(next_page_content, "lxml")
                #             for link in next_soup.find_all("a", href=True):
                #                 self.process_link(
                #                     link["href"], self.driver.current_url, queue
                #                 )
                #         else:
                #             logging.info(
                #                 "Pagination button is disabled, stopping pagination."
                #             )
                #             break
                #     except NoSuchElementException:
                #         logging.info(
                #             "Pagination button not found, stopping pagination."
                #         )
                #         break
                #     except Exception as e:
                #         logging.error(
                #             f"Error clicking pagination button: {e}", exc_info=True
                #         )
                #         break

    def set_chrome_options(self) -> Options:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        logging.info("Set Chrome options for headless browsing")
        return chrome_options

    def fetch_url(self, url):
        try:
            self.driver.get(url)
            sleep(config.page_load_timeout)
            html_content = self.driver.page_source
            logging.info(f"Fetched URL: {url}")
            return html_content
        except Exception as e:
            logging.error(f"Error fetching URL {url}: {e}")
            return None

    def process_link(self, href, current_url, queue):
        full_url = urljoin(current_url, href)
        if self.is_valid_url(full_url):
            if href.lower().endswith(".pdf") and self.pdf_reader != "false":
                self.pdf_urls.add(full_url)
                logging.info(f"Found PDF URL: {full_url}")
            elif self.extract_domain(full_url) == self.domain:
                logging.info(f"Found URL: {full_url}")
                queue.append(full_url)
                self.urls.add(full_url)

    def is_valid_url(self, url):
        parsed_url = urlparse(url)
        if any(kw in parsed_url.path.lower() for kw in self.ignore_keywords):
            return False
        if any(kw in url.lower() for kw in ["#", "javascript:", "mailto:", "tel:"]):
            return False
        if ":" in url.split("/")[2]:  # check for a port in the host part
            return False
        return True

    def download_pdf(self, url):
        try:
            response = self.session.get(url)
            response.raise_for_status()
            file_name = os.path.basename(url)
            file_path = os.path.join(config.base_storage_path, "pdf", file_name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, "wb") as f:
                f.write(response.content)
            logging.info(f"Downloaded PDF: {file_name}")
            return file_path
        except requests.RequestException as e:
            logging.error(f"Error downloading PDF from {url}: {e}")
            return None

    def summarizer(self, text, type):
        document = Document(page_content=text)

        llm = Ollama(
            base_url=config.ollama_server,
            model=config.model_name,
            temperature=0.8,
            num_ctx=8192,
        )
        prompt_template = """Write a concise contextualized text in first-person plural of the following:
        {text}
        CONCISE CONTEXTUALIZED TEXT:"""
        prompt = PromptTemplate.from_template(prompt_template)
        refine_template = """
         "Your job is to produce a final contextualized text in first-person plural\n"
    "We have provided an existing contextualized text up to a certain point: {existing_answer}\n"
    "We have the opportunity to refine the existing contextualized text"
    "(only if needed) with some more context below.\n"
    "------------\n"
    "{text}\n"
    "------------\n"
    "Given the new context, refine the original contextualized text"
    "If the context isn't useful, return the original contextualized text.
    REFINED CONTEXTUALIZED TEXT:"
        """
        refine_prompt = PromptTemplate(
            template=refine_template, input_variables=["text", "existing_answer"]
        )
        if type == "refine":
            chain = load_summarize_chain(
                llm,
                chain_type=type,
                refine_prompt=refine_prompt,
                question_prompt=prompt,
            )
        else:
            chain = load_summarize_chain(llm, chain_type=type)

        summary = chain.invoke(dict(input_documents=[document]))
        logging.info(f"Summarized text with type '{type}'")
        return summary["output_text"]

    def create_txt(self):
        self.urls.update(config.extra_urls.split(", "))
        logging.info("Creating text files from scraped content...")
        content_header = ""
        content_footer = ""
        for idx, url in enumerate(self.urls):
            response = self.fetch_url(url)
            if response:
                soup = BeautifulSoup(response, "lxml")
                main_content = soup.find("main")
                if idx == 0:
                    header = soup.find("header")
                    if header:
                        content_header = header.get_text("\n")
                        self.write_to_file(
                            content_header,
                            os.path.join(config.data_path, f"header.txt"),
                        )
                    footer = soup.find("footer")
                    if footer:
                        content_footer = footer.get_text("\n")
                        self.write_to_file(
                            content_footer,
                            os.path.join(config.data_path, f"footer.txt"),
                        )
                if main_content:
                    text = main_content.get_text("\n")
                else:
                    body_content = soup.find("body")
                    header = body_content.find("header")
                    if header:
                        header.extract()

                    footer = body_content.find("footer")
                    if footer:
                        footer.extract()
                    text = body_content.get_text("\n")

                content = f"{text}"
                sliced_content = content.split(" ")
                if len(sliced_content) > 8000:
                    sliced_content_one = " ".join(sliced_content[:8000])
                    sliced_content_two = " ".join(sliced_content[8000:])
                    self.write_to_file(
                        sliced_content_one,
                        os.path.join(config.data_path, f"data_{idx}_1.txt"),
                    )
                    self.write_to_file(
                        sliced_content_two,
                        os.path.join(config.data_path, f"data_{idx}_2.txt"),
                    )
                else:
                    self.write_to_file(
                        content.replace("\n\n", ""),
                        os.path.join(config.data_path, f"data_{idx}.txt"),
                    )

                summarized_text = self.summarizer(
                    text, "refine" if len(text) < 50000 else "map_reduce"
                )
                content_summarized = f"{summarized_text}"
                self.write_to_file(
                    content_summarized,
                    os.path.join(config.data_path, f"data_summarized_{idx}.txt"),
                )
                logging.info(f"Processed and summarized content from URL: {url}")

        for pdf_url in self.pdf_urls:
            pdf_path = self.download_pdf(pdf_url)
            if pdf_path:
                self.process_pdf(pdf_path, "")
                logging.info(f"Processed PDF content from URL: {pdf_url}")

    def process_pdf(self, pdf_path, content):
        try:
            reader = PdfReader(pdf_path)
            for page in reader.pages:
                content += f"{self.summarizer(page.extract_text(), 'map_reduce')}\n\n"
            logging.info(f"Processed PDF file: {pdf_path}")
            self.write_to_file(
                content,
                os.path.join(config.data_path, f"pdf_{os.path.basename(pdf_path)}.txt"),
            )
        except Exception as e:
            logging.error(f"Error reading PDF {pdf_path}: {e}")

    def write_to_file(self, content, file_path):
        try:
            with open(file_path, "w") as f:
                f.write(content.replace("..", ""))
            logging.info(f"Wrote content to file: {file_path}")
        except IOError as e:
            logging.error(f"Error writing content to file {file_path}: {e}")

    def run(self):
        logging.info("Starting web scraping process...")
        self.crawl_urls()
        self.sort_urls()
        self.create_txt()
        logging.info("Data collection complete.")


def create_database():
    database_path = os.path.join(config.database_path, "database.db")

    if not os.path.exists(database_path):
        con = sqlite3.connect(database_path)
        cur = con.cursor()

        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                message_content TEXT NOT NULL,
                role TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        con.commit()
        con.close()
        print("Database created successfully")
    else:
        print("Database already exists")


def main():
    configure_logging(to_file=True, file_name="bootstrap.log")
    create_database()
    ws = WebScraper(config.website_url)
    ws.run()


if __name__ == "__main__":
    main()
