# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin       | Nội dung                                                                     |
| --------------- | ---------------------------------------------------------------------------- |
| Họ và tên       | Nguyễn Hữu Thành                                                             |
| MSSV            | 2A202602807                                                                  |
| Khóa/Lớp        | K4-L3B                                                                       |
| Tên nhóm        | Nova                                                                         |
| Vai trò chính   | Data ingestion & cleaning owner                                              |
| Repository      | https://github.com/Dzzuy/K4-L3B-DAY10-Nova-DataPipelineDataObservability.git |
| Ngày hoàn thành | 2026-09-26                                                                   |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable                  | File/hàm phụ trách                                                                                | Input nhận vào                              | Output bàn giao                                                     | Trạng thái |
| ----------------------------------- | ------------------------------------------------------------------------------------------------- | ------------------------------------------- | ------------------------------------------------------------------- | ---------- |
| Thu thập và chuẩn hóa dữ liệu nguồn | `src/ingestion/crossref.py`: `parse_crossref_payload`, `fetch_source_records`, `load_raw_records` | Crossref REST API hoặc snapshot JSON cục bộ | `data/raw/crossref_response.json`, `data/raw/crossref_records.json` | Hoàn thành |
| Làm sạch và mô hình hóa dữ liệu     | `src/ingestion/cleaning.py`: `build_clean_dataframe`                                              | Danh sách `PaperRecord` và `run_date`       | `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`       | Hoàn thành |

Hai module trên tạo data contract đầu vào cho các bước embedding/index, evaluation và observability. Phạm vi tôi trực tiếp thực hiện được ghi nhận trong commit `80dd2fe` (`ingestion and cleaning`).

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện                                               | File/hàm/artifact liên quan                                                            | Kết quả bàn giao                                                                         | Cách xác minh                                                       |
| ------------------------------------------------------------------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| Gọi Crossref, retry khi lỗi tạm thời và fallback về snapshot cục bộ | `src/ingestion/crossref.py`, `data/raw/crossref_response.json`                         | Response đầy đủ gồm 24 items được lưu làm lineage anchor                                 | Đọc `message.items` trong raw response; kiểm tra `len(items) == 24` |
| Parse metadata thành `PaperRecord`                                  | `parse_crossref_payload`, `data/raw/crossref_records.json`                             | 24 records có DOI, title, summary sạch, authors, categories và ngày xuất bản             | Nạp bằng `load_raw_records`; đối chiếu số records và schema         |
| Chuẩn hóa dữ liệu và tạo văn bản embedding                          | `build_clean_dataframe`, `data/clean/papers_clean.csv`, `data/clean/papers_clean.json` | 24 dòng, 16 cột; 24 `paper_id` duy nhất; không thiếu trường bắt buộc; không còn thẻ JATS | Chạy lệnh kiểm tra ở mục 4 và đối chiếu hai artifact clean          |
| Bổ sung category khi Crossref không cung cấp `subject`              | `_crossref_categories`                                                                 | Category phân bố: 15 `Journal Article`, 8 `Posted Content`, 1 `Report`                   | Kiểm tra `categories_joined.value_counts()`                         |

Output cụ thể của phần việc là bộ dữ liệu clean 24 dòng. CSV và JSON có cùng schema, cùng thứ tự `paper_id`, không có DOI trùng, và mỗi `text_for_embedding` có đúng thứ tự `Title`, `Authors`, `Published`, `Categories`, `Summary`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu Crossref có cấu trúc lồng nhau, một số publisher bỏ trống `subject`, ngày tháng có thể chỉ có năm hoặc năm-tháng, abstract chứa thẻ JATS/XML và API có thể gặp lỗi mạng hoặc rate limit. Pipeline cần chuyển response này thành dữ liệu có schema ổn định, dễ truy vết và đủ sạch để đưa vào mô hình embedding.

### Cách triển khai

