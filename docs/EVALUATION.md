# Evaluation & quality

AI-generated study material is only useful if it is **complete** and **faithful** to the source. VoxNote measures both for every
video, and the project includes a protocol for evaluating it offline.

## Built-in, per-video checks (`services/knowledge.py::verify`)

| Metric | Definition | Why |
|---|---|---|
| `timeline_coverage` | Share of video minutes that have at least one extracted concept, example, key point or technical item | Detects sections the model skipped |
| `concept_grounding` | Share of concepts whose name (or a word of it) appears in the transcript | Detects invented concepts |
| `invalid_timestamps` | References that point beyond the video duration | Detects broken citations |
| `failed_chunks` | Transcript parts whose extraction failed (their transcript is still included) | Partial-failure visibility |
| `llm_calls`, tokens, provider | Cost and usage tracking | Cost per hour of video |

Warnings are shown in the UI (Quality tab), in the PDF's quality report and in the processing log.

## Operational metrics (Prometheus)

- Processing time per stage (`voxnote_stage_seconds`) gives the time per video and per hour of audio.
- Success and failure counts (`voxnote_videos_processed_total`) give the success rate.
- LLM requests by outcome (`ok`, `http_429`, …) and tokens by provider give rate-limit pressure and cost.
- Transcript source mix (captions vs Whisper).
- Documents generated, which gives the PDF generation success rate.

## Offline evaluation protocol (suggested)

1. **Transcription WER**: for 10 videos with manual captions (5 English, 5 Arabic/mixed), transcribe the audio with Whisper and
   compare against the captions using `jiwer` (normalise Arabic first: alef variants, diacritics).
2. **Extraction completeness**: annotate 20–30 key concepts per lecture by hand and measure recall, i.e. the share found in `knowledge.concepts`.
3. **Factual consistency**: sample 50 extracted statements (`instructor_points`, definitions) and label them as supported, unsupported or
   contradicted by the transcript. An LLM judge can pre-label them, with a human checking the result. Target ≥ 95% supported.
4. **Timestamp accuracy**: for the same sample, check that the cited timestamp is within ±30 s of the actual mention.
5. **Provider comparison**: run the same lectures through Groq / Gemini / Ollama and compare completeness, consistency, latency and tokens.

Record the results in a table in the README to make the project's claims measurable.
