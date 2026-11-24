# Notice2Next

**Bug Slayers · Track 1: Make MCP Matter — Less Magic, More Utility**

Notice2Next is a local proof of concept for turning campus notices into personal reminders that keep their source evidence attached. Upload a text-based PDF or paste a notice, review candidate dates and excerpts, edit a reminder, and approve it into a browser-only demo calendar.

## What works in this MVP

- Reads text from PDFs with page numbers using `pypdf`, or accepts pasted/plain text.
- Finds date mentions and presents the containing source sentence and page.
- Keeps date parsing conservative. A date without an explicit year stays blank so the student can choose the right year.
- Requires a student to review and approve a reminder before saving it to local browser storage.
- Exposes `find_notice_dates` and `draft_reminder` as MCP tools over stdio. The MCP server returns suggestions and drafts; it never writes to a calendar.
- Supports optional ElevenLabs speech-to-text and text-to-speech through server-side API calls. Audio or text is sent only after the user confirms. The API key stays on the local server.

## Run locally

Requires Python 3.11 or newer.

### Windows PowerShell

```powershell
cd notice2next-mvp
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python server.py
```

Open <http://127.0.0.1:8000>.

### macOS or Linux

```bash
cd notice2next-mvp
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python server.py
```

Use **Load sample** to try the fictional Project Expo notice. Check each excerpt, enter a year if needed, and approve a reminder to see it in the demo calendar.

## Optional ElevenLabs voice

Add your key and voice ID to the local `.env` file:

```text
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
```

Restart `python server.py`. The app enables ElevenLabs transcription when the API key exists and ElevenLabs speech when both values exist. It asks before sending each recording or excerpt. Without the key, PDF and text workflows still run.

## MCP tools

The server uses the official Python MCP SDK and the local stdio transport. Add it to an MCP host using the command and file path for your machine:

```json
{
  "mcpServers": {
    "notice2next": {
      "command": "python",
      "args": ["/absolute/path/to/notice2next-mvp/mcp_server.py"]
    }
  }
}
```

The tools are:

- `find_notice_dates(text)`: returns date candidates with evidence excerpts.
- `draft_reminder(title, date_value, source_page, evidence)`: validates a date and returns a draft with no calendar side effect.

For the MCP Inspector, run `mcp dev mcp_server.py` after installing the requirements.

## Design and limits

- This is a rules-based demo, not an LLM. It can miss unusual date formats and may surface irrelevant date mentions. Always inspect the source before approving.
- Scanned/image-only PDFs need OCR, which this MVP does not include.
- The demo calendar uses browser local storage. It does not connect to Google Calendar or another external calendar.
- Notice files are processed in memory and are not written to disk. The app binds to `127.0.0.1`; do not expose this development server to the public internet.
- The sample notice is fictional.

## References

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [ElevenLabs speech-to-text API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
- [ElevenLabs text-to-speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
