# Báo Cáo Nhóm - Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4-L3B |
| Tên nhóm | Nova |
| Repository | https://github.com/Dzzuy/K4-L3B-DAY10-Nova-DataPipelineDataObservability |
| Ngày hoàn thành | 2026-09-26 |

### Thành viên và phân công

| STT | Thành viên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Hữu Thành | 2A202602807 | Data Ingestion & Cleaning Owner | `crossref.py`, `cleaning.py`, raw/clean artifacts |
| 2 | Võ Trường An | 2A202602656 | Data Observability & Reporting Owner | `quality.py`, `reporting.py`, quality/freshness reports |
| 3 | Phạm Đình Duy | 2A202602913 | Evaluation & Baseline Pipeline Owner | `testset.py`, `phase1.py`, baseline metrics |
| 4 | Trần Ngọc Khánh | 2A202602923 | Corruption & Recovery Pipeline Owner | `corruption.py`, `corruption_flow.py`, CP4-CP5 artifacts |

Phân công trên bám theo kế hoạch trong `Lab 10.md`: mỗi thành viên sở hữu một deliverable end-to-end, khối lượng dự kiến xấp xỉ 25%. Thông tin thành viên và phạm vi ownership được đối chiếu từ ba báo cáo cá nhân `individual_2A202602807_NguyenHuuThanh.md`, `individual_2A202602656_VoTruongAn.md`, `individual_2A202602913_PhamDinhDuy.md` và báo cáo của Khánh trong repository.

## 2. Tóm tắt kết quả

Nhóm đã hoàn thiện pipeline RAG từ dữ liệu Crossref đến làm sạch, embedding MiniLM, lập chỉ mục ChromaDB, đánh giá trên bộ 10 câu hỏi, kiểm tra chất lượng bằng Great Expectations 1.x, giám sát freshness, tiêm lỗi và phục hồi. Baseline bảo toàn đủ 24 raw records thành 24 clean records có `paper_id` duy nhất, `age_days` và `text_for_embedding`; Quality Gate và Freshness SLA đều đạt. Bộ test cố định gồm bốn loại câu hỏi `summary`, `authors`, `date`, `categories`. Baseline đạt retrieval hit rate, token F1 và judge accuracy bằng 1.0.

Pha corruption áp dụng đồng thời sáu kịch bản: xóa 20% bài mới nhất, làm rỗng summary, chèn noise, cắt title, lùi ngày 365 ngày và tạo duplicate. Dataset sau lỗi còn 21 dòng; GX phát hiện duplicate và summary quá ngắn, còn Freshness SLA phát hiện 6/21 dòng stale, tương đương 28.57%. Retrieval hit rate giảm còn 0.8, token F1 và judge accuracy còn 0.7. Repair xây lại dữ liệu từ raw snapshot đáng tin cậy, khôi phục 24 dòng, Quality Gate/Freshness đều đạt và toàn bộ metrics trở về baseline. Ragas chưa chạy do chi phí/thời gian; vì corruption được áp dụng theo suite, chưa có ablation để quy riêng mức giảm metric cho từng loại lỗi.

## 3. Kiến trúc và luồng dữ liệu

```text
Crossref API / local raw snapshot
    -> crossref_response.json + crossref_records.json
    -> normalize, validate, deduplicate, calculate age_days
    -> papers_clean.csv/json
    -> MiniLM embeddings + ChromaDB papers-baseline
    -> fixed 10-question evaluation
    -> GX quality checks + Freshness SLA + baseline report
    -> deterministic six-scenario corruption
    -> papers-corrupted + corrupted evaluation/quality
    -> rebuild clean data from trusted raw records
    -> papers-repaired + repaired evaluation/quality
    -> three-state comparison report
```

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref `/works` hoặc snapshot | Retry tối đa 3 lần, fallback local, parse DOI/metadata | `data/raw/crossref_*.json` | Nguyễn Hữu Thành |
| Cleaning | `PaperRecord` | Chuẩn hóa text/list/date, deduplicate, tính derived fields | `data/clean/papers_clean.*` | Nguyễn Hữu Thành |
| Embedding/index | Clean DataFrame | MiniLM normalized vectors, cosine ChromaDB | `data/embeddings/`, `data/chroma/` | Phạm Đình Duy xác minh |
| Evaluation | Index + test set | Deterministic benchmark, retrieval hit, token F1, LLM judge | `data/results/*metrics.json` | Phạm Đình Duy |
| Observability | DataFrame theo từng trạng thái | GX 1.x Ephemeral Context, expectations và Freshness SLA | `data/quality/` | Võ Trường An |
| Corruption/repair | Baseline clean + trusted raw | Tiêm 6 lỗi, re-index, repair idempotent | Corrupted/repaired data, log và metrics | Khánh |
| Reporting | Metrics + quality/freshness artifacts | Tổng hợp Markdown và metric deltas từ kết quả thật | `data/reports/*.md` | Võ Trường An |

