"""A minimal RESP server so the unmodified PayLock can run against a *network* store.

Why: in the in-memory mode the two awaits inside /v1/unlock resolve as microtasks, so the
handler never yields to another request and the check-then-set looks atomic. Against a real
Redis every await is a socket round trip, which is the situation in production. This shim
adds ~6 ms per command to make that window visible and measurable.

It supports exactly the commands platform.js uses, nothing more.
"""
from __future__ import annotations

import asyncio
import sys

STORE: dict[str, str] = {}
DELAY = 0.006


def encode(value) -> bytes:
    if value is None:
        return b"$-1\r\n"
    if isinstance(value, int):
        return f":{value}\r\n".encode()
    if isinstance(value, str) and value in ("PONG", "OK"):
        return f"+{value}\r\n".encode()
    data = value.encode() if isinstance(value, str) else value
    return b"$%d\r\n%s\r\n" % (len(data), data)


async def handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    while True:
        try:
            line = await reader.readline()
            if not line:
                break
            if not line.startswith(b"*"):
                writer.write(b"-ERR protocol\r\n")
                await writer.drain()
                continue
            n = int(line[1:].strip())
            args = []
            for _ in range(n):
                hdr = await reader.readline()
                ln = int(hdr[1:].strip())
                payload = await reader.readexactly(ln + 2)
                args.append(payload[:-2].decode())
            await asyncio.sleep(DELAY)
            cmd = args[0].lower()
            out = None
            if cmd == "ping":
                out = encode("PONG")
            elif cmd == "get":
                out = encode(STORE.get(args[1]))
            elif cmd == "set":
                key, val = args[1], args[2]
                nx = any(a.lower() == "nx" for a in args[3:])
                if nx and key in STORE:
                    out = encode(None)
                else:
                    STORE[key] = val
                    out = encode("OK")
            elif cmd == "del":
                STORE.pop(args[1], None)
                out = encode(1)
            elif cmd == "incr":
                nxt = int(STORE.get(args[1], "0")) + 1
                STORE[args[1]] = str(nxt)
                out = encode(nxt)
            elif cmd == "rpush":
                STORE.setdefault(args[1], "[]")
                out = encode(1)
            else:                       # info, client, command, hello...
                out = encode("OK")
            writer.write(out)
            await writer.drain()
        except Exception:  # noqa: BLE001
            break
    writer.close()


async def main(port: int):
    server = await asyncio.start_server(handle, "127.0.0.1", port)
    print(f"miniredis on {port}", flush=True)
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 6391))
