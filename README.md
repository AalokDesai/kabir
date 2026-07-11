# Kabir

Kabir is a local Windows desktop assistant with voice input, text commands, face authentication, system controls, file search, memory/history, contacts, notifications, telemetry, and a browser-based Eel UI.

## Features

- Voice and text command interface
- Face authentication flow
- Local command and chat history
- File search and safe file opening
- Weather, news, web, media, and desktop automation commands
- Email, messaging, phone, and Spotify integrations
- Local settings, notifications, logs, and system telemetry panels
- Wake word support through Picovoice Porcupine

## Setup

1. Create and activate a virtual environment:
   ```powershell
   python -m venv venv
   .\venv\Scripts\Activate.ps1
   ```

2. Install dependencies:
   ```powershell
   pip install -r requirements.txt
   ```

3. Create local environment settings:
   ```powershell
   Copy-Item .env.example .env
   ```

4. Fill `.env` with your own keys where needed:
   - `OPENWEATHER_API_KEY` for weather.
   - `KABIR_PICOVOICE_ACCESS_KEY` for wake word detection.
   - `ADB_PATH` if ADB is not available on PATH.

5. Run Kabir:
   ```powershell
   python kabir.py
   ```

## Local Data and Privacy

This repository is configured for a public, code-only upload. Runtime data and private assets are intentionally ignored:

- `.env` secrets
- face-auth datasets and trained models
- local history database
- mail/contact/settings stores
- phone profile data
- logs
- personal PDFs and DOCX files
- virtual environment files

Do not commit real API keys, face images, trained biometric models, personal documents, logs, or local databases.

## GitHub Publishing Checklist

Before pushing publicly, run:

```powershell
git status --short
git diff --cached --name-only
git check-ignore -v .env
git check-ignore -v kabir_history.sqlite3
git check-ignore -v engine\phone_profile.json
git check-ignore -v engine\auth\dataset\users.json
git check-ignore -v engine\auth\trainer\trainer.yml
```

Only source code and safe documentation should be staged.
