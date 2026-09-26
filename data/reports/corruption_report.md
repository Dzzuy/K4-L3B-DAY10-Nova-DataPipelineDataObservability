# Báo Cáo Đối Chiếu 3 Trạng Thái: Baseline vs Corrupted vs Repaired

## 1. Bảng So Sánh Hiệu Năng 3 Trạng Thái (Performance Comparison)

| Metric / Tín hiệu | Baseline | Corrupted | Repaired | Thay đổi do Corruption | Mức độ Phục hồi | Nhận xét |
| :--- | :---: | :---: | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | 1.0000 | 0.8000 | 1.0000 | -0.2000 | +0.2000 | Hit rate giảm mạnh khi dữ liệu bị lỗi, phục hồi hoàn toàn sau repair |
| `mean_token_f1` | 1.0000 | 0.7000 | 1.0000 | -0.3000 | +0.3000 | Chất lượng câu trả lời bị kéo sụt theo context truy xuất |
| `judge_accuracy` | 1.0000 | 0.7000 | 1.0000 | -0.3000 | +0.3000 | LLM Judge đánh giá độ chính xác phục hồi về mức chuẩn |
| `mean_judge_score` | 5.00 | 4.00 | 5.00 | -1.0000 | +1.0000 | Điểm ngữ nghĩa cải thiện rõ rệt sau khi tái tạo index |
| `Quality Checks (GX)` | PASS | FAIL | PASS | Vi phạm Expectation | Đã khắc phục | GX 1.x chặn đứng dữ liệu bẩn trước khi phục vụ |
| `Freshness SLA` | FRESH | STALE | FRESH | 28.6% stale | 0.0% stale | Cảnh báo dữ liệu cũ được giải quyết sau khi reload snapshot |

## 2. Chi Tiết Kiểm Định Chất Lượng (Great Expectations 1.x)

| Expectation Check | Corrupted Data | Repaired Data |
| :--- | :---: | :---: |
| `Row count (5 - 5000)` | PASS | PASS |
| `paper_id not null` | PASS | PASS |
| `title not null` | PASS | PASS |
| `text_for_embedding not null` | PASS | PASS |
| `paper_id unique` | FAIL | PASS |
| `summary >= 30 chars` | FAIL | PASS |

## 3. Chi Tiết Giám Sát Freshness SLA

| Thuộc tính Freshness | Corrupted Data | Repaired Data |
| :--- | :---: | :---: |
| Trạng thái SLA | **STALE** | **FRESH** |
| Số bài quá hạn | 6 / 21 | 0 / 24 |
| Tỷ lệ quá hạn | 28.6% | 0.0% |
| Bài mới nhất | 2026-08-26 | 2026-09-15 |
| Bài cũ nhất | 2025-06-15 | 2026-04-01 |

## 4. Phân Tích Nguyên Nhân & Cơ Chế Tự Phục Hồi (Causal Analysis)

1. **Tác động của Synthetic Corruption**:
   - Khi áp dụng 6 kịch bản làm bẩn dữ liệu (xóa bài mới nhất, xóa trắng summary, tiêm noise, cắt ngắn title, làm cũ published date, nhân bản dòng), hệ thống Data Observability lập tức phát hiện các bất thường.
   - Great Expectations 1.x bắt được lỗi trùng lặp `paper_id`, thiếu dữ liệu và độ dài tóm tắt không đạt chuẩn. Freshness SLA phát hiện tỷ lệ bài báo quá hạn vượt trần 25%.
   - Hậu quả dây chuyền: Các vector embedding bị sai lệch ngữ cảnh khiến chỉ số `retrieval_hit_rate` sụt giảm, dẫn đến việc LLM sinh câu trả lời sai lệch (`mean_token_f1` và `judge_accuracy` tụt dốc).

2. **Cơ chế Idempotent Self-Healing / Repair**:
   - Quá trình khôi phục thực hiện trực tiếp từ nguồn lưu trữ thô nguyên bản (`data/raw/crossref_records.json`), đảm bảo tính toàn vẹn (Data Lineage).
   - Pipeline làm sạch, tính toán lại `age_days` và tái tạo cấu trúc chuẩn `text_for_embedding` một cách đơn định (deterministic).
   - Sau khi cập nhật lại Vector Store, các bài kiểm tra chất lượng đều đạt `PASS`, đưa hiệu năng của RAG Agent phục hồi hoàn toàn tương đương trạng thái Baseline.
