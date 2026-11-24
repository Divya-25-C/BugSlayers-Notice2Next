# Notice2Next

**Bug Slayers · Track 1: Make MCP Matter — Less Magic, More Utility**

Notice2Next turns campus notices into personal reminders while keeping each reminder linked to the source evidence. This hackathon MVP accepts text-based PDF notices or pasted text, finds possible dates, and lets a student review a reminder draft before saving it to a local demo calendar.

## What works in this MVP

- Extracts text and page numbers from PDFs with pypdf, or accepts pasted/plain text.
- Finds date mentions and shows the sentence and page where each date appeared.
- Leaves the year blank when the notice does not state one, so the student can choose it.
- Requires review and approval before saving a reminder in browser local storage.
- Provides the MCP tools find_notice_dates and draft_reminder over stdio. They return suggestions and drafts; they do not write to a calendar.
- Supports optional ElevenLabs speech-to-text and text-to-speech through server-side API calls. The key stays on the local server.

## Run locally

Requires Python 3.11 or newer. Run commands from the project root: the cloned BugSlayers-Notice2Next folder, or the notice2next-mvp folder from the supplied ZIP.

### Windows PowerShell

If you cloned from GitHub, first change into the repository folder with cd BugSlayers-Notice2Next. If you extracted the ZIP, open PowerShell in the extracted notice2next-mvp folder instead.

~~~powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python server.py
~~~

Open http://127.0.0.1:8000. Use Load sample to try the fictional Project Expo notice, inspect each excerpt, add a year if needed, and approve a reminder to see it in the demo calendar.

### macOS or Linux

From the cloned repository or extracted project folder, run:

~~~bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
python server.py
~~~

## Optional ElevenLabs voice

Add your own key and voice ID to your local .env file. Never commit that file.

~~~text
ELEVENLABS_API_KEY=your_key_here
ELEVENLABS_VOICE_ID=your_voice_id_here
~~~

Restart python server.py. Transcription is available when the API key exists; speech output also needs a voice ID. Without credentials, the PDF and text workflows still work.

## MCP tools

Install requirements, then run mcp_server.py using the stdio transport. Example MCP host configuration:

~~~json
{
  "mcpServers": {
    "notice2next": {
      "command": "python",
      "args": ["/absolute/path/to/project-root/mcp_server.py"]
    }
  }
}
~~~

The available tools are find_notice_dates(text) and draft_reminder(title, date_value, source_page, evidence). For MCP Inspector, run mcp dev mcp_server.py after installing requirements.

## Design limits

- This is a rules-based proof of concept, not an LLM. It may miss unusual date formats or find irrelevant dates; inspect source evidence before approving.
- Scanned/image-only PDFs need OCR, which is not included.
- The demo calendar uses browser local storage and does not connect to Google Calendar or another external calendar.
- Notice files are processed in memory. The app binds to 127.0.0.1; do not expose this development server to the public internet.
- The sample notice is fictional.

## References

- [Official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- [ElevenLabs speech-to-text API](https://elevenlabs.io/docs/api-reference/speech-to-text/convert)
- [ElevenLabs text-to-speech API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
