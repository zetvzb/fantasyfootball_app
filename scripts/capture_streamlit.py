#!/usr/bin/env python3
"""Capture a fully rendered local Streamlit view through Chrome DevTools."""

import argparse
import base64
import json
import os
from pathlib import Path
import socket
import struct
import time
from urllib.parse import urlparse
from urllib.request import urlopen


class DevToolsSocket:
    def __init__(self, websocket_url):
        parsed = urlparse(websocket_url)
        self.socket = socket.create_connection((parsed.hostname, parsed.port), timeout=20)
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        path = parsed.path + (("?" + parsed.query) if parsed.query else "")
        request = (
            "GET {0} HTTP/1.1\r\n"
            "Host: {1}:{2}\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Key: {3}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(path, parsed.hostname, parsed.port, key)
        self.socket.sendall(request.encode("ascii"))
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.socket.recv(4096)
        if not response.startswith(b"HTTP/1.1 101"):
            raise RuntimeError("Chrome rejected the DevTools websocket handshake.")
        self.command_id = 0

    def _read_exact(self, length):
        payload = b""
        while len(payload) < length:
            chunk = self.socket.recv(length - len(payload))
            if not chunk:
                raise RuntimeError("Chrome closed the DevTools connection.")
            payload += chunk
        return payload

    def _receive_text(self):
        fragments = []
        while True:
            first, second = self._read_exact(2)
            opcode = first & 0x0F
            final = bool(first & 0x80)
            length = second & 0x7F
            if length == 126:
                length = struct.unpack("!H", self._read_exact(2))[0]
            elif length == 127:
                length = struct.unpack("!Q", self._read_exact(8))[0]
            masked = bool(second & 0x80)
            mask = self._read_exact(4) if masked else None
            payload = self._read_exact(length)
            if mask is not None:
                payload = bytes(
                    value ^ mask[index % 4] for index, value in enumerate(payload)
                )
            if opcode == 8:
                raise RuntimeError("Chrome closed the DevTools websocket.")
            if opcode in (1, 0):
                fragments.append(payload)
                if final:
                    return b"".join(fragments).decode("utf-8")

    def _send_text(self, text):
        payload = text.encode("utf-8")
        mask = os.urandom(4)
        length = len(payload)
        header = bytearray([0x81])
        if length < 126:
            header.append(0x80 | length)
        elif length < 65536:
            header.append(0x80 | 126)
            header.extend(struct.pack("!H", length))
        else:
            header.append(0x80 | 127)
            header.extend(struct.pack("!Q", length))
        masked = bytes(
            value ^ mask[index % 4] for index, value in enumerate(payload)
        )
        self.socket.sendall(bytes(header) + mask + masked)

    def command(self, method, params=None):
        self.command_id += 1
        command_id = self.command_id
        self._send_text(
            json.dumps(
                {"id": command_id, "method": method, "params": params or {}}
            )
        )
        while True:
            payload = json.loads(self._receive_text())
            if payload.get("id") == command_id:
                if "error" in payload:
                    raise RuntimeError(str(payload["error"]))
                return payload.get("result") or {}


def _page_websocket(port):
    with urlopen("http://127.0.0.1:{0}/json/list".format(port)) as response:
        targets = json.load(response)
    pages = [target for target in targets if target.get("type") == "page"]
    if not pages:
        raise RuntimeError("No Chrome page target is available.")
    return pages[0]["webSocketDebuggerUrl"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output")
    parser.add_argument("--port", type=int, default=9223)
    parser.add_argument("--click-text")
    parser.add_argument("--scroll-text")
    parser.add_argument("--wait", type=float, default=3.0)
    args = parser.parse_args()

    client = DevToolsSocket(_page_websocket(args.port))
    if args.click_text:
        expression = """
        (() => {
          const match = Array.from(document.querySelectorAll('label,button'))
            .find(node => node.innerText.includes(%s));
          if (!match) return false;
          match.click();
          return true;
        })()
        """ % json.dumps(args.click_text)
        client.command("Runtime.evaluate", {"expression": expression})
        time.sleep(args.wait)
    if args.scroll_text:
        expression = """
        (() => {
          const match = Array.from(document.querySelectorAll('h1,h2,h3,h4'))
            .find(node => node.innerText.includes(%s));
          if (!match) return false;
          match.scrollIntoView({block: 'start'});
          return true;
        })()
        """ % json.dumps(args.scroll_text)
        client.command("Runtime.evaluate", {"expression": expression})
        time.sleep(1.0)
    result = client.command(
        "Page.captureScreenshot",
        {"format": "png", "fromSurface": True, "captureBeyondViewport": False},
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(base64.b64decode(result["data"]))
    print("Captured {0}".format(output))


if __name__ == "__main__":
    main()
