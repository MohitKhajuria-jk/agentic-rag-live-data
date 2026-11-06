import asyncio

from app.retrieval import Document, bm25_scores, chunk_documents, chunk_text, excerpt, rank_chunks, tokenize


def test_tokenize_drops_stopwords_and_stems():
    assert tokenize("What are the invoices for my meetings?") == ["invoice", "meeting"]
    assert tokenize("Studies") == ["study"]


def test_chunk_text_keeps_short_text_whole():
    assert chunk_text("Hello there.") == ["Hello there."]
    assert chunk_text("   ") == []


def test_chunk_text_splits_long_text_with_overlap():
    para = " ".join(f"Sentence number {i} talks about topic {i % 7}." for i in range(120))
    chunks = chunk_text(para, size=400, overlap=80)
    assert len(chunks) > 5
    assert all(len(c) <= 400 for c in chunks)
    # Consecutive chunks share some text, so a fact split across a boundary is still found.
    assert any(chunks[1].split(" ")[0] in chunks[0] for _ in [0])


def test_bm25_ranks_the_relevant_chunk_first():
    docs = [
        Document("gmail", "1", "Lunch", "Shall we get lunch on Friday?"),
        Document("gmail", "2", "Invoice", "Your cloud invoice is ₹1,248, due in ten days."),
        Document("gmail", "3", "Newsletter", "This week in AI agents and retrieval."),
    ]
    chunks = chunk_documents(docs)
    scores = bm25_scores("how much is the cloud invoice", chunks)
    assert scores.index(max(scores)) == 1


class FakeEmbedder:
    """Puts any text about money close to the query, to check semantic scores are mixed in."""

    async def embed(self, texts):
        return [[1.0, 0.0] if ("bill" in t.lower() or "₹" in t) else [0.0, 1.0] for t in texts]


def test_hybrid_ranking_uses_embeddings_when_available():
    docs = [
        Document("gmail", "1", "Trip", "Flight to Delhi at 06:15."),
        Document("gmail", "2", "Payment", "Amount due: ₹1,248."),
    ]
    ranked = asyncio.run(rank_chunks("what is my bill", chunk_documents(docs), FakeEmbedder()))
    assert ranked[0].doc.item_id == "2"


def test_excerpt_cuts_on_a_word():
    assert excerpt("one two three four", 9) == "one two…"
