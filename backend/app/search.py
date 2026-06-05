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


def get_embedding(text: str, model: str = EMBED_MODEL) -> list:
    """
    Calls the local Ollama API to generate a vector embedding for the input text.
    Supports both /api/embeddings and /api/embed endpoints.
    """
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=10.0
        )
        if response.status_code == 200:
            return response.json()["embedding"]
    except Exception as e:
        logger.warning(f"Ollama /api/embeddings endpoint failed or timed out: {e}. Trying /api/embed...")
        
    try:
        response = requests.post(
            f"{OLLAMA_URL}/api/embed",
            json={"model": model, "input": text},
            timeout=10.0
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

    def search(self, query: str, top_k: int = 3) -> tuple[list[dict], bool]:
        """
        Retrieves the top_k matching chunks for the query.
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

        if not self.corpus or self.normalized_matrix is None or len(self.normalized_matrix) == 0:
            return [], True

        # 2. Get embedding for the query
        try:
            query_vector = np.array(get_embedding(query))
        except Exception as e:
            logger.error(f"Error during query vectorization: {e}")
            return [], True

        query_norm = np.linalg.norm(query_vector)
        if query_norm > 0:
            query_vector = query_vector / query_norm
        else:
            return [], True

        # 3. Calculate cosine similarity (dot product of normalized vectors)
        similarities = np.dot(self.normalized_matrix, query_vector)

        # 4. Sort similarities in descending order
        top_indices = np.argsort(similarities)[::-1]

        # 5. Check if the absolute top match is below threshold
        if len(similarities) == 0 or similarities[top_indices[0]] < self.threshold:
            logger.info(f"Top similarity score {similarities[top_indices[0]] if len(similarities) > 0 else 0} is below threshold {self.threshold}. Deflecting.")
            return [], True

        # 6. Entity alignment verification
        entity_keywords = {
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

        matched_entities_in_query = []
        for entity_name, keywords in entity_keywords.items():
            for kw in keywords:
                pattern = rf"\b{kw}\b" if len(kw) <= 6 else kw
                if re.search(pattern, query_lower):
                    matched_entities_in_query.append(entity_name)
                    break

        aligned_chunks = []
        for idx in top_indices:
            score = similarities[idx]
            if score < self.threshold:
                continue

            chunk = self.corpus[idx]
            retrieved_entity = chunk.get("scheme_name") or chunk.get("stock_name")

            # Entity boundary check: If query mentions one or more supported entities,
            # the chunk's entity must match one of them.
            if matched_entities_in_query and retrieved_entity not in matched_entities_in_query:
                logger.info(f"Entity mismatch: query mentions {matched_entities_in_query} but chunk is for '{retrieved_entity}'. Skipping chunk.")
                continue

            chunk_copy = chunk.copy()
            chunk_copy["similarity_score"] = float(score)
            aligned_chunks.append(chunk_copy)

            if len(aligned_chunks) >= top_k:
                break

        if not aligned_chunks:
            logger.info("All retrieved chunks filtered out due to entity alignment mismatch. Deflecting.")
            return [], True

        return aligned_chunks, False
