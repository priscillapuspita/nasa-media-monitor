# Streamlit Community Cloud Deployment

Follow these steps to deploy the NASA Media Monitor dashboard on Streamlit Community Cloud.

## 1. Prepare The Repository

Make sure your latest code is pushed to GitHub:

```bash
git status
git push origin main
```

The dashboard entry point is:

```text
streamlit_dashboard.py
```

## 2. Create The Streamlit App

1. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Sign in with GitHub.
3. Click **Create app**.
4. Choose **Deploy a public app from GitHub**.
5. Select the repository:

```text
priscillapuspita/nasa-media-monitor
```

6. Set the branch:

```text
main
```

7. Set the main file path:

```text
streamlit_dashboard.py
```

## 3. Paste Secrets

Before clicking deploy, open the **Advanced settings** section.

Paste the contents of `.streamlit/secrets.toml.example` into the **Secrets** text box, then replace every placeholder value with your real credentials:

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

Do not paste your local `.env` file into GitHub. Streamlit secrets are stored in the Streamlit Cloud app settings, not in the repository.

## 4. Deploy

Click **Deploy**.

Streamlit Cloud will install dependencies from:

```text
requirements.txt
```

Then it will launch:

```text
streamlit_dashboard.py
```

## 5. Verify

After deployment:

1. Open the deployed app URL.
2. Confirm the dashboard loads without a missing-secret error.
3. Check that charts populate from the PostgreSQL `mentions` table.
4. If the dashboard is empty, run ingestion and sentiment locally or through your preferred scheduled job.

## Notes

Streamlit Community Cloud runs the dashboard, but it does not automatically run the ingestion, sentiment, or alert scheduler scripts. Run these separately:

```bash
python ingest_mentions.py
python sentiment_analysis.py
python alerting.py --once --dry-run
```
