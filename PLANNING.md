# 🗺️ Planning: MCP Server Reliability Improvements

## 📍 Context
The `yfinance_mcp` server calls `web_summarizer_mcp` to process URLs. The interaction was brittle due to a strict 60-second timeout. We increased this to 300s and added retry logic to handle transient failures gracefully.

## 🎯 Objectives
1.  **Eliminate Timeouts:** Increase tolerance for long-running operations (rate limiting waits, slow scraping).
2.  **Add Resilience:** Implement exponential backoff retries for network glitches.
3.  **Configurability:** Externalize timeout settings (Done).
4.  **Voice-Mode Background Integration:** Run `uvx voice-mode` as a persistent background process.

## 🏗️ Architecture & Decisions (ADRs)

### ADR-001: Client-Side Retries
*   **Decision:** Use `tenacity` library in `yfinance_mcp`.
*   **Rationale:** Robust, declarative retry logic.

### ADR-002: Increased & Configurable Timeouts
*   **Decision:** Default timeout set to **300s (5 minutes)**.
*   **Status:** Config updated in `mcp/yfinance_mcp/src/config.py`.

### ADR-003: Voice-Mode Process Management
*   **Decision:** Use a standalone systemd user service OR a background shell process (to be confirmed).
*   **Rationale:** Consistency with existing `mcp-servers.service` pattern for long-running tasks.

## 📝 Implementation Plan

### Phase 1: `yfinance_mcp` Hardening
... (existing items) ...

### Phase 5: Voice-Mode Setup

- [ ] **Discovery:** Check `voice-mode` documentation for required environment variables (e.g., `GEMINI_API_KEY`).
- [ ] **Scripting:** Create `scripts/voice_mode_start.sh` to handle background execution with `nohup` and logging.
- [ ] **Systemd (Optional):** Create `voice-mode.service` in `~/.config/systemd/user/` for persistence across reboots.
- [ ] **Verification:** Use `ps aux | grep voice-mode` and `tail -f` on logs to confirm it's running correctly.

- [x] **Config Update:** Default timeout increased to 300s in `config.py`.
- [x] **Dependency Update:** Added `tenacity` to `mcp/yfinance_mcp/pyproject.toml`.
- [x] **Client Refactor:** Modified `mcp/yfinance_mcp/src/web_summarizer_client.py`:
    - [x] Imported `tenacity`.
    - [x] Added retry strategy for connection errors and timeouts (within the global timeout).

### Phase 2: Verification

- [x] **Integration Check:** Ran `mcp/test_concurrent_search.py` with multiple symbols ("DIS", "GOOGL", "PETR4.SA", "VALE3.SA").
    - **Result:** Success. All requests completed in ~100s without fallback.

### Phase 3: `web_summarizer_mcp` Hardening

- [ ] **Diagnosis:** Identified issues with unbounded concurrency causing browser crashes and API limit failures.
- [ ] **Concurrency Control:**
    - [ ] Implement `asyncio.Semaphore` in `server.py` to limit concurrent crawling tasks (prevent "frame detached" errors).
- [ ] **Crawler Resilience (`crawler.py`):**
    - [ ] Implement exponential backoff for retries.
    - [ ] Add container-friendly browser arguments (`--no-sandbox`, `--disable-dev-shm-usage`).
    - [ ] Increase default retries.
- [x] **API Resilience (`summarizer.py`):**
    - [x] Implement retry loop for 429 (Rate Limit) and Quota Exhausted errors.
    - [x] Ensure internal handling of limits so the tool returns success eventually.

### Phase 4: Robust Crawl4AI Configuration



- [x] **Strategy Change:** User requested to optimize `crawl4ai` usage instead of implementing a fallback. The library is designed for AI/scraping and should be configured correctly.

- [x] **Implementation Plan:**

    - [x] **Modify `crawler.py`:**

        - [x] Remove `simple_crawl` fallback.

        - [x] Optimize `BrowserConfig`:

            - [x] Add `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`.

            - [x] Add `--window-size=1920,1080`.

            - [x] Enable verbose logging.

        - [x] Optimize `CrawlerRunConfig`:

            - [x] Use `wait_until="domcontentloaded"` (faster/safer).

            - [x] Set `page_timeout` explicitly.

            - [x] Enable `remove_overlay_elements`.

    - [x] **Refine API Retries (`summarizer.py`):**

        - [x] Increased retries to 10.

        - [x] Implemented capped exponential backoff.

        - [x] Fallback to raw content on total exhaustion (guaranteed output).
