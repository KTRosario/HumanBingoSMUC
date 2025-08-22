# server.py (v3)
import os, time, uuid, sqlite3, io
from flask import Flask, render_template, request, jsonify, redirect, url_for, send_file
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY","dev")

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
          player_id TEXT, prompt_id TEXT, confirmed INTEGER DEFAULT 0, partner_name TEXT,
          PRIMARY KEY(player_id, prompt_id)
        );
        """)
init_db()

with db() as _c:
    cols = [r[1] for r in _c.execute("PRAGMA table_info(mark)").fetchall()]
    if "partner_name" not in cols:
        _c.execute("ALTER TABLE mark ADD COLUMN partner_name TEXT")

@app.get("/health")
def health():
    return {"ok": True, "time": time.time()}

@app.route("/")
def index():
    return render_template("index.html")

@app.get("/admin")
def admin_home():
    return render_template("admin.html", game_id=None, prompts=None)

@app.post("/admin/create")
def admin_create():
    name = request.form.get("name", "Human Bingo")
    prompts_text = request.form.get("prompts","");
    prompts = [p.strip() for p in prompts_text.splitlines() if p.strip()]
    game_id = uuid.uuid4().hex[:6].upper()
    with db() as c:
        c.execute("INSERT INTO game(id,name,created_at) VALUES(?,?,?)", (game_id, name, time.time()))
        for t in prompts:
            c.execute("INSERT INTO prompt(id,game_id,text) VALUES(?,?,?)", (uuid.uuid4().hex, game_id, t))
    return redirect(url_for("admin_view", game_id=game_id))

@app.get("/admin/<game_id>")
def admin_view(game_id):
    with db() as c:
        g = c.execute("SELECT * FROM game WHERE id=?", (game_id,)).fetchone()
        if not g: return "Game not found", 404
        prompts = c.execute("SELECT id,text FROM prompt WHERE game_id=?", (game_id,)).fetchall()
        players = c.execute("SELECT id,name,score FROM player WHERE game_id=? ORDER BY score DESC, name ASC", (game_id,)).fetchall()
    return render_template("admin.html", game_id=game_id, game_name=g["name"], prompts=prompts, players=players)

@app.post("/admin/<game_id>/end")
def admin_end(game_id):
    with db() as c:
        c.execute("DELETE FROM mark WHERE player_id IN (SELECT id FROM player WHERE game_id=?)", (game_id,))
        c.execute("DELETE FROM player WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM prompt WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game WHERE id=?", (game_id,))
    return redirect(url_for("admin_home"))

@app.get("/admin/<game_id>/player/<player_id>")
def admin_player_detail(game_id, player_id):
    with db() as c:
        g = c.execute("SELECT * FROM game WHERE id=?", (game_id,)).fetchone()
        p = c.execute("SELECT * FROM player WHERE id=?", (player_id,)).fetchone()
        if not g or not p: return "Not found", 404
        rows = c.execute("""            SELECT prompt.text AS prompt, COALESCE(mark.partner_name,'') AS partner
            FROM prompt
            LEFT JOIN mark ON mark.prompt_id = prompt.id AND mark.player_id = ?
            WHERE prompt.game_id = ?
            ORDER BY prompt.text COLLATE NOCASE
        """, (player_id, game_id)).fetchall()
    return render_template("admin_player.html", game_id=game_id, game_name=g["name"], player=p, rows=rows)

@app.get("/preview/<game_id>")
def preview(game_id):
    with db() as c:
        g = c.execute("SELECT * FROM game WHERE id=?", (game_id,)).fetchone()
        if not g: return "Game not found", 404
    return render_template("preview.html", game_id=game_id, game_name=g["name"])

@app.get("/board/<game_id>")
def board(game_id):
    with db() as c:
        prompts = [dict(r) for r in c.execute("SELECT id,text FROM prompt WHERE game_id=?", (game_id,))]
    return jsonify(prompts)

@app.get("/api/leaderboard/<game_id>")
def api_leaderboard(game_id):
    with db() as c:
        rows = c.execute("SELECT id,name,score FROM player WHERE game_id=? ORDER BY score DESC, name ASC LIMIT 50", (game_id,)).fetchall()
    return jsonify([{"id":r["id"],"name":r["name"],"score":r["score"]} for r in rows])

@app.post("/join")
def join():
    data = request.get_json(force=True)
    game_id, name = data["game_id"].strip().upper(), data["name"].strip()
    if not game_id or not name: return jsonify({"error":"Missing game_id or name"}), 400
    player_id = uuid.uuid4().hex
    with db() as c:
        g = c.execute("SELECT id FROM game WHERE id=?", (game_id,)).fetchone()
        if not g: return jsonify({"error":"Game not found"}), 404
        c.execute("INSERT INTO player(id,game_id,name) VALUES(?,?,?)", (player_id, game_id, name))
    return jsonify({"player_id": player_id})

@socketio.on("join")
def on_join(data):
    room = data["game_id"]
    join_room(room)
    emit("joined", {"ok": True})

@socketio.on("mark_square")
def mark_square(data):
    game_id = data["game_id"]; player_id = data["player_id"]; prompt_id = data["prompt_id"]; partner_name = data.get("partner_name"," ").strip()
    with db() as c:
        try:
            c.execute("INSERT INTO mark(player_id,prompt_id,confirmed,partner_name) VALUES(?,?,?,?)", (player_id, prompt_id, 0, partner_name))
        except sqlite3.IntegrityError:
            c.execute("UPDATE mark SET partner_name=COALESCE(NULLIF(?, ''), partner_name) WHERE player_id=? AND prompt_id=?", (partner_name, player_id, prompt_id))
        c.execute("UPDATE player SET score=(SELECT COUNT(*) FROM mark WHERE player_id=?) WHERE id=?", (player_id, player_id))
        rows = c.execute("SELECT id,name,score FROM player WHERE game_id=? ORDER BY score DESC, name ASC LIMIT 50", (game_id,)).fetchall()
        leaderboard = [{"id":r["id"],"name":r["name"],"score":r["score"]} for r in rows]
    emit("leaderboard", {"leaderboard": leaderboard}, room=game_id)

@app.get("/qr/<game_id>")
def qr(game_id):
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
    socketio.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
