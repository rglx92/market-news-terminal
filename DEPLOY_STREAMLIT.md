# Deploy or update Market News Terminal

## Existing deployed app

Use [`UPDATE_GITHUB.md`](UPDATE_GITHUB.md). Upload the new files to the existing repository and commit them to `main`. Streamlit will redeploy automatically.

## New deployment

1. Create a GitHub repository.
2. Upload the extracted project contents so `app.py` and `requirements.txt` are at the repository root.
3. In Streamlit Community Cloud choose **Deploy a public app from GitHub**.
4. Set:
   - **Repository:** your GitHub repository
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Put API keys in **Advanced settings** → **Secrets**.
6. Click **Deploy**.

Never commit `.env`, `.streamlit/secrets.toml`, or real API keys.
