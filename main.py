import math
import random
import sqlite3
import time

import flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = flask.Flask(__name__, static_folder="static", static_url_path="/")
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day"],
    storage_uri="memory://",
)

CHAR_SETS = {
    "classic": ["*", "+", "-", "|", "o", ".", "x"],
    "dense": ["#", "@", "%", "&", "$"],
    "minimal": [".", "o", "*"],
    "mixed": ["*", "+", "-", "|", "o", ".", "x", "#", "@", "%", "&", "$"],
}


class SeededRandom:
    def __init__(self, seed: str):
        self.seed = self._hash_string(seed)

    def _hash_string(self, s: str) -> int:
        h = 0
        for c in s:
            h = ((h << 5) - h) + ord(c)
            h = h & 0xFFFFFFFF
        return abs(h) or 1

    def next(self) -> float:
        self.seed = (self.seed * 1103515245 + 12345) & 0x7FFFFFFF
        return self.seed / 0x7FFFFFFF

    def next_int(self, min_val: int, max_val: int) -> int:
        return int(self.next() * (max_val - min_val + 1)) + min_val

    def choice(self, arr: list):
        return arr[int(self.next() * len(arr))]


def generate_snowflake(size: int, seed: str, style: str = "classic") -> str:
    if size % 2 == 0:
        size += 1

    rng = SeededRandom(seed)
    chars = CHAR_SETS.get(style, CHAR_SETS["classic"])
    center = size // 2
    grid = [[" " for _ in range(size)] for _ in range(size)]

    points = []

    for r in range(center + 1):
        if rng.next() < 0.7:
            points.append({"x": 0, "y": r, "char": rng.choice(chars)})

            if r > 0 and rng.next() < 0.4:
                branch_len = rng.next_int(1, max(1, r // 2))
                for b in range(1, branch_len + 1):
                    if rng.next() < 0.6:
                        points.append({"x": b, "y": r - b, "char": rng.choice(chars)})

    for rotation in range(6):
        angle = (rotation * math.pi) / 3
        cos_a = math.cos(angle)
        sin_a = math.sin(angle)

        for point in points:
            rx = round(point["x"] * cos_a - point["y"] * sin_a)
            ry = round(point["x"] * sin_a + point["y"] * cos_a)

            gx = center + rx
            gy = center + ry

            if 0 <= gx < size and 0 <= gy < size:
                grid[gy][gx] = point["char"]

    return "\n".join("".join(row) for row in grid)


def generate_seed() -> str:
    return f"{int(time.time() * 1000)}-{random.randint(0, 0xFFFFFFFF):08x}"


def get_db():
    conn = sqlite3.connect("flakes.db")
    conn.row_factory = sqlite3.Row
    return conn


conn = get_db()
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS snowflakes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        pattern TEXT NOT NULL,
        size INTEGER NOT NULL,
        melted INTEGER DEFAULT 0,
        created_at INTEGER NOT NULL
    )
""")
conn.commit()
conn.close()


@app.get("/")
@limiter.exempt
def index():
    return flask.send_from_directory("static", "index.html")


@app.get("/api/snowflakes")
@limiter.limit("10 per second")
def list_snowflakes():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, pattern, size, melted, created_at FROM snowflakes ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    return flask.jsonify([
        {
            "id": row["id"],
            "pattern": row["pattern"],
            "size": row["size"],
            "melted": row["melted"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ])


@app.get("/api/snowflakes/<int:snowflake_id>")
@limiter.limit("10 per second")
def get_snowflake(snowflake_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, pattern, size, melted, created_at FROM snowflakes WHERE id = ?", (snowflake_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return flask.jsonify({"error": "Snowflake not found"}), 404

    return flask.jsonify({
        "id": row["id"],
        "pattern": row["pattern"],
        "size": row["size"],
        "melted": row["melted"],
        "createdAt": row["created_at"],
    })


@app.get("/api/snowflakes/<int:snowflake_id>/render")
@limiter.limit("10 per second")
def render_snowflake(snowflake_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT pattern FROM snowflakes WHERE id = ?", (snowflake_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return "Snowflake not found", 404

    return row["pattern"], 200, {"Content-Type": "text/plain"}


@app.post("/api/snowflakes")
@limiter.limit("1 per second")
def create_snowflake():
    data = flask.request.get_json() or {}
    
    size = data.get("size")
    if size is None:
        size = random.randint(3, 12)
    size = max(1, min(20, int(size)))
    
    seed = data.get("seed") or generate_seed()
    style = data.get("style", "classic")
    if style not in CHAR_SETS:
        style = "classic"

    pattern = generate_snowflake(size, seed, style)
    created_at = int(time.time())

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO snowflakes (pattern, size, melted, created_at) VALUES (?, ?, 0, ?)",
        (pattern, size, created_at)
    )
    snowflake_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return flask.jsonify({"id": snowflake_id, "seed": seed, "style": style}), 201


@app.patch("/api/snowflakes/<int:snowflake_id>/melt")
@limiter.limit("1 per second")
def melt_snowflake(snowflake_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM snowflakes WHERE id = ?", (snowflake_id,))
    if not cursor.fetchone():
        conn.close()
        return flask.jsonify({"error": "Snowflake not found"}), 404

    cursor.execute("UPDATE snowflakes SET melted = 1 WHERE id = ?", (snowflake_id,))
    conn.commit()
    conn.close()

    return flask.jsonify({"ok": True})


@app.delete("/api/snowflakes/<int:snowflake_id>")
@limiter.limit("1 per second")
def delete_snowflake(snowflake_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM snowflakes WHERE id = ?", (snowflake_id,))
    if not cursor.fetchone():
        conn.close()
        return flask.jsonify({"error": "Snowflake not found"}), 404

    cursor.execute("DELETE FROM snowflakes WHERE id = ?", (snowflake_id,))
    conn.commit()
    conn.close()

    return flask.jsonify({"ok": True})


if __name__ == "__main__":
    app.run()
