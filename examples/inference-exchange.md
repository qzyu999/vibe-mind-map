# Inference Exchange

## Coordinator ✅
- FastAPI app on port 8000
- WebSocket provider hub (connect/disconnect/heartbeat)
- Request queuing (50 depth, 30s timeout, FIFO dispatch)
- Rate limiting (30 rpm per API key, token bucket)
- CORS + CSRF middleware
- Health/readiness endpoints
- Routes split: inference, exchange, auth, admin, confidential, handshake

## Consumer SDK
- ConfidentialTransport ✅ — OpenAI SDK http_client plugin — #29
  - Encrypts messages locally (NaCl Box)
  - Includes consumer_public_key for response E2E
  - Decrypts encrypted response tokens
  - Session tracking (session_id + sequence number)
  - Fallback routing to OpenAI/OpenRouter (opt-in)
- ExchangeClient ✅ — thin REST wrapper for marketplace endpoints
- Legacy ie_sdk.py ✅ — standalone client, to be deprecated

## Confidential Inference
- Confidential relay endpoint ✅ — POST /v1/confidential/infer — #28
  - Rejects requests with messages field (400 plaintext_rejected)
  - Relays encrypted_envelope unchanged
  - Bills using estimated_input_tokens from metadata
- Coordinator blindness ✅ — validated on hardware — #21
  - Intel MBP coordinator sees only ciphertext
  - M2 MBP provider decrypts and runs inference
- Response E2E ✅ — provider encrypts tokens to consumer key
- Non-confidential path ✅ — /v1/chat/completions (coordinator encrypts)

## Matching Engine ✅
- GreedyStrategy (per-request, O(n×m))
- BatchAuctionStrategy (most-constrained-first, implemented but unused)
- Multi-dimensional scoring: price, speed, trust, load
- Weights by preference: cheapest/fastest/most_secure/balanced
- Reputation modifier (0.5 + 0.5 × rep)
- Session affinity (20% bonus, LRU 1000)
- Alpha improvements needed — #33
  - Cache-aware affinity (replace flat 20%)
  - Context length as hard filter — #32
  - Use observed TPS instead of self-reported

## Provider Architecture
- OCIP Agent ✅ (ocip_agent/agent.py)
  - Two-process: agent + isolated inference server
  - X25519 keypair per agent instance
  - WebSocket to coordinator (reconnect on disconnect)
  - Heartbeat loop (10s)
  - Health monitor + auto-restart (exponential backoff)
  - Request cancellation support
  - Attestation challenge-response
- Inference Server ✅ (ocip_server/server.py)
  - llama-cpp-python on localhost:9999 only
  - GGUF model loading + Metal/CPU inference
  - Streaming + non-streaming completions
  - /health and /identity endpoints
- Hardening (provider-hardened/)
  - PT_DENY_ATTACH ✅ (C module)
  - Core dump disabled ✅
  - SIP verification ✅
  - L2 self-test needed — #3
  - Runtime hardening validation needed — #8
  - Plaintext leakage audit needed — #7
- Model Identity ✅
  - GGUF metadata reader (name, arch, quantization, context length)
  - SHA-256 file hash
  - HuggingFace hash verification

## Security
- E2E Encryption
  - NaCl Box ✅ (X25519 + XSalsa20-Poly1305, per-request forward secrecy)
  - AES-256-GCM session primitives ✅ (merged, not wired into live path)
  - Ed25519 provider identity ✅ (merged, for future handshake)
- App Attest
  - Coordinator-side verifier ✅ (CBOR + X.509 validation) — #19
  - Native macOS client ❌ (needs $99/yr Apple Developer) — #22
  - Handshake schema ✅ (provider offers, transcript binding) — #25
- Attestation loop ✅ — challenge every 5min, 30s timeout, degraded state
- Threat model ✅ — docs/security/threat-model.md
- L2 threat model ✅ — docs/security/threat-model.md (security subfolder)
- PCC comparison ✅ — docs/security/pcc-comparison.md
- Alpha protocol spec ✅ — docs/security/alpha-protocol-spec.md
- SECURITY.md ✅ — vulnerability reporting process

## Billing ✅
- Micro-USD integer arithmetic (no floating point)
- 90/10 split (provider 90%, platform 10%)
- Minimum charge $0.0001 per request
- SQLite persistence (accounts, keys, transactions)
- Property-tested (1000 random events, books always balance)
- Confidential mode: trusts provider-reported token count
- Reference pricing (OpenRouter live API + OpenAI/Anthropic/Google)

## Persistence ✅
- SQLite WAL mode (~/.inference-exchange/exchange.db)
  - Accounts, API keys (SHA-256 hashed), billing, provider history, users
- Audit log (~/.inference-exchange/audit.jsonl)
  - Append-only, hash-chained (each entry chains to previous)
  - Records: billing, attestation, connect/disconnect

## Reputation + TPS ✅
- Reputation: EMA per provider (success/error/timeout/disconnect)
  - Composite: 0.7 × success_rate + 0.3 × latency_score
  - Degraded at <50% success after 5+ requests
- TPS tracker: EMA per (provider, model)
  - Hardware lookup table for initial estimates
  - Observed measurements after 3+ requests
  - Anomaly detection (latest < 50% of EMA)

## Web Dashboard ✅
- React 19 + Vite 8 (8 pages)
- Landing, Exchange (depth chart), Chat (streaming), Models (HF search)
- Providers, Billing, API Keys, Admin

## Alpha Readiness
- Getting-started guide needed — #15
- Known limitations doc needed — #16
- Devex scripts + pentest guide — #34
- E2E smoke test automation — #11
- Hardware benchmark before admission — #36
