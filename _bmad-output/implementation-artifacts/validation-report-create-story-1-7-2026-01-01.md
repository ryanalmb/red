# Validation Report: Story 1-7-ca-key-storage

**Generated:** 2026-01-01
**Story:** 1.7 - CA Key Storage
**Validator:** create-story checklist validation

---

## Summary

| Category | Count |
|----------|-------|
| 🚨 Critical Issues | 2 |
| ⚡ Enhancements | 3 |
| ✨ Optimizations | 2 |

**Overall Assessment:** GOOD with minor improvements recommended

---

## 🚨 CRITICAL ISSUES (Must Fix)

### 1. Missing Test for 7-Day Certificate Expiry Warning

**Gap:** Architecture (line 106) specifies:
> "Warning at 7 days remaining. Block engagement start if <24h remaining"

**Current Story:** Only mentions 24-hour validation. Missing:
- `verify_cert_expiry_warning(cert) -> bool` that returns True if <7 days remaining
- Test case for 7-day warning threshold

**Fix:** Add to Task 4:
```
- [ ] Test `ca_store.get_cert_expiry_status(cert)` returns WARNING if <7 days remaining
- [ ] Test `ca_store.get_cert_expiry_status(cert)` returns BLOCKED if <24h remaining
```

---

### 2. Missing Certificate Serialization Methods

**Gap:** Story mentions saving encrypted CA key but doesn't specify methods for serializing end-entity certificates/keys to PEM for use by C2 server.

**Current Story:** `generate_cert()` returns tuple but no export methods.

**Fix:** Add to Task 7:
```
- [ ] Implement `serialize_cert_pem(cert) -> bytes` for certificate export
- [ ] Implement `serialize_key_pem(key, password=None) -> bytes` for key export
```

---

## ⚡ ENHANCEMENT OPPORTUNITIES (Should Add)

### 1. Add `c2/cert_manager.py` Integration Note

**Architecture Context:** Line 767 shows `c2/cert_manager.py — Certificate rotation` which will consume `CAStore`. Story should reference this dependency.

**Suggestion:** Add to Dev Notes:
```
### Downstream Consumers
- `c2/cert_manager.py` (Epic 12) will use CAStore for certificate rotation
- Ensure public API is stable for downstream consumption
```

---

### 2. Certificate Pinning Consideration

**Architecture Context:** Line 105 mentions "certificate pinning in binary" for drop boxes.

**Suggestion:** Add note that CA certificate must be exportable for embedding in Go binary:
```
### Certificate Pinning Support
- CA certificate public key must be exportable for embedding in drop box binaries
- Add `get_ca_public_key_bytes() -> bytes` for pinning support
```

---

### 3. Add Elapsed Time / Remaining Time Helper

**Pre-flight Check Need:** The CERT_CHECK needs to verify ">24h remaining" easily.

**Suggestion:** Add utility method:
```python
def get_remaining_validity(cert: x509.Certificate) -> timedelta
```

---

## ✨ OPTIMIZATIONS (Nice to Have)

### 1. Token Efficiency: Consolidate Code Examples

**Current:** 3 separate code blocks showing keystore usage, mTLS example, and pre-flight integration.

**Optimization:** Could merge into single comprehensive example.

---

### 2. Add SHA-256 Fingerprint Method

**Future Use:** For certificate pinning and logging, a fingerprint method would be useful:
```python
def get_cert_fingerprint(cert: x509.Certificate) -> str
```

---

## ✅ VALIDATION PASSED

The following requirements ARE properly covered:

- ✅ Story statement and acceptance criteria complete
- ✅ TDD methodology with RED-GREEN-REFACTOR phases
- ✅ All 7 acceptance criteria have corresponding test tasks
- ✅ Architecture references with line numbers
- ✅ Previous story patterns referenced (Story 1.6)
- ✅ Anti-patterns clearly documented
- ✅ Technical specifications for CA and end-entity certs
- ✅ mTLS extensions properly specified (ExtendedKeyUsage, KeyUsage, SAN)
- ✅ Library requirements (cryptography>=42.0.0)
- ✅ File structure matches architecture
- ✅ Dependency chain documented
- ✅ 100% coverage requirement stated
- ✅ Integration verification task included

---

## Recommendation

**Apply Critical Issues (2)** to ensure the story fully covers architecture requirements.

Enhancements and optimizations are nice-to-have but not blocking.