Ở bước ingestion, tôi kiểm tra cấu trúc `message.items`, chuẩn hóa DOI về chữ thường, lấy title đầu tiên, ghép tên tác giả, bóc thẻ JATS khỏi abstract và chuyển `date-parts` về ISO `YYYY-MM-DD`. Bản ghi thiếu DOI, title, summary hoặc ngày xuất bản bị loại vì không đủ điều kiện phục vụ retrieval/evaluation. Category ưu tiên `subject`; nếu nguồn không cung cấp thì dùng Crossref work `type`, cuối cùng mới dùng `Uncategorized`.

Hàm fetch gọi Crossref với timeout, thử tối đa 3 lần cho lỗi `429` và `5xx`, tôn trọng `Retry-After` có giới hạn và dùng exponential backoff. Nếu vẫn thất bại, hàm đọc snapshot cục bộ. Response đầy đủ và records sau parse được lưu riêng để bảo toàn data lineage.

Ở bước cleaning, chuỗi và danh sách được chuẩn hóa khoảng trắng, HTML entity và phần tử trùng. `published`/`updated` được parse theo UTC; `age_days` là số ngày từ ngày xuất bản đến `run_date`. Các bản ghi thiếu trường tối thiểu bị bỏ, DOI trùng được giữ bản đầu tiên, rồi dữ liệu được sắp theo ngày xuất bản giảm dần. `text_for_embedding` được ghép theo định dạng:

```text
Title: <title>
Authors: <authors_joined>
Published: <published>
Categories: <categories_joined>
Summary: <summary>
```

### Input, output và contract

| Thành phần              | Mô tả                                                                                                     |
| ----------------------- | --------------------------------------------------------------------------------------------------------- |
| Input                   | Crossref JSON có `message.items`; hoặc danh sách `PaperRecord`; `run_date` kiểu `datetime`                |
| Output                  | Raw JSON, parsed-record JSON và DataFrame clean 16 cột                                                    |
| Module phụ thuộc        | `src/core/config.py`, `src/core/utils.py`, Crossref REST API                                              |
| Module sử dụng output   | Embedding/index, evaluation set, quality/freshness và corruption/repair                                   |
| Điều kiện lỗi cần xử lý | Mạng/429/5xx, payload sai schema, metadata thiếu, JATS/XML, ngày không hợp lệ, category rỗng và DOI trùng |

### Cách xác minh

```powershell
$env:PYTHONPATH="src"
.\.venv\Scripts\python.exe -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(len(df), df.paper_id.nunique(), df.paper_id.duplicated().sum())"
```

