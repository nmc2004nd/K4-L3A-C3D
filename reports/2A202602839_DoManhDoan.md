# Báo cáo đóng góp cá nhân

## Thông tin

- **Họ và tên:** Đỗ Mạnh Đoan
- **Mã học viên:** 2A202602839
- **Nhóm:** C3D
- **Repository/branch:** `https://github.com/nmc2004nd/K4-L3A-C3D` / `https://github.com/nmc2004nd/K4-L3A-C3D/tree/manh_doan`
- **Phạm vi báo cáo:** Từ bước rà soát và clean bổ sung dữ liệu đã chuẩn hóa đến xây dựng, chạy evaluation và log kết quả. 

## Phần việc đã thực hiện

| Module/deliverable | Việc trực tiếp thực hiện | Bằng chứng | Trạng thái |
|---|---|---|---|
| Data quality | Rà soát lại `data/standardized`; thống nhất cấu trúc Markdown, tiêu đề, khoảng trắng và ngắt dòng; loại nội dung lặp/nhiễu; sửa lỗi OCR/ký tự nghiêm trọng trong 3 văn bản pháp luật; clean bổ sung 5 bài báo có lỗi lớn | Commit `9363ef1`/`beb8f79`; 8 file Markdown, 836 dòng thêm và 2.726 dòng nhiễu/lặp được loại bỏ | Done |
| Evaluation pipeline | Xây dựng script benchmark có checkpoint/resume; chạy cùng golden dataset cho dense-only và hybrid + RRF; tích hợp bốn metric Ragas; lưu answer, context, nguồn, latency và điểm từng case | `scripts/evaluate_rag.py` | Done |
| Fallback calibration | Hiệu chỉnh score threshold từ 18 truy vấn in-domain và 5 truy vấn out-of-domain, tối ưu balanced accuracy | `group_project/evaluation/benchmark_results.json` | Done |
| Benchmark output | Chạy đủ 36 lượt đánh giá (18 câu × 2 cấu hình), tổng hợp A/B, worst performers và khuyến nghị | `group_project/evaluation/benchmark_results.json`, `reports/RESULT.md` | Done |

## Quyết định kỹ thuật quan trọng

1. **Cô lập biến retrieval trong A/B test.**  
   Hai cấu hình dùng chung corpus, 18 câu golden, generator, evaluator, prompt và `top_k=5`; fallback được tắt trong lúc A/B. Config A chỉ dùng dense retrieval, Config B dùng dense + BM25 và hợp nhất RRF với `k=60`. Cách này giúp chênh lệch điểm phản ánh chiến lược retrieval thay vì các biến khác. Trade-off là chưa đo riêng ảnh hưởng của PageIndex/fallback trong cùng thí nghiệm.

2. **Dùng evaluation có thể tiếp tục sau gián đoạn.**  
   Script ghi checkpoint sau từng case và tách generation khỏi scoring, vì đánh giá Ragas qua API có thể chậm hoặc gián đoạn. Cách làm tăng độ an toàn và khả năng tái lập, đổi lại file JSON chi tiết lớn hơn và tổng thời gian chạy dài hơn.

## Kiểm thử và kết quả

- Benchmark hoàn tất **36/36 lượt**, mỗi lượt có đủ Faithfulness, Answer Relevance, Context Recall và Context Precision.
- Dense-only đạt điểm trung bình **0,7448**; hybrid + RRF đạt **0,7792**, tăng **0,0344**.
- Hybrid + RRF cải thiện mạnh nhất ở Context Recall: **0,8148 → 0,9120** (`+0,0972`). Faithfulness tăng `+0,0425`, Context Precision tăng `+0,0042`; Answer Relevance giảm nhẹ `-0,0063`.
- Threshold đề xuất là **0,5215**; trên tập calibration hiện tại đạt balanced accuracy `1,0000`, in-domain recall `1,0000` và out-of-domain specificity `1,0000`.
- Lỗi nổi bật: câu `legal-002` không truy xuất được định nghĩa “du lịch cộng đồng” ở cả hai cấu hình nên cả bốn metric đều bằng 0. Case `legal-009` cho thấy dense-only trả sai ngưỡng lượt khách, trong khi hybrid lấy đúng thông tin hơn nhưng vẫn còn precision thấp.

## Hạn chế và hướng cải thiện

- Golden dataset mới có 18 câu và chỉ 5 câu out-of-domain dùng để hiệu chỉnh threshold; kết quả calibration 1,0 chưa đủ để kết luận khả năng tổng quát hóa. Cần thêm tập holdout chưa từng dùng để chọn threshold.
- Latency chịu ảnh hưởng của API/network và mỗi cấu hình mới chạy một lượt, vì vậy số đo `3,52s` so với `2,83s` chỉ mang tính tham khảo, không chứng minh hybrid luôn nhanh hơn dense-only.
- Dữ liệu pháp luật vẫn còn một số lỗi OCR ở cấp từ và chunking có thể tách mất định nghĩa. Ưu tiên tiếp theo là sửa nguồn/chunk cho `legal-002`, sau đó chạy lại các case lỗi và toàn bộ regression benchmark.

## Xác nhận đóng góp

Tôi xác nhận nội dung trên phản ánh đúng phần việc cá nhân từ giai đoạn clean bổ sung dữ liệu đến evaluation và output. Tôi có thể giải thích và chạy lại pipeline trong buổi demo.

- **Ngày:** 20/09/2026
- **Thành viên:** Đỗ Mạnh Đoan 
