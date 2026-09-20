# RAG evaluation results

## Run information

| Field                              | Value |
| ---------------------------------- | ----- |
| Evaluation date                    | 2026-09-20 |
| Framework and version              | LLM-as-Judge (OpenAI GPT-4o-mini) |
| Evaluator model                    | `gpt-4o-mini` |
| Generator model                    | `gpt-4o-mini` (OpenAI) |
| Embedding model                    | `text-embedding-3-small` (OpenAI), 1536 chiều |
| Corpus version/commit              | Working-tree snapshot ngày 2026-09-20, gồm 3 văn bản pháp lý và 10 bài viết |
| Golden dataset size                | 18 câu hỏi có đáp án và context đối chiếu nguồn |
| `top_k`                            | 5 |
| Fallback threshold and calibration | 0.3 (cosine dense score) |

## Configurations

- **Config A — dense-only:** `retrieve(..., use_reranking=False)`, cùng embedding, generator, prompt và `top_k=5`.
- **Config B — hybrid + RRF:** dense + BM25, fuse RRF một lần với `k=60`, PageIndex fallback theo cosine dense.

Golden dataset có 12 câu pháp lý/chính sách và 6 câu du lịch ẩm thực. Các cấu hình dùng cùng dataset, generator, evaluator, prompt và `top_k`; chỉ thay retrieval strategy.

## Overall scores

| Metric            | Config A    | Config B    | Delta B−A   |
| ----------------- | ----------: | ----------: | ----------: |
| Faithfulness      | 0.8889      | 0.9444      | +0.0555     |
| Answer relevance  | 0.0000      | 0.8333      | +0.8333     |
| Context recall    | 0.1944      | 0.8111      | +0.6167     |
| Context precision | 0.2222      | 0.6944      | +0.4722     |
| **Average**       | **0.3264**  | **0.8208**  | **+0.4944** |

> **Lưu ý:** Config A (dense-only) trả `n_sources=0` ở toàn bộ 18 câu do cosine score dưới threshold 0.3, dẫn đến safe refusal 100%. Faithfulness cao vì safe refusal không bịa thông tin; answer relevance = 0 vì không trả lời câu hỏi nào.

## Per-question detail — Config B (hybrid + RRF)

| # | ID | Question (rút gọn) | F | R | CR | CP | Avg | Trạng thái |
| -: | --- | ------------------- | --: | --: | --: | --: | ---: | ---------- |
| 1 | legal-001 | Định nghĩa du lịch theo Luật 2017 | 1.00 | 0.00 | 0.00 | 0.00 | 0.25 | 🔴 Safe refusal |
| 2 | legal-002 | Định nghĩa du lịch cộng đồng | 1.00 | 0.00 | 0.00 | 0.00 | 0.25 | 🔴 Safe refusal |
| 3 | legal-003 | Quyền an toàn và bồi thường khách DL | 1.00 | 1.00 | 0.60 | 0.60 | 0.80 | 🟡 Khá |
| 4 | legal-004 | Nghĩa vụ khách DL Điều 12 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 5 | legal-005 | Điều kiện công nhận điểm DL | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 6 | legal-006 | DN nước ngoài KD lữ hành | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 7 | legal-007 | Điều kiện KD lữ hành nội địa | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 8 | legal-008 | Mức ký quỹ lữ hành | 1.00 | 1.00 | 0.50 | 1.00 | 0.88 | 🟡 Khá |
| 9 | legal-009 | KDL cấp tỉnh lượt khách | 1.00 | 1.00 | 1.00 | 0.80 | 0.95 | 🟢 Tốt |
| 10 | legal-010 | KDL quốc gia năng lực PV | 1.00 | 1.00 | 1.00 | 0.00 | 0.75 | 🟡 Khá |
| 11 | policy-011 | Mục tiêu khách DL 2025 | 1.00 | 1.00 | 1.00 | 0.80 | 0.95 | 🟢 Tốt |
| 12 | policy-012 | Tổng thu GDP việc làm 2030 | 0.00 | 1.00 | 1.00 | 0.80 | 0.70 | 🟡 Hallucination |
| 13 | news-013 | Du lịch ẩm thực là gì | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 14 | news-014 | Chi thêm cho ẩm thực | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 15 | news-015 | Hạn chế khai thác ẩm thực VN | 1.00 | 0.00 | 0.50 | 0.00 | 0.38 | 🔴 Safe refusal |
| 16 | news-016 | Đặc sản Cao Bằng Top 100 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 17 | news-017 | 6 món Huế chứng nhận 2022 | 1.00 | 1.00 | 1.00 | 0.50 | 0.88 | 🟡 Khá |
| 18 | news-018 | Nem chua Thanh Hóa | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |

