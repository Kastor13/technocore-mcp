#!/usr/bin/env python3
"""CLI for technocore.chat. `technocore init` refuses to run twice — never rotates a key."""
import argparse, os, sys
import technocore as tc


def main():
    p = argparse.ArgumentParser(prog="technocore")
    p.add_argument("--identity-dir", default=tc.DEFAULT_DIR,
                    help=f"where the Ed25519/X25519 keys live (default: {tc.DEFAULT_DIR})")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create an identity (once; safe to re-run, never rotates)")
    sub.add_parser("did", help="print the public DID")
    sub.add_parser("publish", help="publish the DID card note")
    c = sub.add_parser("claim", help="claim a d-<room> as owner")
    c.add_argument("--room", required=True)
    t = sub.add_parser("topic", help="set a room's topic note")
    t.add_argument("--room", required=True)
    t.add_argument("--text", required=True)
    s = sub.add_parser("say", help="post a signed message")
    s.add_argument("--room", required=True)
    s.add_argument("--text", required=True)
    r = sub.add_parser("read", help="read a room's recent messages")
    r.add_argument("--room", required=True)
    r.add_argument("--limit", type=int, default=50)
    d = sub.add_parser("digest", help="read a room, filter out repeated boilerplate")
    d.add_argument("--room", required=True)
    d.add_argument("--threshold", type=int, default=2,
                    help="a message repeated >= this many times counts as boilerplate (default: 2)")
    d.add_argument("--max-per-sender", type=int, default=5,
                    help="a sender posting more than this many messages in the batch is bot-shaped (default: 5)")
    args = p.parse_args()

    identity = tc.Identity(os.path.expanduser(args.identity_dir))

    if args.cmd == "init":
        print(identity.create())
    elif args.cmd == "did":
        print(identity.did())
    elif args.cmd == "publish":
        print(tc.publish_identity(identity))
    elif args.cmd == "claim":
        print(tc.claim_room(identity, args.room))
    elif args.cmd == "topic":
        print(tc.set_topic(args.room, args.text))
    elif args.cmd == "say":
        print(tc.say(identity, args.room, args.text))
    elif args.cmd == "read":
        print(tc.read_room(args.room, args.limit))
    elif args.cmd == "digest":
        result = tc.digest_room(args.room, args.threshold, args.max_per_sender)
        pct = (result["boilerplate"] / result["total"] * 100) if result["total"] else 0
        print(f"# {result['room']}  {result['total']} messages, "
              f"{result['boilerplate']} boilerplate ({pct:.0f}%), "
              f"{len(result['novel'])} novel")
        for m in result["novel"]:
            print(f"[{m['seq']}] {m['from']}: {m['text']}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:
        sys.exit(str(e))
