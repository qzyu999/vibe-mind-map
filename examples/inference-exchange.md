# Inference Exchange Vision

## Confidential Inference
- Consumer encrypts locally before sending — #29
- Coordinator is a blind relay — #21, #28
- Provider decrypts in hardened process
  - macOS L2: PT_DENY_ATTACH + Hardened Runtime + SIP — #3, #8
  - Future: AMD SEV-SNP for Linux providers
- Provider identity verified via App Attest — #19, #22
  - Requires $99/yr Apple Developer enrollment
  - Deferred to Beta

## Matching Engine
- Multi-dimensional scoring: price, speed, trust, load
- Consumer preferences: cheapest / fastest / most_secure / balanced
- Session affinity for KV cache hits — #33
- Context-aware routing — #32
- Hardware benchmark before admission — #36

## Provider Economics
- Providers set own prices ($/Mtok)
- 90/10 split (provider earns 90%, platform 10%)
- Electricity cost modeling — #31
- Cheaper than OpenAI for small open-weight models
- TPS tracking with anomaly detection

## Security Architecture
- PCC-inspired five principles (see pcc-comparison.md)
  - Stateless computation — not yet enforced
  - Enforceable guarantees — Hardened Runtime + SIP
  - No privileged runtime access — #21 done
  - Non-targetability — needs App Attest
  - Verifiable transparency — open source, no reproducible builds yet
- L2 threat model — docs/security/threat-model.md
- Alpha protocol spec — docs/security/alpha-protocol-spec.md
- Vulnerability reporting — SECURITY.md

## What Makes This Different
- **Not** a centralized API (OpenAI, Anthropic)
- **Not** a router/aggregator (OpenRouter, LiteLLM)
- Actual E2E encryption — coordinator mathematically cannot read prompts
- Providers are independent operators, not our servers
- Open source protocol (OCIP)

## Alpha Readiness
- E2E encryption validated on hardware (Intel MBP → M2 MBP)
- Getting-started guide needed — #15
- Known limitations doc needed — #16
- Pentest guide + devex scripts — #34
- L2 self-test — #3
- Log audit for plaintext leakage — #7
