import os
import json
import hashlib
import logging
import re
import numpy as np
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = "nomic-embed-text"

ENTITY_KEYWORDS = {
    "Axis Bluechip Fund": ["axis bluechip", "bluechip"],
    "Axis Long Term Equity Fund": ["axis long term", "long term equity", "elss"],
    "Parag Parikh Flexi Cap Fund": ["parag parikh", "ppfas", "flexi cap", "flexicap"],
    "Groww Large Cap Fund": ["groww", "groww large cap", "groww large cap fund"],
    "General Mutual Fund": ["general", "faq", "statement", "capital gains", "download", "objectives", "category", "elss", "exit load", "sip", "benchmark", "riskometer"],
    "Max Financial Services Ltd": ["max financial", "max", "mfs"],
    "AU Small Finance Bank Ltd": ["au small", "au bank", "au small finance"],
    "The Federal Bank Ltd": ["federal", "federal bank"],
    "Glenmark Pharmaceuticals Ltd": ["glenmark", "glenmark pharma", "pharmaceuticals"],
    "Indian Bank": ["indian bank", "indian"]
}


def get_embedding(text: str, model: str = EMBED_MODEL) -> list:
    """
    Calls the local Ollama API to generate a vector embedding for the input text.
    Supports both /api/embeddings and /api/embed endpoints.
    """
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=0.5
        )
        if response.status_code == 200:
            return response.json()["embedding"]
    except Exception as e:
        logger.warning(f"Ollama /api/embeddings endpoint failed or timed out: {e}. Trying /api/embed...")
        
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": model, "input": text},
            timeout=0.5
        )
        if response.status_code == 200:
            return response.json()["embeddings"][0]
    except Exception as e:
        logger.error(f"Ollama /api/embed endpoint also failed: {e}")
        raise RuntimeError(f"Could not connect to Ollama embedding API. Ensure Ollama is running and has pulled '{model}'.") from e
        
    raise RuntimeError(f"Ollama embedding request failed with status code {response.status_code}: {response.text}")


def compute_md5(filepath: str) -> str:
    """
    Computes MD5 checksum of a file.
    """
    hasher = hashlib.md5()
    with open(filepath, "rb") as f:
        buf = f.read()
        hasher.update(buf)
    return hasher.hexdigest()


