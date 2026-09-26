# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin         | Nội dung                                                        |
| ------------------ | ---------------------------------------------------------------- |
| Họ và tên          | Võ Trường An                                                    |
| MSSV               | 2A202602656                                                     |
| Khóa/Lớp           | K4-L3B-DAY10                                                    |
| Tên nhóm           | Nova                                                            |
| Vai trò chính      | Data Observability & Reporting Owner                            |
| Repository         | K4-L3B-DAY10-Nova-DataPipelineDataObservability                 |
| Ngày hoàn thành    | 2026-09-26                                                      |

---

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| :--- | :--- | :--- | :--- | :--- |
| Data Observability Gate | `src/observability/quality.py`<br>- `run_data_quality_checks`<br>- `evaluate_freshness_sla`<br>- `build_freshness_report` | Clean / Corrupted / Repaired `pd.DataFrame`, `Settings` | `data/quality/*.json`<br>`data/quality/freshness_report.json`<br>dict `{"success": bool, ...}` | Hoàn thành |
| Observability Reporting | `src/observability/reporting.py`<br>- `generate_phase1_report`<br>- `generate_corruption_report` | `source_summary`, `metrics` dict, `quality` dict, `freshness` dict | `data/reports/phase1_report.md`<br>`data/reports/corruption_report.md` | Hoàn thành |

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| :--- | :--- | :--- |
| Đồng bộ schema dữ liệu làm sạch | Thanh (`src/ingestion/cleaning.py`) | Đảm bảo DataFrame đầu ra có đủ các cột `paper_id`, `title`, `summary`, `age_days`, `text_for_embedding` đúng kiểu để vượt qua Quality Gate. |
| Kết nối luồng báo cáo tự động | Duy (`phase1.py`) & Khánh (`corruption_flow.py`) | Cung cấp interface chuẩn của `run_data_quality_checks` và các hàm reporting để pipeline tự động xuất log JSON và markdown report. |

---

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| :--- | :--- | :--- | :--- |
| Cài đặt kiểm định Great Expectations 1.x | `src/observability/quality.py`<br>`run_data_quality_checks` | Bộ kiểm định 4 Expectations chạy in-memory qua Ephemeral Context, xuất log `data/quality/*.json`. | Chạy lệnh kiểm tra Checkpoint 1 in ra `Quality check status = True`. |
| Cài đặt giám sát Freshness SLA | `src/observability/quality.py`<br>`evaluate_freshness_sla` | Phát hiện chính xác các bài báo có `age_days > 180`, tính toán tỷ lệ quá hạn và gắn cờ cảnh báo SLA. | Chạy `evaluate_freshness_sla()` trên clean data (`is_fresh=True`) và corrupted data (`is_fresh=False`). |
| Tự động sinh báo cáo Baseline Pha 1 | `src/observability/reporting.py`<br>`generate_phase1_report` | Báo cáo Markdown `data/reports/phase1_report.md` tổng hợp nguồn dữ liệu, kết quả GX 1.x, Freshness SLA và baseline metrics. | File markdown được sinh tự động khi chạy baseline pipeline, định dạng bảng rõ ràng. |
| Tự động sinh báo cáo đối chiếu 3 trạng thái | `src/observability/reporting.py`<br>`generate_corruption_report` | Báo cáo Markdown `data/reports/corruption_report.md` so sánh chi tiết Baseline vs Corrupted vs Repaired kèm phân tích nhân quả. | Bảng so sánh 3 trạng thái hiển thị đầy đủ độ sụt giảm khi dính lỗi và độ phục hồi sau khi sửa chữa. |

**Output cụ thể chứng minh năng lực module:**
Hàm `run_data_quality_checks` chặn đứng 100% dữ liệu bẩn khi bị tiêm 6 kịch bản corruption (trùng ID, thiếu text embedding, summary quá ngắn, bài quá hạn) và trả về `success = False`, sau đó xác nhận dữ liệu đã hoàn toàn sạch sẽ sau bước Idempotent Repair với `success = True`.

---

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Trong một hệ thống RAG thực tế, dữ liệu từ các nguồn mở (như Crossref REST API) thường xuyên biến động hoặc có thể bị lỗi ngầm (Silent Data Corruption). Nếu không có chốt chặn kiểm dịch (Observability Gate):
1. Dữ liệu thiếu trường hoặc summary rỗng vẫn được đưa vào Vector Database, tạo ra các vector embedding vô nghĩa làm loãng không gian tìm kiếm.
2. Dữ liệu trùng lặp `paper_id` gây sai lệch điểm tương đồng và phân phối retrieval.
3. Dữ liệu quá hạn (stale data) khiến câu trả lời của AI bị lỗi thời so với thực tế.

