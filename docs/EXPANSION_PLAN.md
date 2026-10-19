# Original broad expansion plan (superseded for Phase 1B)

The user authorized targeted expansion and Phase 2 cohort/features, but no training. `PHASE2_PLAN.md` supersedes this original 17.064 GiB proposal: January 2024 paired-member gate first, then only the remaining 2024 members if it passes. 2025 and full parent ZIP acquisition stay pending. Preserve the original proposal below as decision context, not an instruction to download everything.

## Current boundary

The Phase 1 acceptance target is a verified linked real-data pilot plus a feasible expansion plan. Full 2024–2025 acquisition is pending; no model training is authorized in this phase. Current downloaded years are 2022–2023 only. Raw sources and generated sample artifacts are local and ignored, so a fresh checkout must reacquire them using the pinned manifests.

## Next acquisition window

1. Recheck available RAM and D: space with the supplied resource checks. Preserve at least 5 GiB free; budget the actual pending source bytes below plus measured environment/cache/sample usage. Keep TEMP/TMP, package caches, extraction scratch, and generated data on D:.
2. Validate the June 2026 result/item header and date/ID representations, including `completed_date` and the renamed item location field. Write and test an explicit CSV adapter that rejects unexpected columns. Verify all monthly headers, not just the already inspected prefixes. Keep completion time as label-availability metadata, never a prediction feature.
3. Acquire the paired 2024 June 2026 archives sequentially: 9,127,363,082 bytes (8.501 GiB). Verify pinned size, ETag, SHA-256 when known, and member CRCs while streaming. Do not acquire the alternative March 2025 2024 pair.
4. Apply the same SplitMix64 rule and modulus to every monthly member. Retain all months/tests for sampled vehicles. Validate cross-year matches with 2023, class/make/model/first-use consistency, duplicate IDs, item coverage, severity/category mappings, and plausible follow-up gaps. If linkage is inconsistent, stop and diagnose the ID/release issue before claiming four-year histories.
5. After the 2024 gate passes, acquire the paired 2025 archives sequentially: 9,195,264,017 bytes (8.564 GiB), and repeat all checks. Total additional transfer is **18,322,627,099 bytes (17.064 GiB)**, verified from HEAD responses. Both release pairs contain stored monthly CSVs, so unpacking full archives provides no storage benefit. Stream members; isolate workers by member if measured memory requires it.

The 2024–2025 member sizes total 18,322,616,227 uncompressed bytes, according to ZIP directories (not yet full CRC verification). Full archives including current 2022–2023 inputs total 21,575,885,232 bytes. Generated sample size is not yet known for those years; use a hard local capacity reserve and measure growth rather than inventing a compression/output estimate. Existing D: capacity supports these raw archive totals; available RAM must be rechecked at execution time.

Planned acquisition commands after schema/lineage gates are ready (not run in Phase 1):

```powershell
.\.venv\Scripts\python.exe -u -m pipeline.sources fetch --match '^dft_test_(result|item)_extracts_2024\.zip$' --max-bytes 5000000000
.\.venv\Scripts\python.exe -u -m pipeline.sources fetch --match '^dft_test_(result|item)_extracts_2025\.zip$' --max-bytes 5000000000
```

The current sampler deliberately supports only the verified 2022–2023 pipe schema. The commands above acquire bytes; they do not make the existing sampler compatible with newer CSVs. No source updates, larger transfers, or retraining run automatically.

## Evaluation feasibility gate

Two acquired years give useful 2022→2023 follow-ups but cannot establish a robust prospective annual train/validation/test evaluation. A label from a 2022 advisory whose next normal test is in 2023 is not available to a prediction made earlier in 2023. Same-year normal tests are a selected minority, not a substitute for a mature annual cohort. Right-censored 2023 anchors are not negative examples. Histories are also left-truncated at 2022.

The identified four-year window could support an honest retrospective chronological train/test experiment: train using eligible 2022 anchors whose outcomes are observed before 2024-01-01; evaluate disjoint vehicles' 2024 anchors with next-test outcomes in 2024–2025. Enforce `training_outcome_available_date < evaluation_prediction_date`, not just anchor-year splitting. Keep model/threshold selection before evaluation prediction dates, account for completion timestamps where verified, and report revision/availability limitations in older data.

Four calendar years do not automatically supply three fully mature annual prediction cohorts for training, validation, and final testing. Count date-eligible, vehicle-disjoint cohorts and positives first. Predeclare a modest selection protocol using only pre-evaluation labels; if no adequate time-respecting validation window exists, request a longer authoritative window or defer model selection rather than leaking outcomes or labelling unobserved follow-ups negative.

## Resource and release gates

Use the measured per-worker peak from the completed pilot/sample and run one heavy archive/member worker at a time. Keep the sampled numeric test-ID index at or below 200,000 entries; beyond that implement a disk-backed indexed item join. Do not accumulate a population-size Python set of test IDs. Preserve complete acquired histories for the fixed sample; no first-N or independent per-year sampling.

Docker, model training, serving data, GitHub deployment, and AWS resources remain outside this phase. The domain and infrastructure estimate/approval decisions remain unchanged.
