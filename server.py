# server.py
import os, time, uuid, sqlite3, io
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

# Load env (e.g., SECRET_KEY)
load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev")
# In production, use eventlet or gevent for SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

DB = os.environ.get("BINGO_DB_PATH", "bingo.db")

def db():
    conn = sqlite3.connect(DB, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS game(
          id TEXT PRIMARY KEY, name TEXT, created_at REAL
        );
        CREATE TABLE IF NOT EXISTS prompt(
          id TEXT PRIMARY KEY, game_id TEXT, text TEXT
        );
        CREATE TABLE IF NOT EXISTS player(
          id TEXT PRIMARY KEY, game_id TEXT, name TEXT, score INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS mark(
          player_id TEXT, prompt_id TEXT, confirmed INTEGER DEFAULT 0,
          PRIMARY KEY(player_id, prompt_id)
        );
        """)
init_db()

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/health")
def health():
    return {"ok": True, "time": time.time()}

# --- Admin pages ---
@app.get("/admin")
def admin_home():
    return render_template("admin.html", game_id=None, prompts=None)

@app.post("/admin/create")
def admin_create():
    name = request.form.get("name", "Human Bingo")
    prompts_text = request.form.get("prompts","")
    prompts = [p.strip() for p in prompts_text.splitlines() if p.strip()]
    game_id = uuid.uuid4().hex[:6].upper()
    with db() as c:
        c.execute("INSERT INTO game(id,name,created_at) VALUES(?,?,?)",
                  (game_id, name, time.time()))
        for t in prompts:
            c.execute("INSERT INTO prompt(id,game_id,text) VALUES(?,?,?)",
                      (uuid.uuid4().hex, game_id, t))
    return redirect(url_for("admin_view", game_id=game_id))

@app.get("/admin/<game_id>")
def admin_view(game_id):
    with db() as c:
        g = c.execute("SELECT * FROM game WHERE id=?", (game_id,)).fetchone()
        prompts = c.execute("SELECT id,text FROM prompt WHERE game_id=?", (game_id,)).fetchall()
        players = c.execute("SELECT name,score FROM player WHERE game_id=? ORDER BY score DESC, name ASC", (game_id,)).fetchall()
    if not g:
        return "Game not found", 404
    return render_template("admin.html", game_id=game_id, game_name=g["name"], prompts=prompts, players=players)

# --- Student API ---
@app.post("/join")
def join():
    data = request.get_json(force=True)
    game_id, name = data["game_id"].strip().upper(), data["name"].strip()
    player_id = uuid.uuid4().hex
    with db() as c:
        g = c.execute("SELECT id FROM game WHERE id=?", (game_id,)).fetchone()
        if not g:
            return jsonify({"error":"Game not found"}), 404
        c.execute("INSERT INTO player(id,game_id,name) VALUES(?,?,?)",
                  (player_id, game_id, name))
    return jsonify({"player_id": player_id})

@app.get("/board/<game_id>")
def board(game_id):
    with db() as c:
        prompts = [dict(r) for r in c.execute("SELECT id,text FROM prompt WHERE game_id=?",(game_id,))]
    return jsonify(prompts)

# --- WebSocket events ---
@socketio.on("join")
def on_join(data):
    room = data["game_id"]
    join_room(room)
    emit("joined", {"ok": True})

@socketio.on("mark_square")
def mark_square(data):
    game_id = data["game_id"]; player_id = data["player_id"]; prompt_id = data["prompt_id"]
    with db() as c:
        try:
            c.execute("INSERT INTO mark(player_id,prompt_id,confirmed) VALUES(?,?,?)",
                      (player_id, prompt_id, 0))
        except sqlite3.IntegrityError:
            pass
        c.execute("UPDATE player SET score=(SELECT COUNT(*) FROM mark WHERE player_id=?) WHERE id=?",
                  (player_id, player_id))
        rows = c.execute("""
            SELECT name, score FROM player WHERE game_id=? ORDER BY score DESC, name ASC LIMIT 10
        """, (game_id,)).fetchall()
        leaderboard = [{"name": r["name"], "score": r["score"]} for r in rows]
    emit("leaderboard", {"leaderboard": leaderboard}, room=game_id)

# --- Optional: QR code for quick joining (requires qrcode library) ---
@app.get("/qr/<game_id>")
def qr(game_id):
    # Generate a QR pointing to the join page with game prefilled as a query param
    try:
        import qrcode
    except ImportError:
        return "Install 'qrcode[pil]' to enable QR generation", 500
    base = request.host_url.rstrip("/")
    url = f"{base}/?game={game_id}"
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

if __name__ == "__main__":
    # For local dev: socketio.run(app, debug=True)  # plain dev server
    # For production-like dev with websockets:
    # pip install eventlet and use socketio.run(..., ) which picks eventlet automatically if installed.
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