Module Observability đóng vai trò là "người gác cổng", đảm bảo chỉ dữ liệu đạt chuẩn data contract mới được đưa vào bước Indexing.

### Cách triển khai

1. **Chuẩn Great Expectations 1.x Ephemeral Context:**
   - Thay vì sử dụng cấu hình file tĩnh cồng kềnh, code sử dụng chuẩn Ephemeral Context hiện đại của GX 1.x:
     ```python
     context = gx.get_context(mode="ephemeral")
     data_source = context.data_sources.add_pandas(name="papers_source")
     data_asset = data_source.add_dataframe_asset(name="papers_asset")
     batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
     batch = batch_def.get_batch(batch_parameters={"dataframe": df})
     ```
2. **4 Expectations bắt buộc:**
   - `ExpectTableRowCountToBeBetween(min_value=5, max_value=5000)`: Chặn dataset quá nhỏ hoặc phình to bất thường.
   - `ExpectColumnValuesToNotBeNull`: Áp dụng cho các cột cốt lõi `paper_id`, `title`, `text_for_embedding`.
   - `ExpectColumnValuesToBeUnique`: Đảm bảo `paper_id` là khóa chính duy nhất.
   - `ExpectColumnValueLengthsToBeBetween`: Đảm bảo `summary` có độ dài >= 30 ký tự để embedding có ngữ nghĩa tối thiểu.
3. **Freshness SLA Monitoring:**
   - Đọc cột `age_days` (hoặc tính hiệu giữa ngày hiện tại và ngày công bố `published`).
   - Ngưỡng SLA: `age_days > 180`. Nếu tỷ lệ bài cũ `stale_ratio > 25%`, hệ thống kích hoạt vi phạm SLA (`is_fresh = False`).
4. **Markdown Reporting Generator:**
   - Viết các hàm format dữ liệu tự động, tính độ lệch hiệu năng `_format_diff()` và xuất báo cáo markdown chuẩn bảng để coach dễ chấm.

### Input, output và contract

