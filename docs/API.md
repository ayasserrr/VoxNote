# VoxNote REST API

Base URL: `http://localhost:8000/api`. Interactive docs are at **`/docs`** (Swagger) and `/redoc`.
Every endpoint except `auth/register`, `auth/login`, `health` and `system/status` requires `Authorization: Bearer <token>`.
Document downloads also accept `?token=<token>`.

## Auth

| Method | Path | Body | Returns |
|---|---|---|---|
| POST | `/auth/register` | `{email, password, full_name?}` | `{access_token}` |
| POST | `/auth/login` | `{email, password}` | `{access_token}` |
| GET | `/auth/me` | – | user |

## Collections (processing requests)

| Method | Path | Description |
|---|---|---|
| POST | `/collections/preview` | `{url}` → video/playlist preview (title, channel, count, duration) |
| POST | `/collections` | `{url, settings}` → create and start processing (video or playlist) |
| POST | `/collections/upload` | multipart: `file`, `settings` (JSON string), `title?` → process your own audio/video |
| GET | `/collections` | list with progress counters |
| GET | `/collections/{id}` | details, videos, documents, synthesis |
| DELETE | `/collections/{id}` | delete the collection and its files |
| POST | `/collections/{id}/retry` | retry only the failed videos |
| POST | `/collections/{id}/regenerate` | body `settings` → re-run extraction and documents (transcripts reused) |
| GET | `/collections/{id}/logs` | processing log |

`settings`:

```json
{
  "output_language": "auto | en | ar | bilingual",
  "detail_level": "comprehensive | standard",
  "include_transcript": true,
  "include_timestamps": true,
  "per_video_documents": true,
  "combined_document": true,
  "max_videos": null
}
```

Status values: `pending, queued, processing, completed, partial, failed, cancelled`.
Video stages: `waiting, metadata, transcribing, language, extracting, assembling, verifying, rendering, done`
(collections also use `synthesizing`).

## Documentation & Learning Hub

| Method | Path | Description |
|---|---|---|
| POST | `/collections/docs` | `{url, max_pages, same_path_only, level, language}` → crawl docs and build a course |
| POST | `/collections/{id}/recrawl` | read the documentation again |
| GET | `/collections/{id}/pages/{page_id}` | one crawled page (clean Markdown content) |
| POST | `/collections/{id}/course` | `{level, language}` → create/rebuild the course of any collection (docs, video, playlist) |
| GET | `/courses` | your courses with progress stats |
| GET | `/courses/{id}` | course + modules/lessons (status, best score) |
| POST | `/courses/{id}/reset` | reset progress |
| DELETE | `/courses/{id}` | delete the course (source material is kept) |
| GET | `/lessons/{id}` | lesson (content if generated, quiz **without answers**, sources, last attempt) |
| POST | `/lessons/{id}/prepare` | generate the lesson if needed (and prefetch the next one) |
| POST | `/lessons/{id}/simplify` | re-explain more simply (+ fresh quiz) |
| POST | `/lessons/{id}/regenerate` | regenerate the lesson |
| POST | `/lessons/{id}/new-quiz` | new, different questions |
| POST | `/lessons/{id}/submit` | `{answers: {"q1": 0, "q2": true, "q3": "text"}}` → graded attempt, unlocks the next lesson when passed |
| POST | `/lessons/{id}/tutor` | `{question}` → tutor answer grounded in the lesson |
| PUT | `/lessons/{id}/notes` | `{notes}` → save your personal notes for a lesson |
| GET | `/review?course_id=` | spaced-repetition cards due now (questions you missed, without answers) + counts |
| POST | `/review/{card_id}/answer` | `{answer}` → graded result, new Leitner box and next due date |
| GET | `/dashboard` | streak, XP, lessons completed, average score, due reviews, certificates, continue-learning, recent |

Every course ends with a lesson of `kind: "exam"` (course recap + 10-question final exam). It unlocks after the last lesson,
and passing it sets `stats.certified`.

Lesson status values: `locked`, `available`, `completed`. Quiz question types: `mcq` (answer = option index),
`true_false` (boolean), `short` (free text, graded by the LLM with keyword-overlap fallback).

## Videos

| Method | Path | Description |
|---|---|---|
| GET | `/videos/{id}` | metadata, status, `knowledge` (full structured notes), `quality`, documents |
| GET | `/videos/{id}/transcript` | `{source, language, word_count, segments:[{idx,start,end,text}]}` |
| POST | `/videos/{id}/retry` | retry one video |

## Documents

| Method | Path | Description |
|---|---|---|
| GET | `/documents/{id}/download?inline=true` | PDF or Markdown file |

## Ask & search

| Method | Path | Description |
|---|---|---|
| POST | `/ask` | `{question, collection_id?, video_id?, top_k?}` → `{answer, sources:[{ref, video_title, start, end, text, url}], provider, model}` |
| GET | `/search?q=&collection_id=` | ranked transcript passages with deep links |

## System

| Method | Path | Description |
|---|---|---|
| GET | `/health` | liveness + database check |
| GET | `/system/status` | configured LLM providers, STT, ffmpeg, queue, storage |
| GET | `/metrics` (no `/api` prefix) | Prometheus metrics |

## Example (curl)

```bash
TOKEN=$(curl -s localhost:8000/api/auth/register -H 'content-type: application/json' \
  -d '{"email":"me@example.com","password":"secret123"}' | jq -r .access_token)

curl -s localhost:8000/api/collections -H "authorization: Bearer $TOKEN" -H 'content-type: application/json' \
  -d '{"url":"https://www.youtube.com/playlist?list=PL...","settings":{"output_language":"auto"}}' | jq '.id'
```