- **Kết quả mong đợi:** 24 dòng clean, 24 DOI duy nhất và 0 DOI trùng.
- **Kết quả thực tế:** `24 24 0`; không thiếu `paper_id`, `title`, `summary`, `published`; không còn thẻ JATS; `age_days` nằm trong khoảng 11–178 tại ngày chạy 2026-09-26.
- **Artifact/log:** `data/raw/crossref_response.json`, `data/raw/crossref_records.json`, `data/clean/papers_clean.csv`, `data/clean/papers_clean.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Cả 24 items của lần lấy dữ liệu hiện tại đều không có `subject`, khiến `categories` rỗng và làm giảm chất lượng context embedding.
- **Các phương án đã cân nhắc:** (1) giữ category rỗng đúng như nguồn; (2) suy đoán category từ title/abstract bằng keyword hoặc LLM; (3) fallback sang trường `type` có kiểm soát của Crossref.
- **Phương án đã chọn:** Ưu tiên `subject`, nếu thiếu thì chuyển `type` thành nhãn dễ đọc; chỉ dùng `Uncategorized` nếu cả hai đều thiếu.
- **Lý do:** Giữ được nguồn gốc dữ liệu, kết quả xác định và tái lập được, không phát sinh chi phí hay category do mô hình tự suy đoán. Hạn chế là `type` chỉ thể hiện loại tài liệu, không chi tiết như lĩnh vực học thuật.
- **Bằng chứng quyết định phù hợp:** 24/24 dòng clean có category; phân bố gồm 15 `Journal Article`, 8 `Posted Content` và 1 `Report`, trong khi raw response có 0 item chứa `subject`.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** Trường `categories` trong `crossref_records.json` và `categories_joined` trong clean dataset bị rỗng dù các bản ghi khác đầy đủ.
- **Lệnh hoặc bước tái hiện:** Kiểm tra `subject` trên toàn bộ `data/raw/crossref_response.json` và đếm số category rỗng sau parse.
- **Nguyên nhân gốc:** Crossref không bắt buộc publisher cung cấp `subject`; response hiện tại không có `subject` ở cả 24 items. Đây không phải lỗi đọc Unicode hay lỗi serialize JSON.
- **Cách xử lý:** Thêm `_crossref_categories`: lấy `subject` khi có, nếu không lấy `type` và chuẩn hóa dấu gạch nối/chữ hoa; sau đó crawl/parse và tạo lại dữ liệu clean.
- **Cách xác minh sau khi sửa:** `categories_joined` không còn rỗng; CSV và JSON clean cùng 24 DOI và cùng giá trị category.
- **Điều học được:** Cần phân biệt trường “không có trong source” với lỗi parser; fallback phải có nguồn gốc rõ ràng và không nên giả lập lĩnh vực chuyên môn khi chưa có bằng chứng.

## 7. Hiểu biết về luồng end-to-end

1. Crossref trả JSON metadata. Pipeline lưu nguyên response, parse thành `PaperRecord`, làm sạch và ghép `text_for_embedding`. Embedding model biến mỗi văn bản thành vector; vector cùng `paper_id` và metadata được ghi vào ChromaDB để truy hồi.
2. Evaluation set chứa câu hỏi, đáp án tham chiếu và ground-truth document IDs. Với mỗi câu hỏi, hệ thống kiểm tra `paper_id` đúng có xuất hiện trong top-k hay không để tính retrieval hit rate; câu trả lời sinh ra được so với đáp án tham chiếu bằng token F1 và judge metrics.
3. Quality checks đo cấu trúc/nội dung hiện tại như completeness, validity, uniqueness và độ dài summary. Freshness monitoring đo yếu tố thời gian, ví dụ tuổi dữ liệu hoặc lần cập nhật gần nhất so với ngưỡng cho phép. Dữ liệu có thể hợp lệ nhưng vẫn stale.
4. Baseline, corrupted và repaired phải dùng cùng test set để giữ nguyên độ khó và ground truth. Nếu thay test set, thay đổi metric có thể đến từ bộ câu hỏi chứ không phải corruption hay repair.
5. Repair chỉ được xem là thành công khi dữ liệu được phục hồi từ raw/baseline đáng tin cậy, quality/freshness signals trở lại mức mong đợi, index được build lại và agent metrics được đánh giá lại trên đúng test set cũ. Artifact cần đối chiếu gồm repaired clean data, repaired embeddings/index, quality report, repaired metrics và comparison report.

## 8. Phân tích kết quả

### Metrics chính

Số liệu lấy từ lần chạy end-to-end của nhóm (corruption flow do Khánh chạy, OpenAI judge thật, không fallback); metrics đã được tôi đối chiếu với `corrupted_metrics.json` và `repaired_metrics.json`. Artifacts: `data/results/baseline_metrics.json`, `data/results/corrupted_metrics.json`, `data/results/repaired_metrics.json`, `data/quality/`, `data/reports/corruption_report.md`.

| Metric/signal        | Baseline | Corrupted | Repaired | Nhận xét của cá nhân                                                                                            |
| -------------------- | -------: | --------: | -------: | --------------------------------------------------------------------------------------------------------------- |
| `retrieval_hit_rate` |     1.00 |      0.80 |     1.00 | 2/10 câu không retrieve được ground-truth doc; một phần do 5 bài mới nhất bị xóa khỏi dataset                   |
| `mean_token_f1`      |     1.00 |      0.70 |     1.00 | Giảm mạnh hơn hit rate (0.3 so với 0.2): có câu retrieve đúng doc nhưng nội dung doc đã bị hỏng nên trả lời sai |
| `judge_accuracy`     |     1.00 |      0.70 |     1.00 | 3/10 câu bị judge đánh giá materially incorrect                                                                 |
| `mean_judge_score`   |     5.00 |      4.00 |     5.00 | Giảm ít hơn accuracy vì các câu sai vẫn chứa một phần thông tin liên quan                                       |
| Quality checks (GX)  |     PASS |      FAIL |     PASS | Bắt được duplicate `paper_id` và summary quá ngắn                                                               |
| Freshness status     |    FRESH |     STALE |    FRESH | Stale ratio 0% → 28.57% → 0% (ngưỡng 25%, `age_days > 180`)                                                     |

### Kết luận từ số liệu

1. **Corruption → signal → metric:** Suite corruption (24 → 21 rows) xóa 5 bài mới, blank/noise summary, cắt title, lùi 6 ngày xuất bản 365 ngày và thêm 2 dòng duplicate → GX FAIL (uniqueness, summary length) và Freshness STALE (28.57%) → `retrieval_hit_rate` giảm 0.2, `mean_token_f1` và `judge_accuracy` giảm 0.3.
2. **Repair → signal phục hồi → metric phục hồi:** Repair không vá corrupted output mà load lại `data/raw/crossref_records.json` và chạy lại `build_clean_dataframe()` của module cleaning tôi phụ trách → 24 unique rows, 0 stale, GX PASS → toàn bộ metrics trở lại baseline.

Góc nhìn từ phần tôi phụ trách: repair chỉ phục hồi được đúng 100% vì raw snapshot được giữ nguyên vẹn và cleaning là hàm xác định (cùng raw + cùng ngày tham chiếu → cùng output). Nếu cleaning ghi đè raw hoặc phụ thuộc trạng thái trước đó, repair sẽ mang theo lỗi từ lần chạy corrupted.

Về corruption ảnh hưởng mạnh nhất: vì sáu lỗi được tiêm đồng thời trong một lần chạy, tôi không xếp hạng được mức ảnh hưởng của từng lỗi. Số liệu chỉ cho thấy answer quality giảm nhiều hơn retrieval (`judge_accuracy` 0.7 < `retrieval_hit_rate` 0.8, nên ít nhất một câu retrieve đúng doc vẫn trả lời sai). Theo quan sát của Khánh, drop latest gắn với retrieval miss còn blank summary làm câu hỏi dạng summary mất nội dung; điều này hợp lý vì `summary` vừa nằm trong `text_for_embedding` vừa là nguồn để trả lời. Muốn khẳng định cần chạy ablation từng scenario.

Kết quả khác kỳ vọng ban đầu ở phần của tôi: Crossref không trả `subject` cho truy vấn này, nên category rỗng ở 24/24 bản ghi. Tôi kiểm tra raw payload để loại trừ lỗi parser, sau đó fallback sang `type` để category đủ 24/24. Vì repair chạy lại cùng hàm cleaning trên cùng raw snapshot, fallback này được áp dụng nhất quán ở cả baseline và repaired; tuy nhiên chưa có ablation riêng để đo ảnh hưởng của nó lên retrieval.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Raw preservation và document identity ổn định rất quan trọng: có response gốc và DOI giúp chạy lại cleaning, audit và repair mà không phụ thuộc lần gọi API mới.
2. Data quality cần được đo theo nhiều chiều. Một bản ghi có thể đủ DOI/title/summary nhưng vẫn thiếu metadata chuyên ngành; fallback phải minh bạch và có giới hạn.
3. Chất lượng dữ liệu đầu vào tác động trực tiếp đến retrieval: nội dung thiếu, trùng DOI hoặc context embedding sai định dạng đều có thể làm vector/index sai trước khi LLM được gọi.

### Nếu có thêm thời gian

Tôi sẽ bổ sung trường phân biệt `category_source` (`subject`, `type_fallback`, `uncategorized`) và quality check riêng cho tỷ lệ category thực sự đến từ `subject`. Sau đó chạy A/B cùng một evaluation set giữa dữ liệu dùng `type` fallback và dữ liệu có subject/subject được enrichment; đo thay đổi của retrieval hit rate và mean token F1 để xác định fallback có cải thiện RAG thực sự hay chỉ cải thiện completeness hình thức.

## 10. Cam kết của thành viên

- [x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Hữu Thành  
**Ngày xác nhận:** 2026-09-26
