# Local API keys

Open `.env` in this project and paste your Twelve Data key after `TWELVE_DATA_API_KEY=`. Save the file, then restart the backend:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend:create_app --factory --host 127.0.0.1 --port 8000
```

The backend, `python main.py`, and dataset CLI load this file automatically from the project directory, regardless of the terminal's working directory. No extra dependency is required. There is no need to set the key in PowerShell each time. Existing environment variables take precedence, including empty ones; remove an old terminal override if you want the file's value to apply. Restart after editing keys. Keys are never loaded by browser JavaScript.

For optional AI recommendations, fill in both `OPENAI_API_KEY` and `OPENAI_MODEL`. The stock feature only needs `TWELVE_DATA_API_KEY`.

Supported format: one literal `NAME=value` per line, blank lines, whole-line `#` comments, and optional matching quotes around a value. No inline comments, variable expansion or multiline values. Only the three names in `.env.example` are loaded. Blank entries are ignored.

`.env` and `.env.*` are excluded by Git; `.env.example` is an empty, shareable template. Do not put real keys in the template or share `.env`. Git ignores do not encrypt files or prevent OneDrive syncing the project folder. The backend only serves `static/`, so `.env` is outside the web-served directory.
