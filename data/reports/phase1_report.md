# Báo Cáo Pha 1 — Baseline Pipeline & Observability

## 1. Nguồn Dữ Liệu (Source Summary)
- **Nguồn API**: Crossref REST API
- **Query Filter**: `agentic retrieval augmented generation large language model`
- **Số lượng raw records**: 24
- **Số lượng clean records**: 24

## 2. Chỉ Số Đánh Giá Baseline (Evaluation Metrics)
| Chỉ số (Metric) | Giá trị | Ý nghĩa |
| :--- | :--- | :--- |
| `retrieval_hit_rate` | **1.0000** | Tỷ lệ ngữ cảnh truy xuất đúng tài liệu chuẩn |
| `mean_token_f1` | **1.0000** | Độ trùng khớp từ vựng giữa câu trả lời và ground truth |
| `judge_accuracy` | **1.0000** | Độ chính xác câu trả lời theo LLM Judge |
| `mean_judge_score` | **5.00** / 5.0 | Điểm chất lượng trung bình theo thang điểm 5 |
| `samples` | 10 | Số lượng câu hỏi benchmark kiểm thử |

## 3. Kiểm Định Chất Lượng Dữ Liệu (Great Expectations 1.x)
- **Trạng thái kiểm định chung**: **PASS**
- **Tổng số dòng kiểm tra**: 24

| Tên Expectation / Check | Quy chuẩn kiểm tra | Kết quả |
| :--- | :--- | :--- |
| `row_count` | Số dòng nằm trong khoảng [5, 5000] | PASS |
| `paper_id_not_null` | Trường `paper_id` không được null | PASS |
| `title_not_null` | Trường `title` không được null | PASS |
| `text_for_embedding_not_null` | Trường `text_for_embedding` không được null | PASS |
| `paper_id_unique` | Giá trị `paper_id` phải duy nhất | PASS |
| `summary_min_length` | Độ dài tóm tắt bài báo >= 30 ký tự | PASS |

## 4. Giám Sát Freshness SLA
- **Trạng thái Freshness SLA**: **FRESH (Dat SLA)**
- **Ngưỡng quá hạn (SLA Threshold)**: 180 ngày (tối đa 25% bài quá hạn)
- **Số bài quá hạn (stale)**: 0 / 24
- **Tỷ lệ bài quá hạn (stale ratio)**: 0.0%
- **Ngày xuất bản mới nhất**: 2026-09-15
- **Ngày xuất bản cũ nhất**: 2026-04-01
