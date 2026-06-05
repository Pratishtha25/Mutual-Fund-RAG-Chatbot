import os
import json
import logging
import re
from stock_scraper import get_all_stocks_data
from pdf_parser import parse_documents_in_directory

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def chunk_text(text, chunk_size=600, overlap=100):
    """
    Splits text into chunks of chunk_size characters with overlap.
    Ensures chunks do not start/end mid-word if possible.
    """
    chunks = []
    text = re.sub(r'\s+', ' ', text).strip()  # Normalize whitespace
    
    start = 0
    while start < len(text):
        end = start + chunk_size
        
        # Adjust end to land on a space if possible
        if end < len(text):
            space_pos = text.rfind(' ', start, end)
            if space_pos > start + chunk_size // 2:
                end = space_pos
                
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
            
        start = end - overlap
        if start >= len(text) - overlap:
            break
            
    return chunks

def classify_mf_chunk(chunk_content):
    """
    Classifies a mutual fund chunk into one of the 9 specific query types.
    """
    content_lower = chunk_content.lower()
    
    if "expense ratio" in content_lower or "operating expenses" in content_lower or "recurring expenses" in content_lower:
        return "expense_ratio"
    elif "exit load" in content_lower or "redemption load" in content_lower or "load structure" in content_lower:
        return "exit_load"
    elif "minimum investment" in content_lower or "minimum sip" in content_lower or "minimum application" in content_lower or "lump sum" in content_lower:
        return "minimum_investment"
    elif "lock-in" in content_lower or "lockin" in content_lower or "maturity period" in content_lower:
        return "lock_in"
    elif "riskometer" in content_lower or "risk level" in content_lower or "risk classification" in content_lower:
        return "risk_classification"
    elif "benchmark" in content_lower or "index" in content_lower:
        return "benchmark"
    elif "assets under management" in content_lower or "aum" in content_lower or "fund size" in content_lower or "asset management company" in content_lower or "amc" in content_lower:
        return "fund_management"
    elif "fund manager" in content_lower or "portfolio manager" in content_lower or "managed by" in content_lower or "tenure" in content_lower:
        return "fund_manager_details"
    elif "download" in content_lower or "statement" in content_lower or "sid" in content_lower or "kim" in content_lower or "access" in content_lower:
        return "document_access"
    
    return "general"

def compile_corpus(raw_docs_dir, output_corpus_path):
    """
    Aggregates stock and mutual fund data, chunks them, and builds corpus.json
    """
    corpus = []
    
    # 1. Process Stock Data
    logger.info("Starting ingestion of stock data...")
    try:
        stocks_data = get_all_stocks_data()
        for key, stock in stocks_data.items():
            stock_name = stock["name"]
            url = stock["url"]
            
            # Helper to add stock chunks
            def add_stock_chunk(chunk_id_suffix, query_type, content):
                corpus.append({
                    "chunk_id": f"stock_{key}_{chunk_id_suffix}",
                    "type": "stock",
                    "query_type": query_type,
                    "stock_name": stock_name,
                    "content": content,
                    "source_metadata": {
                        "title": f"{stock_name} Stock Details",
                        "url": url
                    }
                })
            
            # A. General metrics chunk
            metrics_content = (
                f"{stock_name} exhibits a Market Capitalization of approximately {stock['market_cap']} "
                f"with a P/E Ratio of {stock['pe_ratio']} and a Dividend Yield of {stock['dividend_yield']}."
            )
            add_stock_chunk("metrics", "market_cap", metrics_content)
            
            # B. 52-Week high/low
            high_low_content = f"The 52-Week High / Low range for {stock_name} is {stock['fifty_two_week_high_low']}."
            add_stock_chunk("fifty_two_week", "fifty_two_week_high_low", high_low_content)
            
            # C. Industry classification
            industry_content = f"{stock_name} is categorized under the '{stock['industry']}' industry sector."
            add_stock_chunk("industry", "industry_classification", industry_content)
            
            # D. Company overview
            overview_content = f"About {stock_name} (Company Overview): {stock['overview']}"
            add_stock_chunk("overview", "company_overview", overview_content)
            
            # E. Management team
            mgmt_list = [f"{m['name']} ({m['designation']})" for m in stock["management"]]
            mgmt_str = ", ".join(mgmt_list)
            mgmt_content = f"The corporate management and executive leadership team of {stock_name} includes: {mgmt_str}."
            add_stock_chunk("management", "company_management_data", mgmt_content)
            
        logger.info(f"Ingested 5 stock profiles, generated {len(stocks_data)*5} chunks.")
    except Exception as e:
        logger.error(f"Error compiling stock data: {e}")
        
    # 2. Process Mutual Fund Documents
    logger.info(f"Starting ingestion of mutual fund documents from: {raw_docs_dir}")
    try:
        documents = parse_documents_in_directory(raw_docs_dir)
        for doc in documents:
            title = doc["title"]
            file_name = doc["file_name"]
            text = doc["text"]
            
            # Deduce mutual fund scheme name from title
            scheme_name = title.replace("Factsheet", "").replace("SID", "").replace("KIM", "").replace("Sid", "").strip()
            if not scheme_name.endswith("Fund"):
                scheme_name += " Fund"
                
            text_chunks = chunk_text(text)
            for idx, chunk_text_content in enumerate(text_chunks):
                query_type = classify_mf_chunk(chunk_text_content)
                corpus.append({
                    "chunk_id": f"mf_{file_name.replace('.', '_')}_{idx}",
                    "type": "mutual_fund",
                    "query_type": query_type,
                    "scheme_name": scheme_name,
                    "content": f"{scheme_name} - {chunk_text_content}",
                    "source_metadata": {
                        "title": title,
                        "source_name": "Groww Verified AMC Document"
                    }
                })
            logger.info(f"Processed {file_name}: Generated {len(text_chunks)} chunks.")
    except Exception as e:
        logger.error(f"Error compiling mutual fund documents: {e}")
        
    # 3. Write compiled corpus.json atomically using a temp file
    output_dir = os.path.dirname(output_corpus_path)
    os.makedirs(output_dir, exist_ok=True)
    
    tmp_corpus_path = output_corpus_path + ".tmp"
    try:
        with open(tmp_corpus_path, "w", encoding="utf-8") as f:
            json.dump(corpus, f, indent=2, ensure_ascii=False)
        # Atomic replacement
        os.replace(tmp_corpus_path, output_corpus_path)
        logger.info(f"Successfully compiled unified corpus.json with {len(corpus)} total chunks at {output_corpus_path}")
    except Exception as e:
        logger.error(f"Failed to write corpus.json atomically: {e}")
        if os.path.exists(tmp_corpus_path):
            try:
                os.remove(tmp_corpus_path)
            except Exception:
                pass

if __name__ == "__main__":
    import sys
    raw_dir = "./backend/data/raw_documents"
    out_file = "./backend/data/corpus.json"
    if len(sys.argv) > 2:
        raw_dir = sys.argv[1]
        out_file = sys.argv[2]
    compile_corpus(raw_dir, out_file)
