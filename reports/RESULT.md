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
| Faithfulness      | 0.9611      | 0.9444      | −0.0167     |
| Answer relevance  | 0.8889      | 0.9444      | +0.0555     |
| Context recall    | 0.7833      | 0.8389      | +0.0556     |
| Context precision | 0.7111      | 0.7222      | +0.0111     |
| **Average**       | **0.8361**  | **0.8625**  | **+0.0264** |

## Per-question detail — Config A (dense-only)

| # | ID | Question (rút gọn) | F | R | CR | CP | Avg | Trạng thái |
| -: | --- | ------------------- | --: | --: | --: | --: | ---: | ---------- |
| 1 | legal-001 | Định nghĩa du lịch theo Luật 2017 | 1.00 | 1.00 | 1.00 | 0.00 | 0.75 | 🟡 CP thấp |
| 2 | legal-002 | Định nghĩa du lịch cộng đồng | 1.00 | 0.00 | 0.00 | 0.00 | 0.25 | 🔴 Safe refusal |
| 3 | legal-003 | Quyền an toàn và bồi thường khách DL | 1.00 | 1.00 | 0.80 | 0.60 | 0.85 | 🟡 Khá |
| 4 | legal-004 | Nghĩa vụ khách DL Điều 12 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 5 | legal-005 | Điều kiện công nhận điểm DL | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 6 | legal-006 | DN nước ngoài KD lữ hành | 0.50 | 1.00 | 1.00 | 0.80 | 0.82 | 🟡 F thấp |
| 7 | legal-007 | Điều kiện KD lữ hành nội địa | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 8 | legal-008 | Mức ký quỹ lữ hành | 1.00 | 1.00 | 0.50 | 0.80 | 0.82 | 🟡 CR thấp |
| 9 | legal-009 | KDL cấp tỉnh lượt khách | 1.00 | 1.00 | 0.50 | 1.00 | 0.88 | 🟡 CR thấp |
| 10 | legal-010 | KDL quốc gia năng lực PV | 1.00 | 1.00 | 1.00 | 0.80 | 0.95 | 🟢 Tốt |
| 11 | policy-011 | Mục tiêu khách DL 2025 | 1.00 | 0.00 | 0.00 | 0.00 | 0.25 | 🔴 Safe refusal |
| 12 | policy-012 | Tổng thu GDP việc làm 2030 | 0.80 | 1.00 | 0.50 | 0.80 | 0.78 | 🟡 F thấp |
| 13 | news-013 | Du lịch ẩm thực là gì | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 14 | news-014 | Chi thêm cho ẩm thực | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 15 | news-015 | Hạn chế khai thác ẩm thực VN | 1.00 | 1.00 | 0.80 | 0.00 | 0.70 | 🟡 CP=0 |
| 16 | news-016 | Đặc sản Cao Bằng Top 100 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 17 | news-017 | 6 món Huế chứng nhận 2022 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 18 | news-018 | Nem chua Thanh Hóa | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |

**Tóm tắt Config A:** 🟢 ≥0.9: **9/18** (50%) · 🟡 0.7–0.89: **7/18** (38.9%) · 🔴 <0.7: **2/18** (11.1%)

## Per-question detail — Config B (hybrid + RRF)

| # | ID | Question (rút gọn) | F | R | CR | CP | Avg | Trạng thái |
| -: | --- | ------------------- | --: | --: | --: | --: | ---: | ---------- |
| 1 | legal-001 | Định nghĩa du lịch theo Luật 2017 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 2 | legal-002 | Định nghĩa du lịch cộng đồng | 1.00 | 0.00 | 0.00 | 0.00 | 0.25 | 🔴 Safe refusal |
| 3 | legal-003 | Quyền an toàn và bồi thường khách DL | 1.00 | 1.00 | 0.80 | 0.60 | 0.85 | 🟡 Khá |
| 4 | legal-004 | Nghĩa vụ khách DL Điều 12 | 1.00 | 1.00 | 1.00 | 0.00 | 0.75 | 🟡 CP=0 |
| 5 | legal-005 | Điều kiện công nhận điểm DL | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 6 | legal-006 | DN nước ngoài KD lữ hành | 1.00 | 1.00 | 1.00 | 0.80 | 0.95 | 🟢 Tốt |
| 7 | legal-007 | Điều kiện KD lữ hành nội địa | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 8 | legal-008 | Mức ký quỹ lữ hành | 0.00 | 1.00 | 0.50 | 0.80 | 0.57 | 🔴 F=0 hallucinate |
| 9 | legal-009 | KDL cấp tỉnh lượt khách | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 10 | legal-010 | KDL quốc gia năng lực PV | 1.00 | 1.00 | 1.00 | 0.80 | 0.95 | 🟢 Tốt |
| 11 | policy-011 | Mục tiêu khách DL 2025 | 1.00 | 1.00 | 0.50 | 0.00 | 0.62 | 🔴 CR+CP thấp |
| 12 | policy-012 | Tổng thu GDP việc làm 2030 | 1.00 | 1.00 | 0.50 | 0.60 | 0.78 | 🟡 CR thấp |
| 13 | news-013 | Du lịch ẩm thực là gì | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 14 | news-014 | Chi thêm cho ẩm thực | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 15 | news-015 | Hạn chế khai thác ẩm thực VN | 1.00 | 1.00 | 0.80 | 0.40 | 0.80 | 🟡 CP thấp |
| 16 | news-016 | Đặc sản Cao Bằng Top 100 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 17 | news-017 | 6 món Huế chứng nhận 2022 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |
| 18 | news-018 | Nem chua Thanh Hóa | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 🟢 Tuyệt đối |

