# 🪙 Poker Chip Counter

A Streamlit app to track poker chips across rounds.

- Set the value of 1 chip in ₹, the number of players, and starting chips
- Each round: enter chips each player put in, pick the winner
- Winner gets the whole pot; others lose what they put in
- Standings with ₹ values, round history + chart, rebuy, undo, reset

> Game data is kept in the browser session only. Refreshing the page starts over.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy (Streamlit Community Cloud)

1. Push this folder to a GitHub repo
2. Go to share.streamlit.io, click **Create app**
3. Pick the repo, branch `main`, main file `streamlit_app.py`
4. Click **Deploy**
