# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên nhóm:** Nova
- **Mã nhóm / Lớp:** K4-L3B-DAY10
- **Repository:** `K4-L3B-DAY10-Nova-DataPipelineDataObservability`
- **Đường dẫn:** https://github.com/Dzzuy/K4-L3B-DAY10-Nova-DataPipelineDataObservability
- **Ngày hoàn thành:** 2026-09-26

## Thành viên

| STT | Họ và tên | MSSV | Email Git/GitHub | Vai trò và phân công | Báo cáo cá nhân |
| ---: | --- | --- | --- | --- | --- |
| 1 | Nguyễn Hữu Thành | 2A202602807 | `hthanh1412004@gmail.com` | Data Ingestion & Cleaning Owner, CP0-CP1 | [`individual_2A202602807_NguyenHuuThanh.md`](../report/individual_2A202602807_NguyenHuuThanh.md) |
| 2 | Võ Trường An | 2A202602656 | `gaming13102004@gmail.com` | Data Observability & Reporting Owner, CP1 và reporting CP3/CP5 | [`individual_2A202602656_VoTruongAn.md`](../report/individual_2A202602656_VoTruongAn.md) |
| 3 | Phạm Đình Duy | 2A202602913 | `kit925969@gmail.com` | Evaluation & Baseline Pipeline Owner, CP2-CP3 | [`individual_2A202602913_PhamDinhDuy.md`](../report/individual_2A202602913_PhamDinhDuy.md) |
| 4 | Trần Ngọc Khánh | 2A202602923 | `khanhtran004@gmail.com` | Corruption & Recovery Pipeline Owner, CP4-CP5 | [`individual_2A202602923_TranNgocKhanh.md`](../report/individual_2A202602923_TranNgocKhanh.md) |

## Phân công và đóng góp cá nhân

### Nguyễn Hữu Thành - 2A202602807

- **Vai trò:** Data Ingestion & Cleaning Owner.
- **Phạm vi sở hữu:** `src/ingestion/crossref.py`, `src/ingestion/cleaning.py`.
- **Công việc đã hoàn thành:**
  - Triển khai parser cho Crossref payload thành `PaperRecord`.
  - Triển khai fetch với timeout, retry/backoff cho lỗi tạm thời và fallback về snapshot local.
  - Bảo toàn hai tầng raw lineage tại `data/raw/crossref_response.json` và `data/raw/crossref_records.json`.
  - Chuẩn hóa JATS/HTML, whitespace, authors, categories và ngày tháng.
  - Deduplicate theo `paper_id`, tính `age_days`, `summary_chars` và tạo `text_for_embedding` năm phần.
  - Bổ sung category fallback từ Crossref `type` khi toàn bộ records thiếu `subject`.
- **Kết quả:** 24 raw records tạo 24 clean rows, 24 DOI duy nhất, `age_days` 11-178.
- **Commit tiêu biểu:** `80dd2fe` - `ingestion and cleaning`.

### Võ Trường An - 2A202602656

- **Vai trò:** Data Observability & Reporting Owner.
- **Phạm vi sở hữu:** `src/observability/quality.py`, `src/observability/reporting.py`.
- **Công việc đã hoàn thành:**
  - Triển khai Great Expectations 1.x bằng Ephemeral Context trên pandas DataFrame.
  - Kiểm tra row count, not-null, `paper_id` unique và summary tối thiểu 30 ký tự.
  - Triển khai Freshness SLA với ngưỡng `age_days > 180` và stale ratio tối đa 25%.
  - Chuẩn hóa output contract gồm `success`, `passed`, `gx_success`, checks và freshness.
  - Sinh báo cáo baseline và báo cáo so sánh Baseline/Corrupted/Repaired.
  - Bổ sung baseline quality và freshness artifacts trong `data/quality/`.
- **Kết quả:** Baseline và repaired đạt quality/freshness; corrupted thất bại đúng tại uniqueness, summary length và freshness.
- **Commit tiêu biểu:** `52e73be`, `c94217a`, `96e7bbc`, `37b5976`.