**Tóm tắt Config B:** 🟢 ≥0.9: **11/18** (61.1%) · 🟡 0.7–0.89: **4/18** (22.2%) · 🔴 <0.7: **3/18** (16.7%)

## A/B comparison

- **Cấu hình tốt hơn:** Config B (hybrid + RRF) nhỉnh hơn, average cao hơn **+0.0264**.
- **Evidence:** Cả hai config đều hoạt động tốt (A=0.8361, B=0.8625). Config B hơn ở answer relevance (+0.06) và context recall (+0.06) nhờ BM25 bổ sung kết quả keyword-match mà dense bỏ lỡ.
- **Config A hơn ở faithfulness** (−0.0167): dense-only ít nguy cơ hallucination hơn vì không trộn nguồn từ BM25.
- **Trade-off:** Config B chạy thêm BM25 + RRF nhưng BM25 tính local (nhanh). Lợi ích nhỏ (+2.6%) có thể không đáng khi triển khai production khi Corpus chỉ có 13 file markdown. vì với corpus nhỏ, dense search đã cover gần hết các chunk liên quan. BM25 chỉ thực sự vượt trội khi corpus lớn. Thêm nữa trong dự án này nhóm sử dụng 18 câu hỏi đều hỏi về nội dung/ý nghĩa của văn bản, mà mô hình dense lại có thế mạnh về ngữ nghĩa nên việc config B chưa cho thấy khả năng vượt trội so với A là điều có thể hiểu được. Thếm nữa, nhóm sử dụng text-embedding-3-small đã xử lý tiếng việt đủ tốt cho dự án của nhóm. Ngoài ra, Khi dense đã xếp hạng tốt, BM25 có thể đẩy chunk không liên quan lên cao làm loãng kết quả. Ví dụ như legal-004 và 008. 

## Worst performers

Ba câu có trung bình bốn metric thấp nhất:

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
| -: | -------- | ------ | -----------: | --------: | -----: | --------: | ------------- | ---------- |
| 1 | Định nghĩa du lịch cộng đồng? | A (dense) | 1.00 | 0.00 | 0.00 | 0.00 | Generation | Chunks không chứa định nghĩa "du lịch cộng đồng" → safe refusal |
| 2 | Mục tiêu khách quốc tế/nội địa 2025? | A (dense) | 1.00 | 0.00 | 0.00 | 0.00 | Retrieval | Chunks lấy về từ phần khác của chiến lược, thiếu mục tiêu 2025 |
| 3 | Định nghĩa du lịch cộng đồng? | B (hybrid) | 1.00 | 0.00 | 0.00 | 0.00 | Generation | Cả dense lẫn BM25 đều không tìm được chunk chứa định nghĩa |

**Nhận xét:** legal-002 (du lịch cộng đồng) thất bại ở cả 2 config → vấn đề nằm ở **chunking**: định nghĩa nằm trong phần đầu Luật nhưng chunk 500 chars cắt ngang, hoặc context trả về không đủ rõ ràng để LLM tổng hợp.

## Recommendations

| Priority | Action | Evidence from failure analysis | Expected impact | How to verify |
| -------: | ------ | ------------------------------ | --------------- | ------------- |
| 1 | Tăng chunk_size (1000–1500 chars) cho văn bản pháp lý | legal-002, policy-011 thất bại do chunks 500 chars cắt ngang định nghĩa | Tăng context recall cho câu hỏi pháp lý | Chạy lại eval sau khi re-index với chunk_size mới |
| 2 | Bổ sung metadata "section" khi chunking | legal-008 thiếu mức ký quỹ ra nước ngoài (CR=0.5) — nằm ở section khác | Retrieval chính xác hơn theo section | Kiểm tra top-5 chunks có từ đúng section |
| 3 | Thêm query expansion cho câu hỏi chính sách | policy-011 dense không tìm thấy "mục tiêu 2025" | Tăng answer relevance cho nhóm chính sách | So sánh trước/sau query expansion |

## Bonus experiments

| Experiment | Baseline | Metric delta | Latency/cost delta | Conclusion |
| ---------- | -------- | -----------: | -----------------: | ---------- |
| Chưa thực hiện bonus | Config B | Chưa đo | Chưa đo | Ưu tiên cải thiện chunking trước khi thử nghiệm bonus |
