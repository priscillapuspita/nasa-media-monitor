# Streamlit Secrets Deployment Checklist

Go to:

```text
https://share.streamlit.io
```

Create or edit the app, then open:

```text
Advanced Settings > Secrets
```

Paste the secrets in TOML format. Use `.streamlit/secrets.toml.example` as the template, then replace every placeholder with the real value.

## Secret Keys

- [ ] `DATABASE_URL`
- [ ] `NEWSAPI_KEY`
- [ ] `HUGGINGFACE_API_TOKEN`
- [ ] `REDDIT_CLIENT_ID`
- [ ] `REDDIT_CLIENT_SECRET`
- [ ] `REDDIT_USER_AGENT`
- [ ] `MENTION_QUERY`
- [ ] `TELEGRAM_BOT_TOKEN`
- [ ] `TELEGRAM_CHAT_ID`

## Paste Template

```toml
DATABASE_URL = "postgresql://username:password@host:5432/nasa_media_monitor"
NEWSAPI_KEY = "your_newsapi_key"
HUGGINGFACE_API_TOKEN = "your_huggingface_api_token"
REDDIT_CLIENT_ID = "your_reddit_client_id"
REDDIT_CLIENT_SECRET = "your_reddit_client_secret"
REDDIT_USER_AGENT = "nasa-media-monitor/0.1 by your_reddit_username"
MENTION_QUERY = "NASA OR Artemis OR \"James Webb\" OR \"Kennedy Space Center\" OR JPL"
TELEGRAM_BOT_TOKEN = "your_telegram_bot_token"
TELEGRAM_CHAT_ID = "your_telegram_chat_id"
```

Do not commit real secrets to GitHub.
