# YasinRelay Core v2 Architecture

This document describes the high-level architecture of YasinRelay Core v2 after the successful merge of FeedBridge and OpenFeed.

---

## High-Level Architecture Diagram

```
                 +-----------------------+
                 |    Telegram Channels  |
                 +-----------+-----------+
                             |
                             v
+----------------------------+----------------------------+
| Fetch Layer                                             |
|                                                         |
| - SubprocessFetcher (invokes openfeed-fetch binary)    |
| - FakeFetcher (unit tests and development)              |
+----------------------------+----------------------------+
                             |
                             | Post
                             v
+----------------------------+----------------------------+
| Storage Layer (Duplicate Check)                         |
|                                             No          |
| - Calculate SHA-256 Content Hash ------------------+    |
| - Does DBPost (source, message_id) exist?          |    |
|   Or content hash matches?                         |    |
+----------------------------+-----------------------|----+
                             | Yes                   |
                             |                       |
                             v (Skip Duplicate)      v (Process & Publish)
                      [Ignore Safely]      +---------+---------+
                                           | Processing Layer  |
                                           |                   |
                                           | - AIProcessor     |
                                           | - MediaProcessor  |
                                           +---------+---------+
                                                     |
                                                     v
                                           +---------+---------+
                                           | Publishing Layer  |
                                           |                   |
                                           | - EitaaPublisher  |
                                           | - SQLite (Mark)   |
                                           +-------------------+
```

---

## Module and Core Layers Description

### 1. Fetch Layer
The Fetch Layer retrieves new posts from specified source channels.
- **`FetchEngine`**: Abstract class defining the fetch interface.
- **`SubprocessFetcher`**: Executes the compiled Go-based `openfeed-fetch` binary located in `fetcher/`. This utilizes domain-fronting with direct Google Translate routing (`cdn*-telesco-pe.translate.goog`) and uTLS to safely bypass internet filtering/censorship without external runtime services.
- **`FakeFetcher`**: A stub used in testing to feed canned data into the pipeline.

### 2. Storage Layer
The Storage Layer is responsible for maintaining post states and deduplicating incoming posts.
- **SQLite Database**: Default persistent local database stored in `relay.db` (or custom path from `DATABASE_PATH`).
- **Models**: `DBPost` represents saved post metadata including source, message_id, content hash, text, media, status (e.g. `pending`, `published`), created timestamp, and published timestamp.
- **Functions**: `save_post()`, `get_post()`, `exists()`, `mark_published()`, and `list_recent_posts()`.
- **Deduplication pipeline**: Generates a SHA-256 signature of the content. A post is safely ignored if either its source/message_id unique pair or its content hash is already registered in SQLite, preventing double publishing after service restarts.

### 3. Processing Layer
The Processing Layer manages AI translation/rewriting and placeholder media preparation.
- **`AIProcessor`**: Interface with methods for `summarize()`, `rewrite()`, `translate()`, and `generate_title()`.
- **`PassthroughProcessor`**: Implements AI completion via OpenAI-compatible APIs (using `AI_API_KEY`/`OPENAI_API_KEY`, `AI_BASE_URL`, and `AI_MODEL` options) with full fallback to unchanged passthrough text.
- **`MediaProcessor`**: Prepares placeholders for processing images, videos, and documents safely before publication.

### 4. Publishing Layer
The Publishing Layer formats and sends finalized content to Eitaa.
- **`EitaaPublisher`**: Sends text and files to `eitaayar.ir/api/` using `sendMessage` or `sendFile` respectively.
- **Rate-limit / delay mitigation**: Enforces configurable message spacing (`INTER_MESSAGE_DELAY_SECONDS`) to comply with platform guidelines.
