# YasinRelay Core v2 Architecture

This document describes the high-level architecture of YasinRelay Core v2 after the successful merge of FeedBridge and OpenFeed and the implementation of the Phase 2 Pipeline Engine.

---

## High-Level Architecture Diagram

```
                 +-----------------------+
                 |    Telegram Channels  |
                 +-----------+-----------+
                             |
                             v
+----------------------------+----------------------------+
| Fetch Layer (Collector)                                 |
|                                                         |
| - SubprocessFetcher (invokes openfeed-fetch binary)    |
| - FakeFetcher (unit tests and development)              |
+----------------------------+----------------------------+
                             |
                             | Post
                             v
+----------------------------+----------------------------+
| Pipeline Engine (Modular Stages)                        |
|                                                         |
|   [ CollectorStage ]                                    |
|          |                                              |
|   [ NormalizerStage ] (Polish & clean text)             |
|          |                                              |
|   [ ValidatorStage ] (Verify non-empty constraints)     |
|          |                                              |
|   [ DuplicateDetectionStage ] (Checks SQLite Db)        |
|          |                                              |
|   [ AIProcessorStage ] (Rewrite or Translate)           |
|          |                                              |
|   [ MediaProcessorStage ] (Process image/video/doc)     |
|          |                                              |
|   [ PublisherStage ] (Eitaa & mark DB published)        |
+---------------------------------------------------------+
```

---

## Module and Core Layers Description

### 1. Fetch Layer (Collector)
The Fetch Layer retrieves new posts from specified source channels.
- **`FetchEngine`**: Abstract class defining the fetch interface.
- **`SubprocessFetcher`**: Executes the compiled Go-based `openfeed-fetch` binary located in `fetcher/`. This utilizes domain-fronting with direct Google Translate routing (`cdn*-telesco-pe.translate.goog`) and uTLS to safely bypass internet filtering/censorship without external runtime services.
- **`FakeFetcher`**: A stub used in testing to feed canned data into the pipeline.

### 2. Pipeline Engine (Modular Stages)
The Pipeline Engine orchestrates the execution flow of each message/item using a series of independent, order-preserving stages wrapped inside `PipelineManager`:
- **`PipelineContext`**: Tracks processing data (`processed_text`, `processed_media_url`, metadata, duplicate/validation states, and errors) as it flows from stage to stage.
- **`PipelineStage`**: Abstract class that defines the stage interface (`process(context: PipelineContext)`).
- **Graceful Failure Isolation**: Any error occurring inside a stage is logged and recorded in `context.errors` without halting execution of separate items in the pipeline or interrupting the Scheduler.

#### Core Stages:
1. **`CollectorStage`**: Transforms raw posts fetched from `FetchEngine` into `PipelineContext` objects.
2. **`NormalizerStage`**: Normalizes and cleans up the message text (removes whitespace, format spacing, etc.).
3. **`ValidatorStage`**: Checks structural sanity (e.g., verifying that the message actually contains text or a media URL).
4. **`DuplicateDetectionStage`**: Generates a SHA-256 hash and checks the SQLite database for duplicates. If not a duplicate, inserts a record with a `pending` status.
5. **`AIProcessorStage`**: Rewrites or translates content based on configurations.
6. **`MediaProcessorStage`**: Processes media assets (e.g., download / upload preparation).
7. **`PublisherStage`**: Publishes the final context to Eitaa and updates the status in SQLite to `published`.

### 3. Storage Layer
The Storage Layer is responsible for maintaining post states and deduplicating incoming posts.
- **SQLite Database**: Default persistent local database stored in `relay.db` (or custom path from `DATABASE_PATH`).
- **Models**: `DBPost` represents saved post metadata including source, message_id, content hash, text, media, status (e.g. `pending`, `published`), created timestamp, and published timestamp.
- **Functions**: `save_post()`, `get_post()`, `exists()`, `mark_published()`, and `list_recent_posts()`.

### 4. Publishing Layer
The Publishing Layer formats and sends finalized content to Eitaa.
- **`EitaaPublisher`**: Sends text and files to `eitaayar.ir/api/` using `sendMessage` or `sendFile` respectively.
- **Rate-limit / delay mitigation**: Enforces configurable message spacing (`INTER_MESSAGE_DELAY_SECONDS`) to comply with platform guidelines.

---

## Extension Points

### Adding a Custom Stage
To add a new stage to the Pipeline Engine, simply inherit from `PipelineStage` and register it in `PipelineManager` inside `yasinrelay/pipeline.py`:

```python
from yasinrelay.pipeline_engine import PipelineStage, PipelineContext

class WatermarkStage(PipelineStage):
    def process(self, context: PipelineContext) -> PipelineContext:
        if context.processed_media_url:
            # Code to apply watermark to image/video
            context.processed_media_url = apply_watermark(context.processed_media_url)
        return context
```

---

## Core Event Bus & Integration Layer Architecture

To support high extensibility and decoupling, YasinRelay Core v2 implements a native **Core Event Bus** and a structured **Integration Layer**. This enables future external systems (e.g., YasinPress-AI-Engine, AI Agents, external analytics/logging, or plugins) to hook into any step of the pipeline.

### High-Level Event Flow

```
+----------------+      publish(ContentReceived)       +-------------------+
| CollectorStage | ----------------------------------> |                   |
+----------------+                                     |                   |
                                                       |                   |
+-----------------+     publish(ContentNormalized)     |                   |
| NormalizerStage | ---------------------------------> |     EventBus      |
+-----------------+                                     |                   |
                                                       |   (Distributes    |
       ...                                             |    events to      |
                                                       |    subscribed     |
+-----------------+     publish(PublishingCompleted)   |    listeners)     |
| PublisherStage  | ---------------------------------> |                   |
+-----------------+                                     |                   |
                                                       |                   |
+-----------------+     publish(ProcessingFailed)      |                   |
| PipelineManager | ---------------------------------> |                   |
+-----------------+                                    +---------+---------+
                                                                 |
                                                                 v
                                                       +-------------------+
                                                       | Subscribed        |
                                                       | Handlers/Plugins  |
                                                       +-------------------+
```

### Event System Details
- **`PipelineEvent`**: The standardized dataclass representing events. It includes the event `name`, `timestamp` (when it occurred), a unique `content_id` (usually `source_channel:message_id` or equivalent), the `payload` dictionary with event-specific data (e.g., the serialized post or normalized text), and a `metadata` dictionary.
- **`EventBus`**: Supports publishing (`publish()`), subscribing to specific events or all events via wildcard (`subscribe()`), unsubscribing (`unsubscribe()`), and clearing all handlers (`clear()`).
- **Handler Failure Isolation**: All event handlers are executed within isolated `try/except` blocks. If an event listener raises an unhandled exception, it is logged and recorded, but the exception **never** halts the main pipeline execution.
- **Configurable Control**: The entire event bus and logging can be toggled using environment configurations (`EVENT_BUS_ENABLED`, `EVENT_LOGGING_ENABLED`).

### Integration Layer & Plugins Foundation
- **`IntegrationRegistry`**: A central hub that maintains mappings for third-party extensions. It features decorator-friendly registration APIs for:
  - Custom AI Content Processors (`register_ai_provider`)
  - Custom Feed Sources (`register_feed_source`)
  - Custom Destination Publishers (`register_publisher`)
  - Custom Media Processors (`register_media_processor`)
- **`IntegrationPlugin`**: An abstract interface that developers of external systems inherit to create complex, cohesive plugin packages. These plugins are registerable inside `IntegrationRegistry` and initialized with the system `EventBus` to bind custom handlers/logic.