### Phạm Đình Duy - 2A202602913

- **Vai trò:** Evaluation & Baseline Pipeline Owner.
- **Phạm vi sở hữu:** `src/evaluation/testset.py`, `src/pipelines/phase1.py`; xác minh retrieval/evaluation modules.
- **Công việc đã hoàn thành:**
  - Tạo deterministic test set gồm 10 câu hỏi trên 10 papers trải đều trong clean DataFrame.
  - Bao phủ bốn loại câu hỏi: 3 summary, 3 authors, 2 date và 2 categories.
  - Lưu ground truth và `ground_truth_doc_ids` phục vụ retrieval hit rate.
  - Tích hợp baseline flow từ raw, cleaning, Chroma index, evaluation, quality/freshness đến Markdown report.
  - Xác minh collection `papers-baseline` có 24 documents và dùng chung test set cho ba trạng thái.
  - Đối chiếu metrics cuối sau khi CP4-CP5 được tích hợp.
- **Kết quả:** Baseline đạt retrieval hit rate 1.0, token F1 1.0, judge accuracy 1.0 và judge score 5.0.
- **Commit tiêu biểu:** `7956798`, `5b236a5`, `64120d7`, `b99f4fa`.

### Trần Ngọc Khánh - 2A202602923

- **Vai trò:** Corruption & Recovery Pipeline Owner.
- **Phạm vi sở hữu:** `src/ingestion/corruption.py`, `src/pipelines/corruption_flow.py`, `tests/test_corruption.py`.
- **Công việc đã hoàn thành:**
  - Triển khai sáu corruption scenarios deterministic: drop latest 20%, blank summary, inject noise, truncate title, stale date 365 ngày và duplicate rows.
  - Không thay đổi baseline DataFrame tại chỗ; cập nhật derived fields và ghi corruption log chi tiết.
  - Build/evaluate collection corrupted bằng cùng baseline test set.
  - Repair idempotent từ trusted raw snapshot, rebuild/evaluate repaired collection.
  - Tích hợp quality/freshness của An và comparison reporting cho ba trạng thái.
  - Đồng bộ embedding data contract với cleaning và bổ sung bốn unit tests.
  - Xác minh OpenAI judge không dùng fallback trong lần chạy cuối.
- **Kết quả:** Retrieval hit rate 1.0 -> 0.8 -> 1.0; token F1 1.0 -> 0.7 -> 1.0; quality PASS -> FAIL -> PASS.
- **Commit tiêu biểu:** `a8a911f`, `0ac78a0`, `20e0215`, `d1e91e4`.

## Luồng phối hợp

```text
Nguyễn Hữu Thành
Crossref ingestion -> cleaning/data contract
               |                  |
               v                  v
Phạm Đình Duy                    Võ Trường An
test set + baseline              GX + freshness + reporting
               \                  /
                \                /
                 v              v
                  Trần Ngọc Khánh
             corruption -> evaluate
                    -> repair
                    -> evaluate
                    -> comparison report
```

## Kết quả chung

| Metric/tín hiệu | Baseline | Corrupted | Repaired |
| --- | ---: | ---: | ---: |
| `retrieval_hit_rate` | 1.00 | 0.80 | 1.00 |
| `mean_token_f1` | 1.00 | 0.70 | 1.00 |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 |
| `mean_judge_score` | 5.00 | 4.00 | 5.00 |
| Quality Gate | PASS | FAIL | PASS |
| Freshness SLA | FRESH | STALE | FRESH |

## Xác nhận

- [x] Bốn thành viên có phạm vi ownership và output rõ ràng.
- [x] Phân công khớp với code, artifacts và lịch sử commit.
- [x] Mỗi thành viên có báo cáo cá nhân trong `report/`.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Kết quả trong tài liệu khớp với artifacts cuối.
- [x] Không có API key hoặc secret trong tài liệu này.
