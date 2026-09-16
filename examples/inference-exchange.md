# Inference Exchange

## Coordinator
- FastAPI app + WebSocket hub ✅ (main.py, 405 lines)
  - CORS + CSRF middleware
  - Health/readiness probes
  - Provider WS with idle timeout (5min)
  - Attestation challenge loop (5min interval, 30s timeout)
  - ⚠️ StoreAuthAdapter/StoreBillingAdapter should be cleaned up
- Routes: inference ✅ (564 lines, tested via #35)
  - OpenAI-compatible /v1/chat/completions
  - Streaming + non-streaming
  - Input validation, balance check, rate limiting
  - Request queuing (50 depth, 30s timeout, FIFO)
  - Retry on provider failure
  - ⚠️ Duplicated scoring trace block (should extract helper)
- Routes: confidential relay ✅ (240 lines, PR #35)
  - POST /v1/confidential/infer — #28
  - Rejects plaintext messages (CB-1) — tested
  - Relays encrypted envelope unchanged
  - Bills using estimated_input_tokens
- Routes: exchange ✅ (407 lines, 13 marketplace endpoints)
  - providers, pricing, balance, depth, traces, TPS, reputation
  - ⚠️ /v1/exchange/history uses raw SQL instead of Store method
- Routes: auth ✅ (JWT + API keys, 212 lines)
  - Signup/login with email+password
  - Custom HMAC-SHA256 JWT (no external dep)
  - ⚠️ Password hashing is SHA-256+salt (alpha-grade, not bcrypt)
  - ⚠️ JWT secret regenerates on restart unless IE_JWT_SECRET set
- Routes: admin ✅ (admin state dump, provider tokens)
- Routes: handshake ✅ (confidential provider discovery, PR #27)
  - Deliberately fail-closed until App Attest admission wired
- Provider Hub ✅ (306 lines, well-tested)
  - register/disconnect with orphaned request cleanup
  - select_provider via GreedyStrategy
  - Session affinity (20% bonus, LRU 1000)
  - ⚠️ app_attest_verified never set True for confidential providers

## Matching Engine ✅
- GreedyStrategy ✅ (used in production, O(n×m), FIFO fair)
  - 4 hard filters: model, price, trust, capacity
  - 4 weighted scoring dimensions: price, speed, trust, load
  - Reputation modifier + session affinity bonus
  - Tests: test_matching.py (262 lines), test_preferences.py — #33
- BatchAuctionStrategy ✅ (implemented, most-constrained-first)
  - ⚠️ Not wired into live routing — only Greedy used
- Future: StreamingStrategy, VCGAuction, PredictiveStrategy ❌

## Consumer SDK
- ConfidentialTransport ✅ (280 lines, PR #35) — #29
  - OpenAI SDK http_client plugin
  - NaCl Box encryption (same crypto provider speaks)
  - Includes consumer_public_key for response E2E
  - Session tracking (session_id + sequence)
  - Decrypts streaming + non-streaming responses
  - Fallback to OpenAI/OpenRouter (opt-in, disabled by default)
  - Provider key discovery from /v1/exchange/providers
  - Tests: test_confidential_sdk.py (response decryption verified)
- ExchangeClient ✅ (marketplace REST wrapper)
  - balance, providers, pricing, depth, stats, API keys
- Legacy ie_sdk.py ✅ (129 lines, to be deprecated)

## Confidential Inference Path
- Request E2E ✅ — consumer encrypts locally, coordinator blind — #21
  - Validated on hardware: Intel MBP → M2 MBP, Llama 3.1 8B
  - Coordinator logs show no plaintext (manually verified)
- Response E2E ✅ — provider encrypts tokens to consumer key
  - Provider reads consumer_public_key from decrypted payload
  - Each token encrypted individually (NaCl Box)
- Coordinator blindness enforced ✅ — #28
  - /v1/confidential/infer rejects messages field (400)
  - Tests: test_confidential_relay.py
- Non-confidential path ✅ — /v1/chat/completions
  - Coordinator encrypts to provider (sees plaintext)
  - Kept for OpenAI SDK drop-in compatibility

## Provider Architecture
- OCIP Agent ✅ (ocip_agent/agent.py, 634 lines)
  - Two-process: agent + isolated inference server
  - WebSocket to coordinator (outbound, reconnect on disconnect)
  - Request decrypt → forward to server → encrypt response → relay
  - Cancellation support (kill in-flight tasks)
  - Heartbeat (10s), health monitor (15s), auto-restart (exp backoff, max 5)
  - Attestation response (SIP, Hardened Runtime, binary hashes)
  - Provider token authentication
- Inference Server ✅ (ocip_server/server.py)
  - FastAPI on 127.0.0.1:9999 only (not 0.0.0.0)
  - llama-cpp-python + Metal/CPU
  - /health, /identity (GGUF metadata), /v1/chat/completions
- Legacy Simple Agent ⚠️ (provider/agent.py — deprecated)
  - Single-process, in-process inference
  - No attestation, no provider tokens
  - ⚠️ TODO: cancellation not implemented
  - Kept for docker-compose demo only
- Model Identity ✅ (model_identity.py)
  - GGUF metadata reader (name, arch, quantization, context, blocks)
  - SHA-256 file hash (⚠️ skips files >2GB)
  - Tests: test_model_identity.py

## Hardening (provider-hardened/)
- PT_DENY_ATTACH ✅ (hardening.c) — blocks debugger permanently
- Core dump disabled ✅ (RLIMIT_CORE=0)
- SIP verification ✅ — refuses to run if SIP disabled
- Windows hardening ✅ (hardening_windows.c — separate)
- Build scripts ✅ (build.sh, build-agent.sh, build-poc.sh)
- Entitlements ✅ (no com.apple.security.get-task-allow)
- ❌ L2 self-test not yet built — #3
- ❌ Runtime validation not automated — #8
- ❌ Plaintext leakage audit not done — #7

## Security
- NaCl Box ✅ (shared/crypto.py, X25519 + XSalsa20-Poly1305)
  - Per-request forward secrecy (fresh ephemeral key each call)
  - Tests: test_crypto.py (roundtrip, forward secrecy, wrong key, tampering)
- AES-256-GCM Sessions ✅ (shared/e2e.py, PR #24)
  - Ed25519 identity signing
  - X25519 ephemeral key exchange
  - HKDF-SHA256 key derivation
  - Directional keys (consumer→provider, provider→consumer)
  - Sequence numbers + replay protection
  - Tests: test_e2e.py (roundtrip, tamper, replay, direction, signature)
  - ⚠️ Not wired into live path — NaCl Box used instead for now
- Provider Offers + Handshake ✅ (shared/handshake.py, PR #27)
  - ProviderOffer with L2/expiry/identity validation
  - Canonical transcript for session binding
  - session_hello with no inference plaintext
  - Tests: test_handshake.py
- App Attest Verifier ✅ (app_attest.py, PR #23, 234 lines)
  - CBOR + X.509 chain validation against Apple Root CA
  - Nonce/RP-ID/AAGUID/key-ID checks
  - Admission binding (identity + encryption key + artifact hash)
  - Tests: test_app_attest.py (negative cases)
  - ⚠️ Not wired into live admission — provider_hub never grants True
  - ❌ Native macOS App Attest client — #22 (needs $99 Apple Dev)
- Attestation Loop ✅ — challenge every 5min, 30s timeout
  - Evaluates hardening evidence (SIP, runtime, PT_DENY_ATTACH)
  - Degrades provider if evidence missing
- ❌ Attack tests not created — #4, #5, #6

## Billing ✅
- Micro-USD integer arithmetic (1 USD = 1,000,000 micro)
- 90/10 split (provider 90%, platform 10%)
- Minimum charge $0.0001 per request
- SQLite-backed (store.py) — survives restarts
- Legacy in-memory billing (billing_memory.py) — tests only
- Property-tested: 1000 random events, books always balance
  - Tests: test_financial_invariants.py, test_billing.py
- Reference pricing (OpenRouter live API + static major providers)
- Confidential mode: trusts provider-reported token count

## Persistence ✅
- SQLite WAL (~/.inference-exchange/exchange.db)
  - accounts, api_keys (SHA-256 hashed), transactions
  - provider_history, provider_tokens, users
  - Tests: test_store.py (302 lines, comprehensive)
- Audit Log ✅ (~/.inference-exchange/audit.jsonl)
  - Append-only, hash-chained (SHA-256 per entry)
  - Records: billing, attestation, connect/disconnect
  - Tests: test_audit_log.py
  - ⚠️ No chain verification utility (write-only)

## Reputation + TPS ✅
- Reputation: EMA per provider (α=0.2)
  - Composite: 0.7 × success_rate + 0.3 × latency_score
  - Degraded at <50% success after 5+ requests
  - Tests: test_reputation.py
  - ⚠️ In-memory only (lost on restart)
- TPS: EMA per (provider, model) (α=0.15)
  - Hardware lookup table for initial estimates
  - Anomaly detection (latest < 50% of EMA)
  - Tests: test_tps_tracker.py
  - ⚠️ In-memory only

## Infrastructure
- Rate Limiting ✅ — token bucket, 30 rpm per key, burst 10
  - Tests: test_rate_limiter.py
  - ⚠️ In-memory only
- Event Bus ✅ — async pub/sub, 50-event history, WS feed
  - Tests: test_event_bus.py
- Web Dashboard ✅ — React 18 + Vite + Tailwind
  - 8 pages: Landing, Exchange, Chat, Models, Providers, Billing, Keys, Admin
  - ❌ No frontend tests
- Docker Compose ✅ — coordinator + 3 provider tiers
  - ⚠️ Uses deprecated simple provider (not OCIP agent)
- SECURITY.md ✅ — vulnerability reporting, PR #35
- Protocol Spec ✅ — docs/security/alpha-protocol-spec.md
- System Design Spec ✅ — docs/alpha-system-design-spec.md
- L2 Threat Model ✅ — docs/security/threat-model.md, PR #18
- PCC Comparison ✅ — docs/security/pcc-comparison.md
- ⚠️ pyproject.toml has duplicate cryptography dependency line

## Alpha Gaps (8 open issues)
- ❌ L2 self-test — #3 (hardening code exists, no self-test wrapper)
- ❌ Plaintext leakage audit — #7 (need to verify logs)
- ❌ Runtime hardening validation — #8 (automated verification needed)
- ❌ E2E smoke test automation — #11 (manual test done, needs script)
- ❌ Getting-started guide — #15
- ❌ Known limitations doc — #16
- ❌ Alpha devex scripts + pentest guide — #34
- 🔴 META: Alpha Definition of Done — #1
