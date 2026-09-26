# Báo Cáo Cá Nhân - Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Trần Ngọc Khánh |
| MSSV | 2A202602923 |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | Nova |
| Vai trò chính | Corruption & Recovery Pipeline Owner |
| Repository | https://github.com/Dzzuy/K4-L3B-DAY10-Nova-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Synthetic corruption suite | `src/ingestion/corruption.py`, `corrupt_clean_dataframe()` | Baseline clean DataFrame | Corrupted CSV/JSON và `corruption_log.json` | Hoàn thành |
| Phase 2 orchestration | `src/pipelines/corruption_flow.py` | Baseline metrics, clean data, raw snapshot, test set | Corrupted/repaired index, metrics, quality và report | Hoàn thành |
| Corruption tests | `tests/test_corruption.py` | Synthetic 24-row DataFrame | 4 deterministic unit tests | Hoàn thành |
| CP4-CP5 evidence | `data/results/`, `data/quality/`, `data/reports/corruption_report.md` | Kết quả pipeline | Artifacts so sánh ba trạng thái | Hoàn thành |

Tôi không nhận ownership cho ingestion/cleaning, GX/reporting hoặc baseline evaluation. Các module đó lần lượt do Thanh, An và Duy phụ trách; phần của tôi tích hợp chúng theo interface chung.

### Hỗ trợ ngoài phạm vi chính

| Hoạt động | Module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Đồng bộ integration branch với `main` | Toàn pipeline | Nhận phiên bản baseline/reporting mới mà không ghi đè artifacts thành viên khác |
| Kiểm tra embedding contract | Cleaning -> corruption | Sửa thứ tự `Published`/`Categories`, test toàn chuỗi năm phần |
| Kiểm tra LLM judge | Evaluation | Phát hiện key cũ ghi đè `.env`, chạy lại và xác minh không fallback |
| End-to-end verification | Phase 2 | Chạy OpenAI judge thật, GX/Freshness và comparison report thành công |

## 3. Kết quả theo vai trò

| Nhiệm vụ | File/artifact | Kết quả | Cách xác minh |
| --- | --- | --- | --- |
| Tiêm sáu lỗi deterministic | `corruption.py`, `corruption_log.json` | Đủ 6 scenarios, 24 -> 21 rows | Đọc `scenario_count=6` và affected IDs |
| Đánh giá corrupted state | `corrupted_metrics.json`, `corrupted.json` | Hit rate 0.8; Quality Gate FAIL | Chạy corruption flow |
| Repair từ trusted raw | `papers_clean_repaired.*` | 24 rows, unique IDs, không stale | `repaired.json` PASS |
| Đánh giá repaired state | `repaired_metrics.json` | Toàn bộ metric trở về baseline | So sánh ba metrics files |
| Kiểm thử corruption | `tests/test_corruption.py` | 4 passed | `python -m pytest -q` |

Output tiêu biểu là `data/results/corruption_log.json`. File ghi row count trước/sau, đủ sáu scenario, affected count, danh sách DOI và before/after cho corruption theo field. Báo cáo cuối nằm tại `data/reports/corruption_report.md`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

RAG có thể vẫn chạy mà không phát exception khi dữ liệu bị thiếu, stale, duplicate hoặc nhiễu. Phần của tôi tạo sự cố có kiểm soát để quan sát cả quality signals lẫn mức giảm retrieval/answer, sau đó chứng minh dữ liệu có thể phục hồi từ nguồn raw đáng tin cậy thay vì vá trực tiếp corrupted output.

### Cách triển khai

`corrupt_clean_dataframe()` tạo deep copy để không thay đổi baseline. Hàm validate clean contract, sắp xếp theo ngày để xóa 20% bài mới nhất và dùng thứ tự `paper_id` để chọn record deterministic. Trên 24 baseline rows, flow xóa 5 rows, blank 3 summaries, thêm noise vào 3 summaries, cắt 3 titles còn 7 ký tự, lùi 6 publication dates đúng 365 ngày và duplicate 2 rows. Các cột `summary_chars`, `age_days` và `text_for_embedding` được cập nhật sau biến đổi. Log JSON ghi đủ tham số và affected IDs.

