from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from email.parser import BytesParser
from email.policy import default
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from analysis import analyze_pages, analyze_text

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "static"
MAX_BODY = 8 * 1024 * 1024
MAX_PAGES = 30


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def _elevenlabs_enabled() -> tuple[bool, bool]:
    has_key = bool(os.environ.get("ELEVENLABS_API_KEY"))
    has_voice = bool(os.environ.get("ELEVENLABS_VOICE_ID"))
    return has_key, has_key and has_voice


def _parse_multipart(content_type: str, body: bytes) -> dict[str, tuple[str, bytes]]:
    headers = f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode("utf-8")
    message = BytesParser(policy=default).parsebytes(headers + body)
    fields: dict[str, tuple[str, bytes]] = {}
    if not message.is_multipart():
        raise ValueError("Expected a multipart form upload.")
    for part in message.iter_parts():
        name = part.get_param("name", header="content-disposition")
        if not name:
            continue
        filename = part.get_filename() or ""
        payload = part.get_payload(decode=True) or b""
        fields[name] = (filename, payload)
    return fields


def _extract_pages(filename: str, payload: bytes) -> list[str]:
    if not payload:
        raise ValueError("The selected file is empty.")
    suffix = Path(filename).suffix.casefold()
    if suffix == ".pdf" or payload.startswith(b"%PDF"):
        reader = PdfReader(__import__("io").BytesIO(payload), strict=False)
        if len(reader.pages) > MAX_PAGES:
            raise ValueError(f"This demo accepts up to {MAX_PAGES} pages at a time.")
        return [page.extract_text() or "" for page in reader.pages]
    if suffix in (".txt", ".md") or not suffix:
        return [payload.decode("utf-8-sig", errors="replace")]
    raise ValueError("Upload a PDF or a plain-text file.")


def _elevenlabs_transcribe(filename: str, payload: bytes) -> str:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        raise RuntimeError("Add ELEVENLABS_API_KEY to .env to enable ElevenLabs transcription.")
    boundary = "----Notice2NextBoundary7MA4YWxkTrZu0gW"
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", Path(filename).name) or "question.webm"
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"model_id\"\r\n\r\nscribe_v2\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{safe_name}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + payload + f"\r\n--{boundary}--\r\n".encode("utf-8")
    request = urllib.request.Request(
        "https://api.elevenlabs.io/v1/speech-to-text",
        data=body,
        headers={"xi-api-key": api_key, "Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        raise RuntimeError(f"ElevenLabs transcription returned {exc.code}: {detail}") from exc
    return str(result.get("text", "")).strip()


def _elevenlabs_speak(text: str) -> bytes:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    voice_id = os.environ.get("ELEVENLABS_VOICE_ID")
    if not api_key or not voice_id:
        raise RuntimeError("Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID in .env to enable ElevenLabs speech.")
    voice = urllib.parse.quote(voice_id, safe="")
    payload = json.dumps({"text": text[:1200], "model_id": "eleven_multilingual_v2"}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice}?output_format=mp3_44100_128",
        data=payload,
        headers={"xi-api-key": api_key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=35) as response:
            return response.read(4 * 1024 * 1024)
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", errors="replace")
        raise RuntimeError(f"ElevenLabs speech returned {exc.code}: {detail}") from exc


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, directory=str(STATIC), **kwargs)

    def _json(self, status: int, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:
        if self.path == "/api/health":
            stt, tts = _elevenlabs_enabled()
            self._json(200, {"ok": True, "elevenlabs_stt": stt, "elevenlabs_tts": tts})
            return
        super().do_GET()

    def do_POST(self) -> None:
        if self.path not in ("/api/analyze", "/api/voice/transcribe", "/api/voice/speak"):
            self._json(404, {"error": "Route not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._json(400, {"error": "Invalid request length."})
            return
        if length < 1 or length > MAX_BODY:
            self._json(413, {"error": "Request is empty or larger than the 8 MB demo limit."})
            return
        body = self.rfile.read(length)
        try:
            if self.path == "/api/analyze":
                self._handle_analyze(body)
            elif self.path == "/api/voice/transcribe":
                fields = _parse_multipart(self.headers.get("Content-Type", ""), body)
                filename, audio = fields.get("audio", ("question.webm", b""))
                transcript = _elevenlabs_transcribe(filename, audio)
                self._json(200, {"text": transcript})
            else:
                payload = json.loads(body.decode("utf-8"))
                text = str(payload.get("text", "")).strip()
                if not text or len(text) > 1200:
                    raise ValueError("Provide a short summary to read aloud (1-1,200 characters).")
                audio = _elevenlabs_speak(text)
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(audio)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(audio)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
        except RuntimeError as exc:
            self._json(503, {"error": str(exc)})
        except Exception as exc:
            self._json(500, {"error": f"Could not process this request: {exc}"})

    def _handle_analyze(self, body: bytes) -> None:
        content_type = self.headers.get("Content-Type", "")
        if content_type.startswith("multipart/form-data"):
            fields = _parse_multipart(content_type, body)
            filename, payload = fields.get("file", ("", b""))
            pasted_text = fields.get("text", ("", b""))[1].decode("utf-8", errors="replace").strip()
            if payload:
                result = analyze_pages(_extract_pages(filename, payload))
                result["filename"] = Path(filename).name or "Uploaded notice"
            elif pasted_text:
                result = analyze_text(pasted_text)
                result["filename"] = "Pasted notice text"
            else:
                raise ValueError("Choose a PDF or paste notice text first.")
        elif content_type.startswith("application/json"):
            payload = json.loads(body.decode("utf-8"))
            text = str(payload.get("text", "")).strip()
            if not text:
                raise ValueError("Paste notice text or upload a PDF.")
            if len(text) > 100_000:
                raise ValueError("Pasted text is larger than the 100,000 character limit.")
            result = analyze_text(text)
            result["filename"] = "Pasted notice text"
        else:
            raise ValueError("Use the upload form or paste notice text.")
        self._json(200, result)


def main() -> None:
    load_dotenv()
    host = "127.0.0.1"
    port = int(os.environ.get("NOTICE2NEXT_PORT", "8000"))
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Notice2Next is running at http://{host}:{port}")
    print("Uploaded notices are processed in memory and are not saved by the app.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
