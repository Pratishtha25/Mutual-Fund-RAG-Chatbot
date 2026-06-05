import os
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")


def build_prompt(query: str, chunks: list[dict]) -> tuple[str, str]:
    """
    Constructs the system instruction and user prompt for the local LLM.
    """
    system_instruction = (
        "You are a facts-only, regulatory-compliant financial assistant for Groww. "
        "Your objective is to answer the user's question using ONLY the retrieved context chunks below.\n\n"
        "STRICT INSTRUCTIONS:\n"
        "1. If the answer cannot be found in the context chunks, say: \"I do not have this information in my verified records.\"\n"
        "2. Never formulate answers based on external knowledge.\n"
        "3. Every factual statement must be cited immediately with the exact source metadata in square brackets:\n"
        "   - For Mutual Fund details: [Source: Document Title]\n"
        "   - For Stock details: [Source: Stock Name (URL)]\n"
        "4. Never give recommendations, buy/sell guidance, or advisory inputs. Refuse such queries politely."
    )

    context_str = "---\nRETRIEVED CONTEXT CHUNKS:\n"
    for i, chunk in enumerate(chunks, 1):
        content = chunk.get("content", "")
        # Determine source metadata string
        if chunk.get("type") == "mutual_fund":
            source = chunk["source_metadata"].get("title", "Groww Verified AMC Document")
        else:
            name = chunk.get("stock_name", "Stock Details")
            url = chunk["source_metadata"].get("url", "")
            source = f"{name} ({url})"
        
        context_str += f"[{i}] Content: \"{content}\"\nSource: {source}\n\n"
    context_str += "---\n"

    user_prompt = f"{context_str}\nUser Question: {query}"
    return system_instruction, user_prompt


def post_process_citations(answer: str, chunks: list[dict]) -> str:
    """
    Validates that the answer contains citation patterns [Source: ...].
    If missing, appends correct source citations based on the retrieved chunk metadata.
    """
    # If the answer indicates out-of-corpus deflection, we don't append citations
    if "I do not have this information in my verified records." in answer:
        return answer

    # Check if a citation is already present
    if "[Source:" in answer:
        return answer

    # If missing, construct citations for all retrieved chunks
    citations = []
    for chunk in chunks:
        if chunk.get("type") == "mutual_fund":
            title = chunk["source_metadata"].get("title", "Groww Verified AMC Document")
            citations.append(f"[Source: {title}]")
        else:
            name = chunk.get("stock_name", "Stock Details")
            url = chunk["source_metadata"].get("url", "")
            citations.append(f"[Source: {name} ({url})]")

    # Remove duplicates while preserving order
    seen = set()
    unique_citations = [x for x in citations if not (x in seen or seen.add(x))]

    if unique_citations:
        citation_str = " " + " ".join(unique_citations)
        return answer.strip() + citation_str

    return answer


def query_groq(system_instruction: str, user_prompt: str, model: str = GROQ_MODEL) -> str:
    """
    Queries the Groq Cloud completions API with strict factual parameters and 5.0s timeout.
    Returns the generated answer or the traffic fallback message.
    """
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY environment variable is missing.")
        return "The assistant is experiencing high traffic. Please try again shortly."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 1024,
        "top_p": 1e-9  # For maximum determinism
    }

    try:
        response = requests.post(
            GROQ_API_URL,
            headers=headers,
            json=payload,
            timeout=5.0
        )
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"].strip()
        else:
            logger.error(f"Groq API returned status code {response.status_code}: {response.text}")
    except requests.exceptions.Timeout:
        logger.warning("Groq API request timed out (5s limit).")
    except Exception as e:
        logger.error(f"Failed to query Groq API: {e}")

    return "The assistant is experiencing high traffic. Please try again shortly."


def generate_cited_answer(query: str, chunks: list[dict], model: str = GROQ_MODEL) -> str:
    """
    Synthesizes a cited answer for a query using retrieved chunks and the Groq LLM.
    """
    if not chunks:
        return "I do not have this information in my verified records."

    system_instruction, user_prompt = build_prompt(query, chunks)
    raw_answer = query_groq(system_instruction, user_prompt, model)
    
    # Apply citation fallback if raw_answer is successful (i.e. not the traffic error message)
    if raw_answer != "The assistant is experiencing high traffic. Please try again shortly.":
        raw_answer = post_process_citations(raw_answer, chunks)
        
    return raw_answer
