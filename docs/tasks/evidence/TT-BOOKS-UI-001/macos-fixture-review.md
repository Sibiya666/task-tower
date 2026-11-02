# Independent macOS fixture correction acceptance

2026-11-02. CI41397503371 at5b90ff4 passed Ubuntu/Windows but failed macOS: test_canonical_connections_projection_publishes_before_blocked_verifier never entered its verifier barrier (455tests51.643s, one failure, six skips). The positive temporary config traversed macOS /var alias and was correctly rejected by the unchanged production safe-config guard.

Implementer independently reproduced the exact failure with an isolated temporary Windows junction: original test failed entered.wait(5), snapshot unavailable before proof; canonicalized root passed the same probe. This is author evidence, not coordinator-run alias reproduction.

Coordinator reviewed the complete minimal test diff and independently ran tests.test_overlay_books:9tests0.150s, OK. ACCEPT test-only correction raw/LF SHA256 d4e5230965fe67143aac738d01550dc5c0778bc022de7a3588015dcf387657d9. Actual config and checkout use the canonical root; privacy assertion now checks that actual root. Verifier entry/barrier ordering, pending/final verification assertions and timeouts remain unchanged. No production guard or skip changed. Remote macOS rerun remains required; this artifact grants no whole test-stage acceptance.