`corruption_flow.py` yêu cầu baseline clean data, raw records, test set và baseline metrics tồn tại. Flow lưu corrupted data, build `papers-corrupted`, đánh giá bằng test set baseline, chạy GX/Freshness; sau đó load lại raw records, cleaning lại với ngày tham chiếu suy ra từ baseline, build `papers-repaired`, đánh giá và gọi reporting của An. Repair không đọc corrupted rows nên không tích lũy lỗi qua các lần chạy.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Clean DataFrame có `paper_id`, title, summary, joined fields, dates, derived fields |
| Output | Corrupted DataFrame cùng schema và JSON log; repaired artifacts từ raw |
| Phụ thuộc | `cleaning.py`, `crossref.py`, `index.py`, `metrics.py`, `quality.py`, `reporting.py` |
| Module sử dụng output | Chroma index, evaluation, quality checks và comparison report |
| Error handling | DataFrame rỗng, thiếu cột, published/age_days lỗi, thiếu baseline artifacts |

### Cách xác minh

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe script\run_corruption_flow.py
Select-String -Path data\results\corrupted_answers.json,data\results\repaired_answers.json -Pattern "Fallback heuristic"
```

- **Kết quả mong đợi:** 4 tests pass; corrupted metrics/quality giảm; repaired trở về baseline; không dùng judge fallback.
- **Kết quả thực tế:** 4 passed; hit rate 1.0 -> 0.8 -> 1.0; GX PASS -> FAIL -> PASS; fallback matches bằng 0.
- **Artifacts:** `data/results/`, `data/quality/`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** Corruption phải tái lập để so sánh metrics và repair phải idempotent.
- **Phương án cân nhắc:** Chọn record ngẫu nhiên mỗi lần; hoặc chọn deterministic theo ngày và `paper_id`.
- **Phương án chọn:** Xóa theo published descending, chọn field corruption theo sorted `paper_id`, không dùng random.
- **Lý do:** Kết quả không phụ thuộc seed hoặc thứ tự DataFrame ngẫu nhiên; log và metric dễ đối chiếu; lỗi thực sự đến từ data change thay vì sample drift.
- **Bằng chứng:** Hai lần chạy tạo cùng SHA256 cho `papers_clean_repaired.json` và `repaired_metrics.json`; unit test deterministic pass.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng:** OpenAI trả HTTP 429 với `credit_balance_exhausted`; mọi judge result ghi `Fallback heuristic judge used because the LLM evaluator was unavailable.`
- **Tái hiện:** Gọi một prompt tối thiểu qua `build_llm()` và tìm chuỗi fallback trong answers JSON.
- **Nguyên nhân gốc:** Biến môi trường `OPENAI_API_KEY` cũ trong process ghi đè key mới trong `.env`; fingerprint của project và active key không trùng.
- **Cách xử lý:** Loại override cũ, buộc tiến trình đọc project `.env`, kiểm tra key bằng fingerprint đã che và chạy lại flow.
- **Xác minh:** Request tối thiểu thành công; `fallback_matches=0`; OpenAI reasoning xuất hiện trong 20 corrupted/repaired answers.
- **Điều học được:** Cần kiểm tra cấu hình hiệu lực, không chỉ nội dung `.env`; fallback không nên bị hiểu nhầm là LLM evaluation thật.

## 7. Hiểu biết về luồng end-to-end

1. Crossref payload được lưu nguyên bản để bảo toàn lineage, parse thành `PaperRecord`, làm sạch và tạo DataFrame có derived fields. `text_for_embedding` được MiniLM mã hóa và nạp vào ChromaDB cùng metadata.
2. Mỗi test case có câu hỏi, ground truth và `ground_truth_doc_ids`. Retrieval hit khi top-k chứa ID chuẩn; câu trả lời được so bằng token F1 và OpenAI structured judge.
3. GX kiểm tra volume, completeness, uniqueness và validity. Freshness đo timeliness riêng bằng `age_days > 180` và stale ratio tối đa 25%.
4. Ba trạng thái phải dùng cùng test set để khác biệt metrics phản ánh dataset/index, không phải câu hỏi thay đổi.
5. Repair thành công khi repaired data có 24 unique rows, Quality Gate/Freshness PASS/FRESH và retrieval/answer metrics trở lại baseline. Việc rebuild từ raw và output hash ổn định chứng minh lineage và idempotency.

## 8. Phân tích kết quả

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét |
| --- | ---: | ---: | ---: | --- |
| `retrieval_hit_rate` | 1.00 | 0.80 | 1.00 | Hai trên mười câu không retrieve được ground-truth doc sau corruption |
| `mean_token_f1` | 1.00 | 0.70 | 1.00 | Nội dung câu trả lời suy giảm rõ hơn retrieval hit rate |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 | OpenAI judge xác nhận ba câu materially incorrect |
| `mean_judge_score` | 5.00 | 4.00 | 5.00 | Corrupted answers vẫn có một phần đúng nên điểm giảm ít hơn accuracy |
| Quality Gate | PASS | FAIL | PASS | Duplicate và summary length bị phát hiện |
| Freshness | FRESH | STALE | FRESH | Stale ratio 0% -> 28.57% -> 0% |

Chuỗi nguyên nhân-bằng chứng:

1. Suite corruption làm mất 5 bài mới, phá summary/title/date và thêm duplicate -> uniqueness, summary length và freshness fail -> hit rate giảm 0.2, token F1/judge accuracy giảm 0.3.
2. Repair load lại raw snapshot và rebuild index -> 24 unique rows, 0 stale, quality pass -> tất cả retrieval/answer metrics trở lại baseline.

Không thể kết luận một corruption riêng lẻ ảnh hưởng mạnh nhất chỉ từ lần chạy hiện tại vì sáu lỗi được áp dụng đồng thời. Quan sát trực tiếp cho thấy drop latest liên quan đến retrieval miss, blank summary làm câu summary không có nội dung, và stale date đủ làm SLA fail; muốn xếp hạng ảnh hưởng cần chạy ablation từng scenario.

Kết quả khác kỳ vọng ban đầu là judge score corrupted vẫn đạt 4.0 dù judge accuracy chỉ 0.7. Lý do là các câu đúng vẫn đạt 5 và một số câu sai còn chứa thông tin liên quan; kiểm tra `corrupted_answers.json` xác nhận reasoning của OpenAI judge thay vì fallback.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Data lineage và immutable raw snapshot là điều kiện để repair đúng, thay vì che hoặc sửa chồng lỗi downstream.
2. Quality Gate và model metrics bổ sung cho nhau: GX bắt structural defects còn retrieval/judge cho biết tác động serving thực tế.
3. Reproducibility cần deterministic selection, cùng test set, cùng embedding contract và kiểm tra runtime config thực sự có hiệu lực.

### Nếu có thêm thời gian

Tôi sẽ tách sáu corruption thành sáu ablation runs, ghi metric delta riêng cho từng scenario và thêm pipeline integration tests sử dụng dependency fakes. Kết quả mong muốn là bảng xếp hạng mức ảnh hưởng, coverage >80% và CI chạy tự động trên Pull Request.

## 10. Cam kết của thành viên

- [x] Nội dung phản ánh đúng phần việc và mức hiểu của tôi.
- [x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [x] Mọi kết luận đều có artifact hoặc metric để đối chiếu.
- [x] Tôi không ghi thành công cho phần chưa kiểm chứng.
- [x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x] Báo cáo cá nhân không sao chép nguyên văn báo cáo nhóm.

**Họ và tên:** Trần Ngọc Khánh  
**Ngày xác nhận:** 2026-09-26
