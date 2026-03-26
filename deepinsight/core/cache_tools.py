import time
from datetime import datetime

import chromadb
from sentence_transformers import SentenceTransformer


class SemanticCache:
    def __init__(self, similarity_threshold=0.95, model_name="all-MiniLM-L6-v2"):
        self.similarity_threshold = similarity_threshold
        self.model = SentenceTransformer(model_name)
        self.client = chromadb.EphemeralClient()
        self.collection = self.client.get_or_create_collection(
            name="semantic_cache",
            metadata={"hnsw:space": "cosine"},
        )
        self.exact_cache = {}

    def _normalize_query(self, user_query):
        return " ".join(user_query.strip().lower().split())

    def _embed(self, text):
        embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def check_cache(self, user_query):
        normalized_query = self._normalize_query(user_query)
        if normalized_query in self.exact_cache:
            return {
                "hit": True,
                "mode": "exact",
                "answer": self.exact_cache[normalized_query],
                "score": 1.0,
            }

        embedding = self._embed(normalized_query)
        result = self.collection.query(query_embeddings=[embedding], n_results=1, include=["distances", "metadatas"])
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        if not metadatas or not distances:
            return {"hit": False, "mode": "miss", "answer": None, "score": 0.0}
        score = 1 - float(distances[0])
        if score >= self.similarity_threshold:
            return {
                "hit": True,
                "mode": "semantic",
                "answer": metadatas[0]["answer"],
                "score": score,
            }
        return {"hit": False, "mode": "miss", "answer": None, "score": score}

    def update_cache(self, user_query, answer):
        normalized_query = self._normalize_query(user_query)
        self.exact_cache[normalized_query] = answer
        embedding = self._embed(normalized_query)
        cache_id = f"cache-{len(self.exact_cache)}-{int(time.time() * 1000)}"
        self.collection.upsert(
            ids=[cache_id],
            documents=[normalized_query],
            embeddings=[embedding],
            metadatas=[{"answer": answer, "created_at": datetime.now().isoformat(timespec="seconds")}],
        )


if __name__ == "__main__":
    cache = SemanticCache()
    question = "ST生物2023年的经营质量怎么样？"
    answer = "ST生物2023年经营质量稳中改善，营收和现金流表现相对稳健。"

    start = time.perf_counter()
    first = cache.check_cache(question)
    first_elapsed = (time.perf_counter() - start) * 1000
    print("第一次查询：", first, f"耗时 {first_elapsed:.2f} ms")

    if not first["hit"]:
        cache.update_cache(question, answer)
        print("已写入缓存。")

    start = time.perf_counter()
    second = cache.check_cache(question)
    second_elapsed = (time.perf_counter() - start) * 1000
    print("第二次查询：", second, f"耗时 {second_elapsed:.2f} ms")
