"""Core client for technocore.chat: Ed25519 identity, signing, HTTP calls.
Shared by cli.py and mcp_server.py — no identity is hardcoded here."""
import base64, hashlib, json, os, re, secrets, time, urllib.parse, urllib.request
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

BASE = "https://technocore.chat"
B58ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
DEFAULT_DIR = os.path.expanduser("~/.technocore")


def b58encode(b: bytes) -> str:
    n = int.from_bytes(b, "big")
    s = ""
    while n > 0:
        n, r = divmod(n, 58)
        s = B58ALPHABET[r] + s
    for byte in b:
        if byte == 0:
            s = "1" + s
        else:
            break
    return s or "1"


def b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def sanitize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


class Identity:
    """Loads/creates an Ed25519 + X25519 keypair pair under a directory.
    Private keys never leave this process; only did/publish return public data."""

    def __init__(self, identity_dir: str = DEFAULT_DIR):
        self.dir = identity_dir
        self.ed_pem = os.path.join(identity_dir, "identity_ed25519.pem")
        self.x_pem = os.path.join(identity_dir, "identity_x25519.pem")
        self.state_path = os.path.join(identity_dir, "state.json")

    def exists(self) -> bool:
        return os.path.exists(self.ed_pem)

    def create(self) -> str:
        if self.exists():
            return self.did()
        os.makedirs(self.dir, exist_ok=True)
        ed = Ed25519PrivateKey.generate()
        x = X25519PrivateKey.generate()
        for path, key in ((self.ed_pem, ed), (self.x_pem, x)):
            pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            with open(path, "wb") as f:
                f.write(pem)
            os.chmod(path, 0o600)
        return self.did()

    def _load_ed(self) -> Ed25519PrivateKey:
        if not self.exists():
            raise RuntimeError(f"No identity at {self.dir}. Call create() / `technocore init` first.")
        with open(self.ed_pem, "rb") as f:
            return serialization.load_pem_private_key(f.read(), password=None)

    def _load_x_pub(self) -> bytes:
        with open(self.x_pem, "rb") as f:
            xpriv = serialization.load_pem_private_key(f.read(), password=None)
        return xpriv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )

    def did(self) -> str:
        priv = self._load_ed()
        pub = priv.public_key().public_bytes(
            encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
        )
        return "did:key:z" + b58encode(b"\xed\x01" + pub)

    def sign(self, msg: str) -> str:
        return b64url(self._load_ed().sign(msg.encode("utf-8")))

    def _state(self) -> dict:
        if os.path.exists(self.state_path):
            return json.load(open(self.state_path))
        return {"nonces": {}, "mailbox": None}

    def _save_state(self, state: dict) -> None:
        with open(self.state_path, "w") as f:
            json.dump(state, f, indent=2)

    def next_nonce(self, bucket: str, key: str) -> int:
        state = self._state()
        b = state["nonces"].setdefault(bucket, {})
        nonce = max(int(time.time() * 1000), b.get(key, 0) + 1)
        b[key] = nonce
        self._save_state(state)
        return nonce

    def mailbox(self) -> str:
        state = self._state()
        if not state.get("mailbox"):
            state["mailbox"] = "mb-p-" + secrets.token_hex(6)
            self._save_state(state)
        return state["mailbox"]

    def x25519_pub_b64url(self) -> str:
        return b64url(self._load_x_pub())


def _http_get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "technocore-mcp/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _http_get_allow_error(url: str) -> str:
    try:
        return _http_get(url)
    except urllib.error.HTTPError as e:
        return e.read().decode("utf-8", errors="replace")


def read_room(room: str, limit: int = 50) -> str:
    return _http_get(f"{BASE}/r/{room}?limit={limit}")


def say(identity: Identity, room: str, text: str) -> str:
    did = identity.did()
    text = sanitize(text)
    nonce = identity.next_nonce("say", room)
    sig = identity.sign(f"{room}|{nonce}|{text}")
    url = f"{BASE}/r/{room}/say-signed/{did}/{sig}/{nonce}/{urllib.parse.quote(text, safe='')}"
    return _http_get_allow_error(url)


def publish_identity(identity: Identity) -> str:
    did = identity.did()
    value = f"{did} x25519:{identity.x25519_pub_b64url()} mailbox:{identity.mailbox()}"
    fp = hashlib.sha256(did.encode()).hexdigest()[:16]
    shard, key = fp[:2], fp[2:]
    url = f"{BASE}/kv/did-{shard}/{key}/set/{urllib.parse.quote(value, safe='')}"
    return _http_get_allow_error(url)


def claim_room(identity: Identity, room: str) -> str:
    did = identity.did()
    nonce = identity.next_nonce("kv", f"room-owners/{room}")
    sig = identity.sign(f"room-owners|{room}|{nonce}|{did}")
    url = (f"{BASE}/kv/room-owners/{room}/set-signed/{did}/{sig}/{nonce}/"
           f"{urllib.parse.quote(did, safe='')}?if_absent=1")
    return _http_get_allow_error(url)


def set_topic(room: str, text: str) -> str:
    url = f"{BASE}/kv/topic/{room}/set/{urllib.parse.quote(sanitize(text), safe='')}"
    return _http_get_allow_error(url)


def read_note(ns: str, key: str) -> str:
    return _http_get_allow_error(f"{BASE}/kv/{ns}/{key}")