| Thành phần | Mô tả |
| :--- | :--- |
| **Input** | `df: pd.DataFrame` (chứa các trường clean metadata), `settings: Settings`, `stage: str` |
| **Output** | `dict` chứa `success: bool`, `passed: bool`, `checks: dict`, `freshness: dict`<br>File JSON tại `data/quality/{stage}.json` |
| **Module phụ thuộc** | `src/core/config.py` (cấu hình đường dẫn và ngưỡng SLA) |
| **Module sử dụng output** | `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py` |
| **Điều kiện lỗi cần xử lý** | DataFrame rỗng (`len(df) == 0`), thiếu cột trong schema, ngày tháng không hợp lệ (NaN/Coerce) |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print('Tín hiệu hoàn thành: Quality check status =', res['success'])"
```

- **Kết quả mong đợi:** In ra `Tín hiệu hoàn thành: Quality check status = True` và file `data/quality/test.json` được tạo.
- **Kết quả thực tế:** In đúng chuỗi `Tín hiệu hoàn thành: Quality check status = True`.
- **Artifact:** `data/quality/baseline_quality_report.json`, `data/quality/freshness_report.json`.

---

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Lựa chọn phương án triển khai Data Quality giữa việc tự viết logic kiểm tra bằng Pandas thuần vs Sử dụng Great Expectations cú pháp cũ (0.18.x) vs Sử dụng Great Expectations chuẩn mới 1.x.
- **Các phương án đã cân nhắc:**
  1. *Viết hàm validate bằng Pandas thuần:* Viết rất nhanh, code ngắn nhưng không chuẩn hóa, khó mở rộng khi tích hợp Data Catalog và không đúng với rubric bài lab.
  2. *Dùng Great Expectations theo cú pháp DataContext cũ:* Dễ dính warning deprecation và phát sinh lỗi runtime khi thư viện `great_expectations` trong môi trường là phiên bản 1.23.2.
  3. *Dùng Great Expectations 1.x Ephemeral Context:* Chuẩn chính thống của GX 1.x, không cần tạo thư mục cục bộ `gx/`, chạy hoàn toàn in-memory trực tiếp trên pandas DataFrame.
- **Phương án đã chọn:** Phương án 3 (Great Expectations 1.x Ephemeral Context).
- **Lý do:** Đáp ứng trọn vẹn tiêu chí Checkpoint 1 và Rubric bài lab (tránh bị trừ 10 điểm do dùng cú pháp cũ gây crash), đồng thời tốc độ thực thi nhanh và code gọn gàng, dễ bảo trì.
- **Bằng chứng:** Code chạy mượt mà trên môi trường ảo không phát sinh cảnh báo, vượt qua bài kiểm tra tự nghiệm thu chỉ trong ~1.3 giây.

---

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Khi chạy lệnh kiểm tra tự nghiệm thu của bài lab:
  `KeyError: 'success'`
- **Lệnh tái hiện:**
  ```bash
  python -c "...; res=run_data_quality_checks(df, s, 'test'); print(res['success'])"
  ```
- **Nguyên nhân gốc:** Khởi đầu hàm trả về dictionary có trường `"passed": all(checks.values())` nhưng tài liệu nghiệm thu của ban tổ chức lại truy cập vào thuộc tính `"success"`.
- **Cách xử lý:** Cập nhật dictionary trả về cung cấp cả 2 khóa `"success": passed` và `"passed": passed`, đồng thời bổ sung khóa `"gx_success"` để tách biệt rõ giữa kết quả kiểm tra schema (GX) và kiểm tra SLA (Freshness).
- **Cách xác minh sau khi sửa:** Chạy lại lệnh nghiệm thu, màn hình in ra chính xác `Tín hiệu hoàn thành: Quality check status = True`.
- **Điều học được:** Khi phát triển module trong một team, Data Contract giữa các hàm (API Specification) phải được tuân thủ tuyệt đối theo checklist nghiệm thu.

---

## 7. Hiểu biết về luồng end-to-end

1. **Dữ liệu đi từ Crossref đến vector index như thế nào?**
   Dữ liệu thô JSON được tải từ Crossref API (hoặc fallback snapshot local) -> lưu trữ nguyên vẹn tại `data/raw/` (Data Lineage) -> module Cleaning chuẩn hóa text, loại bỏ thẻ JATS XML, tính toán `age_days` và ghép chuỗi chuẩn `text_for_embedding` -> đi qua chốt kiểm định Great Expectations 1.x -> nạp vào ChromaDB để tính vector embedding (model `all-MiniLM-L6-v2`) và lưu trữ vector index.

2. **Evaluation set và ground-truth document IDs dùng để đo retrieval/answer quality ra sao?**
   Bộ test set 10 câu hỏi bao phủ 4 dạng nghiệp vụ (`summary`, `authors`, `date`, `categories`). Khi truy vấn, `retrieval_hit_rate` được tính bằng cách kiểm tra xem ID tài liệu được truy xuất có nằm trong `ground_truth_doc_ids` hay không. Sau đó, LLM sinh câu trả lời dựa trên context và được chấm điểm qua `mean_token_f1` (độ trùng từ vựng) và LLM Judge (`judge_accuracy`, `mean_judge_score`).

3. **Quality checks khác freshness monitoring ở điểm nào trong bài lab?**
   - *Quality checks (GX 1.x)*: Kiểm tra tính toàn vẹn tĩnh của cấu trúc dữ liệu (tồn tại cột, không null, số lượng dòng, tính duy nhất của ID, độ dài tối thiểu của văn bản).
   - *Freshness monitoring*: Kiểm tra tính thời sự, kịp thời của dữ liệu theo thời gian thực (đo lường độ cũ của tri thức). Dữ liệu có thể rất sạch về mặt schema nhưng vẫn vi phạm SLA nếu là các bài báo xuất bản quá lâu trước đây.

4. **Vì sao phải dùng cùng test set cho baseline, corrupted và repaired?**
   Đây là nguyên tắc đối chứng khoa học (Controlled Experiment). Muốn kết luận được sự suy giảm hiệu năng do dữ liệu bẩn và sự phục hồi do repair, thước đo (test set) phải được giữ cố định. Nếu thay đổi câu hỏi kiểm thử giữa các trạng thái, sự thay đổi điểm số có thể do độ khó câu hỏi chứ không phản ánh đúng chất lượng dữ liệu.

5. **Repair được xem là thành công dựa trên artifact và metric nào?**
   - Về dữ liệu: Các file `papers_clean_repaired.csv/json` được tái tạo từ nguồn raw tin cậy, vượt qua toàn bộ 4 expectations của GX 1.x và Freshness SLA (`success = True`).
   - Về hiệu năng AI: Bảng đối chiếu trong `data/reports/corruption_report.md` và `repaired_metrics.json` chứng minh `retrieval_hit_rate` và `mean_token_f1` hồi phục về mức ngang bằng hoặc xấp xỉ trạng thái Baseline.

---

## 8. Phân tích kết quả

### Metrics chính (Dữ liệu thử nghiệm thực tế)

| Metric / Tín hiệu | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| :--- | :---: | :---: | :---: | :--- |
| `retrieval_hit_rate` | 1.0000 | 0.4000 | 1.0000 | Hit rate sụt giảm mạnh (-0.6) khi bị corrupt và phục hồi nguyên vẹn sau repair |
| `mean_token_f1` | 0.8542 | 0.2500 | 0.8542 | Khả năng trả lời đúng từ khóa giảm sâu khi embedding bị nhiễu và thiếu context |
| `judge_accuracy` | 0.9000 | 0.3000 | 0.9000 | LLM Judge đánh giá tỷ lệ trả lời đúng giảm tới 60% khi dính dữ liệu lỗi |
| `mean_judge_score` | 4.60 | 1.80 | 4.60 | Điểm trung bình trượt từ mức Xuất sắc (4.6) xuống mức Kém (1.8) |
| Quality checks (GX) | PASS | FAIL | PASS | Bắt trúng lỗi schema vi phạm (trùng lặp ID, summary ngắn) |
| Freshness status | FRESH | STALE | FRESH | Cảnh báo kịp thời khi bài báo bị lùi ngày xuất bản > 180 ngày |

### Kết luận từ số liệu

1. **Chuỗi nhân quả 1 (Tác động của Corruption):**
   Tiêm dữ liệu bẩn (Blank summary, noise, truncate) → Great Expectations báo `summary_min_length` FAIL, Freshness SLA báo STALE → Vector embeddings bị méo ngữ cảnh → `retrieval_hit_rate` sụp đổ từ 1.0 xuống 0.4, kéo theo `mean_token_f1` giảm xuống 0.25.
2. **Chuỗi nhân quả 2 (Cơ chế Repair):**
   Khôi phục idempotent từ snapshot thô `crossref_records.json` → Tái tạo sạch sẽ `text_for_embedding` và `age_days` → Quality checks và Freshness hồi phục 100% PASS → Vector store được index lại đưa `retrieval_hit_rate` hồi phục về 1.0.

- **Kịch bản corruption ảnh hưởng rõ nhất:**
  Kịch bản *Blank summary* và *Inject noise* ảnh hưởng nặng nề nhất đến vector search vì nó trực tiếp phá hủy nội dung của trường `text_for_embedding`, khiến vector index không thể tìm ra bài báo phù hợp cho câu hỏi.

---

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. **Về Data Pipeline:** Pipeline phải luôn được thiết kế theo cơ chế **Idempotent** và bảo toàn bản ghi thô (Data Lineage) để khi xảy ra lỗi luôn có khả năng tua lại (replay) và sửa chữa an toàn.
2. **Về Data Observability:** Data Observability không chỉ là kiểm tra kiểu dữ liệu mà cần bao gồm cả kiểm tra tính phân phối (Distribution), tính duy nhất (Uniqueness) và độ tươi mới (Freshness SLA) để ngăn chặn Silent Failure.
3. **Về RAG System:** "Garbage in, garbage out" là sự thật tuyệt đối trong RAG. Chất lượng retrieval và generation phụ thuộc hoàn toàn vào độ sạch và tính đầy đủ của trường ngữ cảnh được dùng để nhúng vector.

### Nếu có thêm thời gian

Tôi sẽ xây dựng một Web Dashboard đơn giản bằng Streamlit hiển thị trực quan trạng thái Data Observability theo thời gian thực (real-time drift monitor) để đạt thêm điểm Bonus B1 (+5 điểm) theo tiêu chí của môn học.

---

## 10. Cam kết của thành viên

Đánh dấu sau khi tự kiểm tra:

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Võ Trường An  
**Ngày xác nhận:** 2026-09-26  
