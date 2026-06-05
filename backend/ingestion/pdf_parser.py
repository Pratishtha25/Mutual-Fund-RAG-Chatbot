import os
import logging
from pypdf import PdfReader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def parse_pdf(file_path):
    """
    Extracts text from a PDF file using pypdf.
    """
    logger.info(f"Parsing PDF: {file_path}")
    text = ""
    try:
        reader = PdfReader(file_path)
        for i, page in enumerate(reader.pages):
            page_text = page.extract_text()
            if page_text:
                text += f"\n--- Page {i+1} ---\n" + page_text
        return text
    except Exception as e:
        logger.error(f"Error parsing PDF {file_path}: {e}")
        return ""

def parse_txt(file_path):
    """
    Reads text content from a plain text or markdown file.
    """
    logger.info(f"Parsing Text/Markdown: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {e}")
        return ""

def parse_documents_in_directory(directory_path):
    """
    Scans the directory for PDF and text files, parses them,
    and returns a list of document details.
    """
    if not os.path.exists(directory_path):
        logger.warning(f"Directory {directory_path} does not exist. Creating it.")
        os.makedirs(directory_path, exist_ok=True)
        return []
        
    parsed_docs = []
    for file_name in os.listdir(directory_path):
        file_path = os.path.join(directory_path, file_name)
        if not os.path.isfile(file_path):
            continue
            
        ext = os.path.splitext(file_name)[1].lower()
        text_content = ""
        
        if ext == ".pdf":
            text_content = parse_pdf(file_path)
        elif ext in [".txt", ".md", ".json"]:
            text_content = parse_txt(file_path)
        else:
            logger.info(f"Skipping unsupported file format: {file_name}")
            continue
            
        if text_content.strip():
            # Derive a title from the file name
            title = os.path.splitext(file_name)[0].replace("_", " ").title()
            parsed_docs.append({
                "file_name": file_name,
                "text": text_content,
                "title": title
            })
            logger.info(f"Successfully processed {file_name}")
            
    return parsed_docs

if __name__ == "__main__":
    import sys
    test_dir = "./backend/data/raw_documents"
    if len(sys.argv) > 1:
        test_dir = sys.argv[1]
    docs = parse_documents_in_directory(test_dir)
    print(f"Parsed {len(docs)} documents.")
