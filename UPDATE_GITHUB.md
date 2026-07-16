# Update the deployed app on GitHub

Use these labels exactly as they appear on an English-language GitHub page.

1. Open your `market-news-terminal` repository.
2. Click **Add file** → **Upload files**.
3. Drag every file and folder from this extracted V2 folder into the upload area.
4. When GitHub says files already exist, keep the new uploaded versions so they replace the old ones.
5. At the bottom, enter a message such as `Market News Terminal V2`.
6. Leave **Commit directly to the main branch** selected.
7. Click **Commit changes**.
8. Streamlit should detect the commit and redeploy automatically. Open **Manage app** if you need to watch the deployment logs.

Do not upload `.env`, `market_news.db`, or any file containing real API keys. Your existing Streamlit **Secrets** remain stored in Streamlit and do not need to be pasted again.
