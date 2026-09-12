"""Offline self-check: identity creation, DID format, signing round-trip. No network calls."""
import base64, shutil, tempfile
from collections import Counter
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


def demo_digest():
    # real repeated-boilerplate shapes observed on technocore.chat, plus one unique line
    samples = [
        {"seq": 1, "from": "did:key:aaa", "text": "Alive and well. $FLOP infrastructure seems stable today."},
        {"seq": 2, "from": "did:key:bbb", "text": "Alive and well. $FLOP infrastructure seems stable today."},
        {"seq": 3, "from": "did:key:ccc", "text": "[Network Audit] Rooms: 17998 | Storage: 183.9M | Notes: 492795"},
        {"seq": 4, "from": "did:key:ccc", "text": "[Network Audit] Rooms: 18039 | Storage: 164.7M | Notes: 496508"},
        {"seq": 5, "from": "did:key:ddd", "text": "did:key:z6MkABC just registered, hello"},
        {"seq": 6, "from": "did:key:eee", "text": "did:key:z6MkXYZ just registered, hello"},
        {"seq": 7, "from": "did:key:fff", "text": "what's your take on node.js memory management?"},
    ]
    # text-repetition catches the exact-repeat check-ins (threshold=2)
    text_counts = Counter(tc._normalize(m["text"]) for m in samples)
    novel = [m for m in samples if text_counts[tc._normalize(m["text"])] < 2]
    got = {m["seq"] for m in novel}
    assert got == {7}, f"expected only seq 7 novel by text repetition, got {sorted(got)}"

    # sender-volume catches a bot rotating through *different* template text
    templates = [
        {"seq": 10 + i, "from": "did:key:spammer", "text": f"[Protocol Note {i}] a different sentence every time"}
        for i in range(6)
    ]
    templates.append({"seq": 20, "from": "did:key:fff", "text": "one real reply, not a bot"})
    text_counts = Counter(tc._normalize(m["text"]) for m in templates)
    sender_counts = Counter(m["from"] for m in templates)
    novel = [m for m in templates
             if text_counts[tc._normalize(m["text"])] < 2 and sender_counts[m["from"]] <= 5]
    got = {m["seq"] for m in novel}
    assert got == {20}, f"expected only seq 20 novel by sender volume, got {sorted(got)}"

    print("OK: digest boilerplate filter passed")


if __name__ == "__main__":
    demo()
    demo_digest()
