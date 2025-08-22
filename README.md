# Human Bingo — v3

What's new:
1) **Readable student screen** — bingo cells now use light text on dark background.
2) **End Game button** — on admin page; purges all game data and returns to setup.
3) **Read-only preview** — admin page iframe now shows `/preview/<GAME_ID>` which renders the prompts grid and a live leaderboard without requiring a student to join.

## Local run
```
pip install -r requirements.txt
python server.py
```
Open http://localhost:5000/admin

## Deploy (Render)
- Build: `pip install -r requirements.txt`
- Start: `gunicorn -k eventlet -w 1 server:app`
- Python: `runtime.txt` → Python 3.11.9