## 4. Cách tái hiện kết quả

### Cấu hình

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `openai` |
| `LLM_MODEL` | `gpt-4o-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | 180 ngày; fail khi stale ratio > 25% |
| Corruption selection | Deterministic theo `paper_id`, không dùng random |

API key chỉ nằm trong `.env`, không xuất hiện trong source hoặc báo cáo.

### Cài đặt và chạy

```bash
python -m venv .venv
./.venv/Scripts/python -m pip install -e ".[dev]"
./.venv/Scripts/python script/run_phase1.py
./.venv/Scripts/python script/run_corruption_flow.py
./.venv/Scripts/python -m pytest -q
```

| Lệnh | Trạng thái | Lần xác minh | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công | 2026-09-26 | `phase1_report.md`, `baseline_metrics.json` |
| Corruption flow | Thành công | 2026-09-26 | `corruption_report.md`, corruption/repaired artifacts |
| Pytest | 4 passed | 2026-09-26 | `tests/test_corruption.py` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Endpoint | `https://api.crossref.org/works` |
| Query | `agentic retrieval augmented generation large language model` |
| Giới hạn | 24 records, có abstract |
| Snapshot được đánh giá | 24 raw records, ngày chạy 2026-09-26 |
| Retry/fallback | 3 lần cho lỗi mạng/429/5xx; backoff và fallback local snapshot |
| Category fallback | Ưu tiên Crossref `subject`; nếu thiếu dùng work `type` có kiểm soát |

### Raw và clean schema chính

| Trường | Kiểu | Bắt buộc | Ý nghĩa/xử lý lỗi |
| --- | --- | --- | --- |
| `paper_id` | string | Có | DOI/document identity; record thiếu bị loại; deduplicate |
| `title` | string | Có | Chuẩn hóa HTML và whitespace; record rỗng bị loại |
| `summary` | string | Có | Loại JATS/HTML; record rỗng bị loại; GX yêu cầu >= 30 ký tự |
| `authors`, `categories` | list[string] | Không | Làm sạch, loại phần tử rỗng/trùng, ghép thành helper fields |
| `published`, `updated` | ISO date | Published có | Parse UTC; published lỗi làm record bị loại |
| `age_days` | integer | Có sau cleaning | Số ngày từ published đến ngày chạy chuẩn hóa |
| `text_for_embedding` | string | Có sau cleaning | Năm phần: title, authors, published, categories, summary |