class SimilarityIndex:
    def __init__(
        self,
        corpus_path: str = "backend/data/corpus.json",
        cache_path: str = "backend/data/embeddings.npy",
        hash_path: str = "backend/data/corpus_hash.txt",
        threshold: float = 0.35
    ):
        self.corpus_path = corpus_path
        self.cache_path = cache_path
        self.hash_path = hash_path
        self.threshold = threshold
        
        self.corpus = []
        self.normalized_matrix = None  # NumPy matrix of normalized embeddings

    def load(self) -> None:
        """
        Loads corpus and cached embeddings. Re-vectorizes if cache is stale or missing.
        """
        if not os.path.exists(self.corpus_path):
            logger.warning(f"Corpus file not found at {self.corpus_path}. Creating an empty index.")
            self.corpus = []
            self.normalized_matrix = np.empty((0, 768))
            return

        with open(self.corpus_path, "r", encoding="utf-8") as f:
            self.corpus = json.load(f)

        if not self.corpus:
            logger.warning("Corpus is empty.")
            self.normalized_matrix = np.empty((0, 768))
            return

        current_hash = compute_md5(self.corpus_path)
        cache_valid = False

        if os.path.exists(self.cache_path) and os.path.exists(self.hash_path):
            try:
                with open(self.hash_path, "r", encoding="utf-8") as f:
                    cached_hash = f.read().strip()
                if cached_hash == current_hash:
                    embeddings = np.load(self.cache_path)
                    if len(embeddings) == len(self.corpus):
                        logger.info("Loading embeddings from disk cache...")
                        self.normalized_matrix = embeddings
                        cache_valid = True
                    else:
                        logger.warning("Cache size mismatch with corpus size. Re-vectorizing...")
                else:
                    logger.info("Corpus modified. Re-vectorizing...")
            except Exception as e:
                logger.error(f"Error reading vector cache: {e}. Re-vectorizing...")

        if not cache_valid:
            self.vectorize_corpus(current_hash)
            
        import gc
        gc.collect()

    def vectorize_corpus(self, current_hash: str) -> None:
        """
        Generates embeddings for all chunks in the corpus and writes them to the cache.
        """
        logger.info(f"Generating vector embeddings for {len(self.corpus)} chunks using '{EMBED_MODEL}'...")
        vectors = []
        for idx, chunk in enumerate(self.corpus):
            content = chunk["content"]
            try:
                vector = get_embedding(content)
                vectors.append(vector)
            except Exception as e:
                logger.error(f"Failed to vectorize chunk {idx}: {e}")
                # Use a zero vector as placeholder to maintain alignment, will log critical
                vectors.append([0.0] * 768)

        matrix = np.array(vectors)
        # Normalize vectors for fast cosine similarity calculations
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self.normalized_matrix = matrix / norms

        # Save to disk
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            np.save(self.cache_path, self.normalized_matrix)
            with open(self.hash_path, "w", encoding="utf-8") as f:
                f.write(current_hash)
            logger.info("Successfully cached vector embeddings and corpus hash.")
        except Exception as e:
            logger.error(f"Failed to write vector cache to disk: {e}")
            
        import gc
        gc.collect()

    def keyword_search(self, query: str, top_k: int = 3) -> list[dict]:
        """
        Pure Python fallback keyword search when vector search returns low similarity or fails.
        """
        query_lower = query.lower()
        
        # Tokenize query: remove punctuation and split into words
        query_words = set(re.findall(r"\w+", query_lower))
        stop_words = {
            "what", "is", "the", "of", "in", "for", "does", "have", "any", "how", "can", "i", 
            "download", "a", "an", "to", "on", "at", "about", "with", "by", "scheme", "fund"
        }
        query_keywords = query_words - stop_words
        if not query_keywords:
            query_keywords = query_words
            
        # Determine which entities are mentioned in the query
        matched_entities_in_query = []
        for entity_name, keywords in ENTITY_KEYWORDS.items():
            for kw in keywords:
                pattern = rf"\b{kw}\b" if len(kw) <= 6 else kw
                if re.search(pattern, query_lower):
                    matched_entities_in_query.append(entity_name)
                    break
            
        scored_chunks = []
        for chunk in self.corpus:
            content_lower = chunk["content"].lower()
            score = 0
            
            # 1. Overlap of query keywords with chunk content
            for kw in query_keywords:
                if kw in content_lower:
                    score += 1.0
                    
            # 2. Match with the entity in query (boost score)
            entity = chunk.get("scheme_name") or chunk.get("stock_name")
            if entity and entity in matched_entities_in_query:
                score += 5.0
                    
            # 3. Match query type (boost score)
            qtype = chunk.get("query_type")
            if qtype:
                qtype_keywords = qtype.replace("_", " ").split()
                if any(w in query_lower for w in qtype_keywords):
                    score += 3.0
                    
            if score > 0:
                scored_chunks.append((score, chunk))
                
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        results = []
        for score, chunk in scored_chunks:
            retrieved_entity = chunk.get("scheme_name") or chunk.get("stock_name")
            # Entity boundary filtering: if any entities are mentioned in the query,
            # only return chunks matching those entities.
            if matched_entities_in_query and retrieved_entity not in matched_entities_in_query:
                continue
                
            chunk_copy = chunk.copy()
            chunk_copy["similarity_score"] = float(score)
            results.append(chunk_copy)
            if len(results) >= top_k:
                break
                
        return results

    def search(self, query: str, top_k: int = 3) -> tuple[list[dict], bool]:
        """
        Retrieves the top_k matching chunks for the query using semantic search,
        falling back to keyword search if vector similarity is low or Ollama is offline.
        Returns a tuple: (list_of_chunks, is_deflected)
        """
        query_lower = query.lower()

        # 1. Deflect common out-of-corpus entities immediately
        out_of_corpus_keywords = [
            "sbi", "hdfc", "icici", "reliance", "tcs", "infosys", "apple", "google", "microsoft", 
            "nifty", "sensex", "tata", "wipro", "adani", "lic", "birla", "nippon", "quant", 
            "mirae", "kotak", "dsp", "uti", "franklin", "motilal", "axis midcap", "axis small cap",
            "axis growth", "parag parikh conservative", "parag parikh tax saver"
        ]
        for ooc in out_of_corpus_keywords:
            if re.search(rf"\b{ooc}\b", query_lower):
                logger.info(f"Out-of-corpus entity keyword '{ooc}' detected. Deflecting.")
                return [], True

        if not self.corpus:
            return [], True

        # 2. Try Vector Semantic Search
        vector_run_success = False
        vector_above_threshold = False
        aligned_chunks = []
        
        if self.normalized_matrix is not None and len(self.normalized_matrix) > 0:
            try:
                query_vector = np.array(get_embedding(query))
                query_norm = np.linalg.norm(query_vector)
                
                if query_norm > 0:
                    query_vector = query_vector / query_norm
                    similarities = np.dot(self.normalized_matrix, query_vector)
                    top_indices = np.argsort(similarities)[::-1]
                    
                    if len(similarities) > 0:
                        vector_run_success = True
                        max_score = similarities[top_indices[0]]
                        if max_score >= self.threshold:
                            vector_above_threshold = True
                            
                            # Entity alignment check
                            matched_entities_in_query = []
                            for entity_name, keywords in ENTITY_KEYWORDS.items():
                                for kw in keywords:
                                    pattern = rf"\b{kw}\b" if len(kw) <= 6 else kw
                                    if re.search(pattern, query_lower):
                                        matched_entities_in_query.append(entity_name)
                                        break
                                        
                            for idx in top_indices:
                                score = similarities[idx]
                                if score < self.threshold:
                                    continue
                                    
                                chunk = self.corpus[idx]
                                retrieved_entity = chunk.get("scheme_name") or chunk.get("stock_name")
                                
                                if matched_entities_in_query and retrieved_entity not in matched_entities_in_query:
                                    logger.info(f"Entity mismatch: query mentions {matched_entities_in_query} but chunk is for '{retrieved_entity}'. Skipping.")
                                    continue
                                    
                                chunk_copy = chunk.copy()
                                chunk_copy["similarity_score"] = float(score)
                                aligned_chunks.append(chunk_copy)
                                
                                if len(aligned_chunks) >= top_k:
                                    break
            except Exception as e:
                logger.warning(f"Vector search failed or timed out: {e}. Falling back to keyword search.")

        # 3. Fallback to Keyword Match Search if Vector Search failed / had low similarity
        # We only fallback if vector search was NOT run successfully (e.g. Ollama offline),
        # OR if vector search was run but the top match was below threshold.
        # If vector search ran and found matches above threshold, but they were filtered out by entity mismatch,
        # we deflect immediately to preserve entity boundary logic.
        if not vector_run_success or not vector_above_threshold:
            logger.info("Vector search was not successful (offline or low similarity). Triggering fallback keyword search...")
            aligned_chunks = self.keyword_search(query, top_k)
            
        if not aligned_chunks:
            logger.info("All search methods failed to find matches. Deflecting.")
            return [], True

        return aligned_chunks, False
