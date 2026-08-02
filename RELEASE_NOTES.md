# YasinRelay v2.0.0 Stable Release Notes

We are thrilled to announce the stable release of **YasinRelay v2.0.0**, a highly robust, secure, and production-ready message relay pipeline bridging Telegram and Eitaa channels.

---

## Executive Summary of Major Features Delivered

YasinRelay v2.0.0 introduces a modular **Phase 2 Pipeline Engine** coupled with a high-performance **Message Router and Transport Layer** designed to offer flawless content delivery, advanced AI rewriting/translation, and persistent SQLite database deduplication.

### Key Features in v2.0.0:
1. **Modular Pipeline Engine**: Ordered stages featuring independent error isolation (`Collector`, `Normalizer`, `Validator`, `DuplicateDetection`, `AIProcessor`, `MediaProcessor`, `Publisher`).
2. **Intelligent Message Routing**: Prioritization rules (`RoutingRule`, `ChannelRule`, `KeywordRule`, `RegexRule`) combined with customizable content transformers.
3. **Advanced Go Fetcher Integration**: Dual-mode Go subprocess fetcher (`fetch` and `download`) utilizing `uTLS` and translation domain-fronting to reliably bypass local network filters.
4. **Reliable Dead-Letter Queue (DLQ)**: Failed message tracking and fallback/retry systems to handle temporary external API or network outages.
5. **Decoupled Event Bus**: Thread-safe event distribution using wildcard subscription and isolated handler execution for zero pipeline disruption.
6. **Robust Logging and Sensitive Masking**: Dedicated log rotation with automatic credentials masking (e.g., `EITAA_TOKEN` and API keys) under `logs/relay.log` and `logs/error.log`.

---

## Integration Status and Ecosystem Compatibility

### 1. Yasin-Core SDK Integration Status
YasinRelay is fully integrated with **Yasin-Core v1.0.0**. The platform uses only the public SDK APIs to manage hierarchial contexts, store memory elements, and register/execute tools:
- **Hierarchical Contexts**: Uses `active_context` and `get_current_context` to track the state, pipeline configurations, and processing pipeline metadata.
- **Memory Store**: Standardized short-term and long-term memories accessed via the public client API.
- **Pluggable Tools**: Uses `@tool` to register formatting, translation, or validation actions dynamically.

### 2. YasinHub Compatibility
- **Status Reporting Layer**: Implemented structured, automatic status updates inside `yasinrelay/hub_integration.py`.
- **JSON File Fallback**: Dynamically dumps operational logs and pipeline statistics to `~/.yasin_status/` to guarantee communication resilience.

### 3. Yasin-Agent Compatibility
- Fully compatible with the **Yasin Agent Platform**.
- Translates pipeline milestones into Standard Agent Lifecycle Hooks and Events, allowing AI agents to dynamically plan, supervise, and execute relay schedules.

### 4. Agent Communication Support
- Powered by `AgentCommunicator` in `yasinrelay/agent/communication.py`.
- Incorporates dynamic state synchronization, automatic retry loops for connection drops, and robust exception-safe event propagation.

### 5. Runtime Monitoring Subsystem
- The custom `HealthMonitor` hooks into the `EventBus` to track metrics:
  - Uptime duration
  - Message metrics (Total fetched, successfully published, and failed counts)
  - Connectivity status (SQLite db, Go fetcher binary availability, and Eitaayar API HEAD checks)
- Seamlessly accessible through the public client API (`YasinRelayClient.get_status()`).

---

## Production Readiness Audit & Safety Report

Following a rigorous security and robustness audit, YasinRelay v2.0.0 includes:
- **Input Sanitization**: Strictly checks and validates all media URLs fetched from sources before passing to subprocess commands to eliminate shell injection vulnerabilities.
- **Graceful Error Recovery**: Replaces fragile API dependencies with bulletproof fallback cascades. If AI completions or translation endpoints fail, the pipeline falls back to the original text.
- **Robust Transaction Management**: All SQLite transactions and database connections are guarded with try-except-finally blocks to eliminate locking issues.
- **Log Masking**: Custom logging formatters mask sensitive credentials dynamically.

---

*Prepared by Jules for the YasinRelay v2.0.0 Stable Release.*