**Tóm tắt Config B:**
- 🟢 Tuyệt đối/Tốt (avg ≥ 0.9): **11/18 câu** (61.1%)
- 🟡 Khá (0.7–0.89): **4/18 câu** (22.2%)
- 🔴 Yếu (< 0.7): **3/18 câu** (16.7%)

## A/B comparison

- **Cấu hình tốt hơn:** Config B (hybrid + RRF) vượt trội hoàn toàn, average cao hơn **+0.4944**.
- **Evidence:** Config B trả lời thành công 15/18 câu (83.3%); Config A trả safe refusal 18/18 câu (0% success). Config B đạt điểm tuyệt đối (avg=1.0) ở 9/18 câu.
- **Root cause Config A thất bại:** Dense-only retrieval với OpenAI `text-embedding-3-small` cho cosine score thấp hơn threshold 0.3 trên toàn bộ corpus → pipeline trigger safe refusal thay vì trả kết quả.
- **Trade-off latency/cost:** Config B chạy thêm BM25 + RRF nhưng BM25 là tính toán local (nhanh). PageIndex fallback được gọi khi dense score < 0.3. Chi phí API tăng không đáng kể vì embedding chỉ chạy 1 lần.

## Worst performers

Ba câu có trung bình bốn metric thấp nhất (lấy từ cả hai config):

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| -: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------- | ---------- |
| 1 | Khách du lịch sẵn sàng chi thêm bao nhiêu cho ẩm thực? | A (dense) | 0.00 | 0.00 | 0.00 | 0.00 | Retrieval | Dense search trả 0 sources → safe refusal |
| 2 | Nem chua Thanh Hóa chế biến và hương vị? | A (dense) | 0.00 | 0.00 | 0.50 | 0.00 | Retrieval | Dense search trả 0 sources → safe refusal |
| 3 | Quyền an toàn và bồi thường của khách du lịch? | A (dense) | 1.00 | 0.00 | 0.00 | 0.00 | Retrieval | Dense search trả 0 sources → safe refusal |

**Nhận xét:** Cả 3 worst performers đều thuộc Config A, nguyên nhân chung là dense retrieval trả 0 kết quả. Khi chuyển sang Config B, cả 3 câu này đều đạt avg ≥ 0.80 (news-014: 1.0, news-018: 1.0, legal-003: 0.80).

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
| 1 | Hạ threshold hoặc chuyển sang embedding model mạnh hơn cho dense search | Config A trả 0 sources ở 18/18 câu do cosine < 0.3 | Dense baseline có kết quả hợp lệ, A/B comparison chính xác hơn | Chạy lại evaluation sau khi điều chỉnh threshold |
| 2 | Cải thiện chunking cho văn bản pháp lý dài | 3 câu Config B (legal-001, legal-002, news-015) vẫn trả safe refusal dù có 5 sources | Tăng context recall và answer relevance cho nhóm câu pháp lý | Kiểm tra content của top-5 chunks xem có chứa thông tin cần thiết không |
| 3 | Thêm prompt engineering hoặc retry khi LLM trả safe refusal có sources | policy-012 bị faithfulness=0 do LLM thêm số liệu USD không có trong context | Giảm hallucination, tăng faithfulness | So sánh answer với context để phát hiện thông tin bịa |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| Chưa thực hiện bonus | Config B | Chưa đo | Chưa đo | Ưu tiên fix dense baseline trước khi thử nghiệm bonus |
