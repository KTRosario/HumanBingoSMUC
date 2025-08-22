# Human Bingo (Python • Flask • Socket.IO)

Mobile-friendly Human Bingo for classrooms. Students join via a game code or QR, tap squares as they meet classmates, and a live leaderboard updates in real time.

## Features
- Create a game with your own prompts (admin page)
- Students join on phones (no install) using a code or QR
- Real-time leaderboard via WebSockets
- Simple SQLite storage (no external DB needed)
- Ready for local use or cloud deploy (Render/Railway/Fly/Heroku-like)

---

## 1) Run locally (Mac/Windows/Linux)

```bash
# 0) cd into the folder
cd human-bingo

# 1) (optional) Create a venv
python -m venv .venv && source .venv/bin/activate  # on Windows: .venv\Scripts\activate

# 2) Install deps
pip install -r requirements.txt

# 3) (optional) copy env template
cp .env.example .env

# 4) Start the app
python server.py
# or with gunicorn (production-like websockets):
# gunicorn -k eventlet -w 1 server:app
```

Open http://localhost:5000/admin to create a game. After creating, project the join URL/QR.

**On-campus Wi‑Fi tip:** Students must be on the same network as your machine. Show the QR from the admin page.

---

## 2) Deploy to Render (free-ish)

1. Push this folder to a GitHub repo.
2. Create a **Render** “Web Service” → connect repo.
3. Set:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -k eventlet -w 1 server:app`
4. Open the public URL → go to `/admin`, create your game, share the QR.

(For Railway/Fly/Heroku-like platforms, the included `Procfile` works similarly.)

---

## How to use in class

1. Go to `/admin` → paste your prompts (one per line) → **Create Game**.
2. You’ll see the **Game Code**, join URL, and a **QR** image.
3. Students open the URL (or scan QR), enter the **code** and **name**, and get a grid.
4. As they tap squares, the **leaderboard** updates in real time.
5. You can keep the admin page open to monitor progress (or screen-share a student view).

---

## Customization

- **Grid size**: The UI lays out 3×N on small screens and 5×N on larger. Keep 20–25 prompts for a classic feel.
- **Peer confirmation**: For stricter validation, add a second step before accepting a mark (e.g., scan partner QR). This can be added to `mark_square` logic.
- **Export data**: The SQLite file (`bingo.db`) contains tables `game`, `prompt`, `player`, `mark`.

---

## Troubleshooting

- **WebSockets blocked?** Use `gunicorn -k eventlet -w 1 server:app` and ensure your host supports upgrades.
- **Students can’t reach your laptop URL?** Same network requirement; otherwise deploy to a public host or tunnel with `cloudflared`/`ngrok`.
- **QR not loading?** Ensure `qrcode[pil]` installed (already in `requirements.txt`).

---

## License
MIT
