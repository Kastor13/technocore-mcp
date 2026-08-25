"""Offline self-check: identity creation, DID format, signing round-trip. No network calls."""
import base64, shutil, tempfile
import technocore as tc


def demo():
    tmp = tempfile.mkdtemp()
    try:
        identity = tc.Identity(tmp)
        did = identity.create()
        assert did.startswith("did:key:z6Mk"), f"bad DID prefix: {did}"
        assert did == identity.did(), "DID not stable across calls"

        sig = identity.sign("lobby|123|hello world")
        raw = base64.urlsafe_b64decode(sig + "==")
        assert len(raw) == 64, f"Ed25519 signature must be 64 bytes, got {len(raw)}"
        assert "=" not in sig, "signature must be unpadded base64url"

        assert tc.sanitize("hello\n\nworld  \t!") == "hello world !"

        n1 = identity.next_nonce("say", "lobby")
        n2 = identity.next_nonce("say", "lobby")
        assert n2 > n1, "nonce must be strictly increasing per (bucket, key)"

        # re-running create() must NOT rotate the key
        did_again = identity.create()
        assert did_again == did, "init must be idempotent — never rotate on re-run"

        print("OK: all smoke checks passed")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    demo()
