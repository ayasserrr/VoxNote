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
