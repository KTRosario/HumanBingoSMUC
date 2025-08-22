# Human Bingo — v2

Changes in this version:
- Students must enter a **classmate's name** for each prompt.
- Stored per-square `partner_name` in DB; tiny migration included.
- Admin: **click a player** to see per-prompt entered names.
- Input visibility improvements in CSS.
- Render-friendly: `runtime.txt` pins Python 3.11.9.

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
