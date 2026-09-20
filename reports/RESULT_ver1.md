# RAG evaluation results

## Run information

| Field | Value |
|---|---|
| Evaluation date | 2026-09-20 |
| Framework and version | Ragas 0.4.3 |
| Evaluator model | `gpt-4o-mini` |
| Generator model | `gpt-4o-mini` |
| Embedding model | `text-embedding-3-small` |
| Corpus version/commit | `beb8f79`; 3 legal + 10 news documents |
| Golden dataset size | 18 questions |
| Evaluation runs | 36 (18 questions × 2 configurations) |
| `top_k` | 5 |
| Fallback threshold | `0.5215`, calibrated on 18 in-domain + 5 out-of-domain queries |

## Configurations

- **Config A — dense-only:** semantic vector search; không dùng BM25, RRF hoặc PageIndex.
- **Config B — hybrid + RRF:** dense search kết hợp BM25, hợp nhất kết quả bằng RRF với `k=60`; không dùng PageIndex trong A/B test.

Hai cấu hình dùng chung corpus, golden dataset, generator, evaluator, prompt và `top_k`. Fallback được tắt trong A/B để chỉ đo ảnh hưởng của retrieval strategy.

## Overall scores

| Metric | Config A | Config B | Delta B−A |
|---|---:|---:|---:|
| Faithfulness | 0.8487 | 0.8912 | +0.0425 |
| Answer relevance | 0.5326 | 0.5264 | -0.0063 |
| Context recall | 0.8148 | 0.9120 | +0.0972 |
| Context precision | 0.7829 | 0.7872 | +0.0042 |
| **Average** | **0.7448** | **0.7792** | **+0.0344** |

Latency trung bình quan sát được: dense-only `3,52s/query`, hybrid + RRF `2,83s/query`. Chênh lệch này có thể chịu ảnh hưởng của API/network vì mỗi cấu hình mới được chạy một lượt; chưa nên diễn giải là hybrid luôn nhanh hơn.
(Chủ yếu là do mạng)

## A/B comparison

- **Cấu hình tốt hơn:** hybrid + RRF.
- **Evidence:** điểm trung bình tăng từ `0,7448` lên `0,7792`; mức tăng lớn nhất là Context Recall (`+0,0972`). Điều này cho thấy kết hợp lexical signal giúp tìm đủ evidence hơn trên corpus pháp luật và tin tức.
- **Trade-off:** Answer Relevance giảm nhẹ `0,0063`; hybrid cần thêm BM25 và bước RRF nên phức tạp hơn về tính toán, dù latency của lần chạy này thấp hơn `0,69s/query`.
- **Kết luận:** chọn hybrid + RRF làm retrieval mặc định, nhưng tiếp tục tối ưu prompt/chunking để cải thiện relevance và các case pháp luật thất bại.

## Threshold calibration

| Metric | Result |
|---|---:|
| Proposed threshold | 0.5215 |
| Balanced accuracy | 1.0000 |
| In-domain recall | 1.0000 |
| Out-of-domain specificity | 1.0000 |

Threshold chỉ dùng cho fallback runtime, không dùng trong A/B. Vì calibration mới có 23 query và chưa có holdout độc lập, cần xác nhận lại trước khi coi đây là ngưỡng production.

## Worst performers

| # | Question | Config | Faithfulness | Relevance | Recall | Precision | Failure stage | Root cause |
|---:|---|---|---:|---:|---:|---:|---|---|
| 1 | Luật Du lịch 2017 định nghĩa du lịch cộng đồng ra sao? | dense-only | 0.0000 | 0.0000 | 0.0000 | 0.0000 | Data/retrieval | Top-5 không chứa đoạn định nghĩa; generator fallback “không thể xác minh”. Chunking/OCR của Điều 3 cần được kiểm tra. |
| 2 | Luật Du lịch 2017 định nghĩa du lịch cộng đồng ra sao? | hybrid + RRF | 0.0000 | 0.0000 | 0.0000 | 0.0000 | Data/retrieval | BM25 + dense vẫn đưa các chunk mở đầu/phạm vi điều chỉnh lên top-5, không lấy đúng định nghĩa. |
| 3 | Khu du lịch cấp tỉnh phải đáp ứng tối thiểu bao nhiêu lượt khách ăn uống, mua sắm và lưu trú mỗi năm? | dense-only | 0.1429 | 0.3847 | 0.0000 | 0.0000 | Retrieval/generation | Context không khớp reference và câu trả lời sinh ra ngưỡng `500.000/300.000`, sai so với đáp án chuẩn. |

## Recommendations

| Priority | Action | Evidence | Expected impact | How to verify |
|---:|---|---|---|---|
| 1 | Kiểm tra và sửa đoạn Điều 3 chứa “Luật Du lịch 2017 định nghĩa du lịch cộng đồng”; chunk theo ranh giới Điều/Khoản | `legal-002` đạt 0 ở cả hai config | Khôi phục recall cho định nghĩa pháp luật | Chạy lại `legal-002`, yêu cầu recall và precision > 0 |
| 2 | Bổ sung/tinh chỉnh lexical normalization cho số, đơn vị và cụm “tối thiểu” | Dense-only trả sai số ở `legal-009`; hybrid lấy đúng hơn | Tăng độ chính xác câu hỏi định lượng | Regression `legal-008`, `legal-009` trên cả hai config |
| 3 | Mở rộng calibration và benchmark bằng tập holdout | Threshold đạt 1,0 trên tập nhỏ 18 + 5 | Giảm nguy cơ overfit threshold | Chọn ngưỡng trên calibration, chỉ báo cáo kết quả cuối trên holdout |
| 4 | Lặp benchmark latency nhiều lần và báo cáo median/p95 | Kết quả hiện tại chịu biến động API/network | So sánh hiệu năng đáng tin cậy hơn | Chạy ≥5 lần/config, cùng cache và điều kiện |

## Outputs và khả năng tái lập

- Script chạy benchmark: `scripts/evaluate_rag.py`.
- Kết quả chi tiết từng câu: `group_project/evaluation/benchmark_results.json`.
- Mỗi case lưu question, reference, answer, retrieved contexts, source IDs, retrieval methods, latency và đủ bốn Ragas metrics.
- Script hỗ trợ checkpoint/resume và các tùy chọn giới hạn generation/evaluation để chạy thử trước khi benchmark đầy đủ.

## Bonus experiments

Chưa thực hiện HyDE hoặc reranker nâng cao. Baseline ưu tiên hiện tại là hybrid + RRF; các thử nghiệm tiếp theo chỉ nên thực hiện sau khi sửa các lỗi dữ liệu/chunking ở nhóm worst performers để tránh che lấp nguyên nhân gốc.
