# Yasin Core Architecture


## Overview

Yasin Core is the central runtime layer of the Yasin AI Ecosystem.


## Main Components


### Runtime

Responsible for:

- Starting system
- Managing lifecycle
- Providing core services


### Event Bus

Provides internal communication between modules.


Example:

YasinRelay

emits:

NEW_CONTENT


YasinPress

receives event.


### Plugin System

Allows extending Yasin Core without changing the kernel.


### Provider Layer

Provides abstraction for AI models.


Future providers:

- OpenAI
- Ollama
- HuggingFace
- Local Models


## Memory Architecture (v0.2)

Yasin Core v0.2 introduces a modular Memory Architecture consisting of three independent yet connected layers designed to manage state, transient execution data, and persistent storage across the ecosystem.

```
+-------------------------------------------------------------+
|                  Plugin System / Providers                  |
+-------------------------------------------------------------+
                               | Uses
                               v
+-------------------------------------------------------------+
|                        Context Layer                        |
| - Scoped variable isolation / hierarchical context          |
| - Async-safe and Thread-safe active context tracking        |
+-------------------------------------------------------------+
                               | Can reference
                               v
+-------------------------------------------------------------+
|                        Memory Layer                         |
| - ShortTermMemory: transient session storage                |
| - LongTermMemory: persistent search-oriented storage        |
+-------------------------------------------------------------+
                               | Storage Backend
                               v
+-------------------------------------------------------------+
|                        Storage Layer                        |
| - Pluggable backend interface (BaseStorage)                 |
| - Default concrete JSONFileStorage                          |
+-------------------------------------------------------------+
```

### 1. Memory Layer (`yasin_core/memory/`)

Provides abstraction for cognitive state tracking of AI agents.
- **BaseMemory**: Defines common dictionary-like CRUD interface (`set`, `get`, `delete`, `clear`).
- **ShortTermMemory**: Subclass of BaseMemory optimized for high-speed, transient/session-scoped ephemeral records (such as immediate chat turn history).
- **LongTermMemory**: Subclass of BaseMemory adding querying capabilities (`search`) for retrieving relevant records based on keyword matching across structured profiles, list values, or text logs.
- **Implementations**:
  - `InMemoryShortTermMemory` & `InMemoryLongTermMemory`: Fast in-memory dictionary-backed implementations.
  - `StorageLongTermMemory`: Pluggable storage-backed implementation ensuring memories persist across runtime lifecycles.

### 2. Context Layer (`yasin_core/context/`)

Manages the transient execution state passed between the Yasin Runtime, active Plugins, and AI Providers.
- **Thread & Async-Safe**: Utilizing Python's `contextvars` to ensure distinct threads or coroutines run within isolated context spaces without data leakage.
- **Hierarchical/Scoped**: Supports nested parent-child inheritance (`ctx.child()`), allowing child contexts to read from parent environments while safely writing or overriding keys locally.
- **Access Protocols**: Fully compatible with dictionary lookup/setting (`ctx['key']`), attribute access (`ctx.key`), and standard python context managers (`with ctx:`).
- **Active Tracking**: Callers can dynamically fetch the currently active runtime context using `Context.get_current()`.

### 3. Storage Layer (`yasin_core/storage/`)

A pluggable persistence layer designed to shield the rest of the application from specific database implementations.
- **BaseStorage**: Simple, clean abstract interface for standard storage backends.
- **JSONFileStorage**: Concrete implementation of `BaseStorage` that persists data locally using human-readable JSON files with active thread locking (`threading.Lock`) for safety.
- **Decoupled Swapping**: Includes global registry utilities (`get_storage()`, `set_storage()`) allowing runtime systems to swap out the JSON file backend with database-backed storage (such as SQLite or PostgreSQL) at startup without modifying callers.
