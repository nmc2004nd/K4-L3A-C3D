# 📋 Phân tích dự án RAG Pipeline — Toàn bộ việc cần làm

## Tổng quan
Đây là bài nhóm **Day 8 — RAG Pipeline**: Xây chatbot RAG trả lời câu hỏi từ bộ tài liệu do nhóm thu thập, có hybrid retrieval, citation, giao diện Streamlit và báo cáo đánh giá.

> [!CAUTION]
> **Tất cả 10 task đều chưa implement** — mọi hàm đều đang `raise NotImplementedError`. Dự án hiện tại chỉ có **skeleton code** (khung sườn) với hướng dẫn trong comment.

---

## Trạng thái từng Task

| Task | File | Trạng thái | Mô tả |
|------|------|:----------:|--------|
| 1 | [`task1_collect_legal_docs.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task1_collect_legal_docs.py) | ❌ | Tải ≥3 PDF/DOCX tài liệu chính sách vào `data/landing/legal/` |
| 2 | [`task2_crawl_news.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task2_crawl_news.py) | ❌ | Crawl ≥5 bài viết vào `data/landing/news/` (dùng Crawl4AI) |
| 3 | [`task3_convert_markdown.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task3_convert_markdown.py) | ❌ | Convert PDF/DOCX → Markdown, JSON → Markdown vào `data/standardized/` |
| 4 | [`task4_chunking_indexing.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task4_chunking_indexing.py) | ❌ | Chunking (RecursiveCharacterTextSplitter), embed (BGE-M3), index vào ChromaDB |
| 5 | [`task5_semantic_search.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task5_semantic_search.py) | ❌ | Dense search từ ChromaDB, trả `SearchResult` |
| 6 | [`task6_lexical_search.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task6_lexical_search.py) | ❌ | BM25 search trên cùng corpus, trả `SearchResult` |
| 7 | [`task7_reranking.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task7_reranking.py) | ❌ | RRF fusion: `sum(1/(k+rank))`, gộp dense + BM25 |
| 8 | [`task8_pageindex_vectorless.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task8_pageindex_vectorless.py) | ❌ | PageIndex fallback (vectorless search) |
| 9 | [`task9_retrieval_pipeline.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task9_retrieval_pipeline.py) | ❌ | Pipeline hoàn chỉnh: dense + BM25 → RRF → fallback |
| 10 | [`task10_generation.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/task10_generation.py) | ❌ | Reorder chunks, format context, gọi LLM, trả `GenerationResult` có citation |
| UI | [`app.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/app.py) | ❌ | Chatbot Streamlit — có 4 TODO chưa hoàn thiện |
| Eval | [`RESULT.md`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/group_project/evaluation/RESULT.md) | ❌ | Toàn bộ là placeholder `TODO` |
| Golden | [`golden_dataset.json`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/group_project/evaluation/golden_dataset.json) | ❌ | File rỗng, cần ≥15 Q&A |

---

## Chi tiết việc cần làm theo thứ tự

### Phase 1: Data Collection (Task 1–3)

#### ✅ Bước 0 — Chọn đề tài & Setup
- [ ] Chọn chủ đề (tham khảo [`SUGGESTED_TOPICS.md`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/docs/SUGGESTED_TOPICS.md))
- [ ] Cài đặt môi trường (`.venv`, dependencies, playwright)
- [ ] Điền `.env` (API key cho LLM provider, embedding, PageIndex...)

#### ✅ Bước 1 — Task 1: Thu thập tài liệu chính sách
- [ ] Tìm ≥3 PDF/DOCX công khai về chủ đề đã chọn
- [ ] Implement `download_documents()` — tải về `data/landing/legal/`

#### ✅ Bước 2 — Task 2: Crawl bài viết
- [ ] Điền ≥5 URL vào `ARTICLE_URLS`
- [ ] Implement `crawl_article()` dùng Crawl4AI (hoặc Firecrawl)
- [ ] Mỗi bài lưu JSON: `{url, title, date_crawled, content_markdown}`

#### ✅ Bước 3 — Task 3: Chuẩn hóa Markdown
- [ ] Implement `convert_legal_docs()` — dùng MarkItDown convert PDF/DOCX
- [ ] Implement `convert_news_articles()` — convert JSON sang Markdown kèm header metadata

### Phase 2: Indexing & Search (Task 4–7)

#### ✅ Bước 4 — Task 4: Chunking & Indexing
- [ ] `embed_texts()` — dùng SentenceTransformer + `BAAI/bge-m3` (1024 dim)
- [ ] `get_collection()` — tạo ChromaDB persistent collection (cosine)
- [ ] `load_documents()` — đọc tất cả `.md` từ `data/standardized/`
- [ ] `chunk_documents()` — RecursiveCharacterTextSplitter (500 chars, 50 overlap)
- [ ] `embed_chunks()` — embed batch
- [ ] `index_to_vectorstore()` — upsert vào ChromaDB

#### ✅ Bước 5 — Task 5: Semantic Search
- [ ] `semantic_search()` — query ChromaDB, chuyển cosine distance → similarity score

#### ✅ Bước 6 — Task 6: BM25 Search
- [ ] `build_bm25_index()` — tokenize + tạo BM25Okapi index
- [ ] `lexical_search()` — tính BM25 score, sort giảm dần

#### ✅ Bước 7 — Task 7: RRF Fusion
- [ ] `rerank_rrf()` — công thức `sum(1/(k+rank))`, rank từ 1

### Phase 3: Pipeline & Generation (Task 8–10)

#### ✅ Bước 8 — Task 8: PageIndex Fallback
- [ ] `upload_documents()` — upload tài liệu lên PageIndex
- [ ] `pageindex_search()` — query và parse thành SearchResult

#### ✅ Bước 9 — Task 9: Retrieval Pipeline
- [ ] `retrieve()` — dense + BM25 → RRF → check threshold → fallback nếu cần

#### ✅ Bước 10 — Task 10: Generation
- [ ] `reorder_for_llm()` — lost-in-the-middle reordering
- [ ] `format_context()` — format kèm title/source
- [ ] `call_llm()` — dispatch theo `LLM_PROVIDER` (openai/gemini/anthropic)
- [ ] `generate_with_citation()` — end-to-end, trả `GenerationResult`

### Phase 4: UI & Evaluation

#### ✅ Bước 11 — Hoàn thiện Chatbot UI
- [ ] Gọi `generate_with_citation()` trong `app.py`
- [ ] Hiển thị sources, retrieval method, score
- [ ] Lưu answer + sources vào session state

#### ✅ Bước 12 — Evaluation
- [ ] Tạo ≥15 golden Q&A trong `golden_dataset.json`
- [ ] Chạy 4 metric: faithfulness, answer relevance, context recall, context precision
- [ ] So sánh A/B: dense-only vs hybrid+RRF
- [ ] Điền [`RESULT.md`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/group_project/evaluation/RESULT.md)

#### ✅ Bước 13 — Test & Nộp bài
- [ ] Chạy `pytest tests/test_contracts.py -q`
- [ ] Chạy `pytest tests/test_acceptance.py -q`
- [ ] Viết báo cáo cá nhân (mỗi thành viên)
- [ ] Kiểm tra không commit `.env` / API key

---

## Rubric chấm điểm (90 + 10 bonus)

| Hạng mục | Điểm |
|----------|-----:|
| Dữ liệu rõ ràng, chuẩn hóa | 10 |
| Chunking, embedding, vector DB | 10 |
| Dense search, BM25 và RRF | **20** |
| Retrieval pipeline và fallback | 10 |
| Generation có citation + safe refusal | **15** |
| Chatbot end-to-end, hiển thị nguồn | 10 |
| Golden dataset, 4 metrics, A/B | 10 |
| README, chạy lại được, individual reports | 5 |
| **Bonus:** HyDE/query expansion (+3), Reranker nâng cao (+3), Conversation memory (+2), Deploy/UI highlighting (+2) | +10 |

---

## Contracts cần tuân thủ

Xem chi tiết tại [`contracts.py`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/src/contracts.py) và [`MODULE_CONTRACTS.md`](file:///d:/AI_Thucchien/K4-L3A-RAG-Pipeline/docs/MODULE_CONTRACTS.md):

- **Document/Chunk**: `{id, content, metadata: {source, title, doc_type, url, chunk_index}}`
- **SearchResult**: `{id, content, score, metadata, retrieval_method}`
- **GenerationResult**: `{answer, sources, retrieval_source}`
- ID phải unique, score sort giảm dần, RRF chỉ fuse 1 lần
- Fallback dùng **dense cosine score gốc**, KHÔNG dùng RRF score