Kết quả thực tế: 24 raw records tạo 24 clean rows với 16 cột, không có duplicate `paper_id`; `age_days` nằm trong khoảng 11-178. Vì cả 24 Crossref items không cung cấp `subject`, fallback minh bạch sang `type` tạo phân bố 15 `Journal Article`, 8 `Posted Content` và 1 `Report`. Cách này tránh suy đoán category bằng keyword/LLM nhưng vẫn bảo toàn completeness. Document ID trong Chroma dùng `paper_id` kết hợp vị trí dòng để vẫn quan sát được duplicate trong corrupted state.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| Phân bố loại câu hỏi | 3 summary, 3 authors, 2 date, 2 categories |
| Cách chọn papers | 10 vị trí trải đều trên clean DataFrame, deterministic |
| Ground truth ID | DOI từ `paper_id` của clean row được chọn |
| Embedding | `all-MiniLM-L6-v2`, normalized embeddings |
| Vector store | ChromaDB cosine; `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval | `top_k=4` |
| LLM judge | OpenAI `gpt-4o-mini`, structured score 1-5 |
| Test set dùng chung | `data/eval/test_set.json` |

Cùng một test set được dùng cho cả ba trạng thái để metric chỉ phản ánh thay đổi dữ liệu/index, không bị nhiễu do thay đổi câu hỏi hoặc ground truth. `build_test_set()` dừng nếu clean data có dưới 10 rows hoặc thiếu sáu cột bắt buộc; mỗi câu lưu `ground_truth_doc_ids`. Lần chạy cuối đã xác minh không có `Fallback heuristic` trong corrupted/repaired answers. Ragas được bỏ qua vì `RUN_RAGAS` chưa bật.

## 7. Kết quả baseline

| Artifact | Đường dẫn | Trạng thái |
| --- | --- | --- |
| Raw response/records | `data/raw/` | Có, 24 records |
| Cleaned dataset | `data/clean/papers_clean.*` | Có, 24 rows |
| Embedding/index | `data/embeddings/`, `data/chroma/` | Có khi chạy local |
| Evaluation set | `data/eval/test_set.json` | Có, 10 câu |
| Baseline metrics/answers | `data/results/baseline_*` | Có |
| Baseline report | `data/reports/phase1_report.md` | Có |

| Metric | Giá trị | Diễn giải |
| --- | ---: | --- |
| `retrieval_hit_rate` | 1.0000 | Cả 10 câu đều retrieve được ground-truth document trong top-k |
| `mean_token_f1` | 1.0000 | Câu trả lời deterministic khớp ground truth |
| `judge_accuracy` | 1.0000 | OpenAI judge đánh giá đúng cả 10 câu |
| `mean_judge_score` | 5.00 | Điểm trung bình tối đa |
| Ragas | N/A | Chưa bật `RUN_RAGAS=1` |

## 8. Data quality và freshness

| Check | Dimension | Kỳ vọng | Baseline |
| --- | --- | --- | --- |
| Row count | Volume | 5-5000 | PASS, 24 |
| `paper_id` not null/unique | Completeness/Uniqueness | 100% non-null và unique | PASS |
| `title` not null | Completeness | 100% non-null | PASS |
| `text_for_embedding` not null | Completeness | 100% non-null | PASS |
| Summary length | Validity | >= 30 ký tự | PASS |
| Freshness | Timeliness | `age_days > 180` không quá 25% | FRESH, 0/24 stale |

Baseline có ngày mới nhất 2026-09-15, ngày cũ nhất 2026-04-01 và stale ratio 0%. Module của Võ Trường An dùng GX 1.x Ephemeral Context, kiểm tra row count, not-null, uniqueness và summary length. Kết quả trả đồng thời `success`, `passed` và `gx_success` để đáp ứng contract của pipeline, đồng thời tách trạng thái GX khỏi Freshness SLA.

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Số record | Signal/tác động quan sát |
| --- | --- | ---: | --- |
| Drop latest records | Xóa `ceil(24 * 20%)` bài mới nhất | 5 | Mất ground-truth docs, row count giảm |
| Blank summary | Đặt summary thành chuỗi rỗng | 3 | `summary_min_length` FAIL, câu trả lời summary suy giảm |
| Inject noise | Nối marker noise vào summary | 3 | Embedding context bị nhiễu |
| Truncate title | Cắt title còn 7 ký tự | 3 | Giảm tín hiệu semantic/title lookup |
| Stale date | Trừ 365 ngày và tăng `age_days` | 6 | 28.57% stale, Freshness SLA FAIL |
| Duplicate rows | Nhân bản deterministic rows | 2 | `paper_id_unique` FAIL, tổng sau corruption là 21 |

`data/results/corruption_log.json` ghi đủ sáu scenario, tham số, affected count, `paper_id` và before/after khi phù hợp. Repair không vá trực tiếp corrupted rows. Pipeline đọc lại `data/raw/crossref_records.json`, chạy lại cleaning với ngày tham chiếu baseline, ghi repaired dataset, rebuild collection và đánh giá lại. Hai lần chạy liên tiếp tạo cùng SHA256 cho repaired JSON và repaired metrics, chứng minh tính idempotent trong cùng baseline.

## 10. So sánh ba trạng thái

| Metric/signal | Baseline | Corrupted | Repaired | Corruption delta | Recovery delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.00 | 0.80 | 1.00 | -0.20 | +0.20 |
| `mean_token_f1` | 1.00 | 0.70 | 1.00 | -0.30 | +0.30 |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 | -0.30 | +0.30 |
| `mean_judge_score` | 5.00 | 4.00 | 5.00 | -1.00 | +1.00 |
| Quality Gate | PASS | FAIL | PASS | Duplicate/summary fail | Phục hồi toàn bộ |
| Freshness | FRESH | STALE | FRESH | 0% -> 28.57% | 28.57% -> 0% |

Hai chuỗi nguyên nhân-bằng chứng:

1. Drop/blank/truncate/stale/duplicate làm dataset giảm còn 21 rows, phá uniqueness/summary/freshness; retrieval hit rate giảm 0.20 và token F1 giảm 0.30. Suite hiện chạy đồng thời nên chưa đủ bằng chứng định lượng để kết luận một scenario riêng lẻ gây toàn bộ mức giảm.
2. Rebuild từ raw snapshot phục hồi 24 unique rows, Quality Gate và Freshness trở lại PASS/FRESH; retrieval hit rate, token F1 và judge accuracy đều trở lại 1.0.

## 11. Vấn đề tích hợp quan trọng

| Vấn đề | Nguyên nhân gốc | Cách xử lý | Bằng chứng |
| --- | --- | --- | --- |
| 24/24 records thiếu category chuyên ngành | Crossref response không có `subject`, không phải lỗi parser | Nguyễn Hữu Thành fallback có kiểm soát sang work `type` | Clean data có 24/24 categories và phân bố 15/8/1 |
| Lệnh nghiệm thu gặp `KeyError: 'success'` | Quality function ban đầu chỉ trả `passed` | Võ Trường An thống nhất contract với cả `success`, `passed`, `gx_success` | Baseline/repaired trả `success=true`; corrupted trả `false` |
| Corruption embedding khác baseline contract | Thứ tự `Categories` và `Published` không khớp cleaning | Khánh đồng bộ `Title -> Authors -> Published -> Categories -> Summary`, chỉ rebuild dòng đổi | `tests/test_corruption.py`: 4 passed |
| MiniLM chưa có trong cache khi chạy offline | Cài package không đồng nghĩa model weights đã được tải | Phạm Đình Duy tải model một lần rồi xác minh cache/offline execution | Chroma baseline có 24 documents, retrieval đạt 10/10 hits |
| OpenAI judge âm thầm fallback | Biến môi trường hệ thống chứa key cũ ghi đè project `.env` | Đối chiếu fingerprint đã che, loại override cũ và chạy lại | `fallback_matches=0`, answers có OpenAI reasoning |

## 12. Giới hạn và hướng cải thiện

| Giới hạn | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| Sáu corruption chạy đồng thời | Không tách được tác động riêng của từng lỗi | Chạy ablation từng scenario và so sánh metric delta |
| Ragas chưa bật | Thiếu faithfulness/context precision/recall | Bật `RUN_RAGAS=1`, cố định provider và lưu kết quả |
| Câu hỏi chứa nguyên văn title | Exact-title lookup làm baseline dễ đạt điểm tuyệt đối | Thêm nhóm paraphrase không chứa title và báo cáo Hit Rate@4 riêng |
| Chỉ có 4 unit tests cho corruption | Coverage toàn repo chưa được đo | Thêm ingestion/quality/pipeline tests và CI coverage >80% |
| Live Crossref thay đổi theo thời gian | Snapshot mới có thể làm metrics thay đổi | Ghim snapshot/hash và lưu run metadata |
| Quality report path chung có thể bị ghi đè | Khó truy vết nếu chỉ giữ file chung | Dùng riêng baseline/corrupted/repaired freshness paths |

## 13. Checklist trước khi nộp

- [x] Đủ họ tên, MSSV và ownership của bốn thành viên.
- [x] Repository và phân công khớp với code/artifacts.
- [x] Baseline và corruption flow chạy exit code 0.
- [x] Ba trạng thái dùng cùng `data/eval/test_set.json`.
- [x] Metrics trong báo cáo khớp `data/results/`.
- [x] Quality/freshness kết luận khớp `data/quality/`.
- [x] Báo cáo so sánh và artifacts truy cập được.
- [x] `.env` được ignore và báo cáo không chứa secret.
- [X] Đưa báo cáo cá nhân của Thành, An và Duy vào `report/`; xác nhận đủ Contributor trên `main`.
