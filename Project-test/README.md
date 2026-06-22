# Machine Insight MML Studio

Streamlit prototype for machine analysis, maintenance tracking, Excel reports, and an AI assistant.

## Demo credentials

- Admin: `admin` / `admin123`
- User: `user` / `user123`

## What is included

- Role-based login with admin and user permissions.
- Unique machine IDs generated automatically.
- Telemetry scoring for machine-risk analysis.
- Maintenance logging and scheduling.
- Excel export for machines, telemetry, maintenance, and users.
- AI assistant with optional OpenAI support and local fallback guidance.
- HTML, CSS, and JavaScript frontend shell for the future standalone app.

## Run the Streamlit prototype

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy on Streamlit Cloud

1. Push this folder to a GitHub repository.
2. In Streamlit Cloud, choose the repository and set the main file path to `app.py`.
3. Keep [runtime.txt](runtime.txt) in the repo so Streamlit Cloud uses Python 3.11 (avoids Python 3.14 build failures).
4. Make sure the installed packages come from [requirements.txt](requirements.txt).
5. Add secrets only if you want the optional OpenAI assistant, then set `OPENAI_API_KEY` in Streamlit Cloud secrets.
6. After pushing changes, click Reboot app in Streamlit Cloud.

The app is already configured to run locally with SQLite, so no extra database setup is required for the first cloud test.

## Access database note

The prototype runs on SQLite for Streamlit testing. The storage layer also includes an Access-ready backend switch:

- Set `APP_DB_BACKEND=access`
- Set `APP_ACCESS_DB_PATH` to your `.accdb` file
- Use a Windows environment with the Microsoft Access ODBC driver installed

That keeps the current build testable in Streamlit while leaving room for a separate Windows app that uses Microsoft Access directly.

## Separate app later

When you move past the Streamlit proof of concept, the next step is a standalone app in C# or another desktop/web stack that reuses the same data rules, user roles, and report logic.
