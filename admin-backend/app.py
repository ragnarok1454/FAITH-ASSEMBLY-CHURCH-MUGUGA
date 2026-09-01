"""
Faith Assembly Church Muguga - Admin Backend
==============================================
Handles:
  - Login / logout for Super Admins and Ministry Admins
  - Gallery photo upload & delete, scoped by ministry + role
  - Public read-only endpoint the website uses to display gallery photos

Run locally:
    pip install -r requirements.txt
    python app.py
Then create your first users with create_admin.py (see that file).
"""

import os
import sqlite3
import uuid
from functools import wraps

from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "church.db")
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}
ALLOWED_VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}

# Ministries that have a gallery an admin can manage.
# Add more slugs here later (e.g. "youth", "praise", "instruments") as you
# create admins for them — no other code changes needed.
VALID_MINISTRIES = {"men", "women", "youth", "praise", "instruments"}

app = Flask(__name__)
app.secret_key = os.environ.get("APP_SECRET_KEY", "change-this-in-production")
app.config.update( SESSION_COOKIE_SAMESITE="None", SESSION_COOKIE_SECURE=True, )

# Video files can be large — raise the default upload limit to 300MB.
# (If you host on a free-tier service, check its own upload limit too —
# many free tiers cap requests around 10-100MB regardless of this setting.)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024

# Allow your static site (hosted elsewhere) to call this API with cookies.
CORS(app, supports_credentials=True, origins="*")  # tighten origins before going live


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('superadmin', 'ministry_admin')),
            ministry TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS gallery_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ministry TEXT NOT NULL,
            filename TEXT NOT NULL,
            caption TEXT,
            uploaded_by TEXT,
            uploaded_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Site-wide assets that only a Super Admin can change:
    # home_background -> a single uploaded image, replaces itself each time
    # latest_sermon   -> either a YouTube video ID, or an uploaded video file
    conn.execute("""
        CREATE TABLE IF NOT EXISTS site_assets (
            key TEXT PRIMARY KEY,
            asset_type TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_by TEXT,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not logged in"}), 401
        return f(*args, **kwargs)
    return wrapper


def can_manage_ministry(ministry):
    """Superadmins can touch any ministry. Ministry admins only their own."""
    if session.get("role") == "superadmin":
        return True
    return session.get("role") == "ministry_admin" and session.get("ministry") == ministry


def superadmin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return jsonify({"error": "Not logged in"}), 401
        if session.get("role") != "superadmin":
            return jsonify({"error": "Super Admin access only"}), 403
        return f(*args, **kwargs)
    return wrapper


def allowed_image(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def allowed_video(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_VIDEO_EXTENSIONS


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "")

    conn = get_db()
    user = conn.execute(
        "SELECT * FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"error": "Invalid username or password"}), 401

    session["user_id"] = user["id"]
    session["username"] = user["username"]
    session["role"] = user["role"]
    session["ministry"] = user["ministry"]

    return jsonify({
        "username": user["username"],
        "role": user["role"],
        "ministry": user["ministry"],
    })


@app.route("/api/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"ok": True})


@app.route("/api/me", methods=["GET"])
def me():
    if "user_id" not in session:
        return jsonify({"error": "Not logged in"}), 401
    return jsonify({
        "username": session["username"],
        "role": session["role"],
        "ministry": session["ministry"],
    })


# ---------------------------------------------------------------------------
# Gallery routes
# ---------------------------------------------------------------------------

@app.route("/api/gallery/<ministry>", methods=["GET"])
def list_gallery(ministry):
    """Public endpoint — the website's ministry pages call this to render photos."""
    if ministry not in VALID_MINISTRIES:
        return jsonify({"error": "Unknown ministry"}), 404

    conn = get_db()
    rows = conn.execute(
        "SELECT id, filename, caption, uploaded_at FROM gallery_images "
        "WHERE ministry = ? ORDER BY uploaded_at DESC",
        (ministry,),
    ).fetchall()
    conn.close()

    images = [
        {
            "id": row["id"],
            "url": f"/uploads/{ministry}/{row['filename']}",
            "caption": row["caption"],
            "uploaded_at": row["uploaded_at"],
        }
        for row in rows
    ]
    return jsonify(images)


@app.route("/api/gallery/<ministry>", methods=["POST"])
@login_required
def upload_image(ministry):
    if ministry not in VALID_MINISTRIES:
        return jsonify({"error": "Unknown ministry"}), 404
    if not can_manage_ministry(ministry):
        return jsonify({"error": "You don't have permission to manage this gallery"}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_image(file.filename):
        return jsonify({"error": "Invalid or missing file"}), 400

    caption = request.form.get("caption", "")

    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{ext}"

    ministry_dir = os.path.join(UPLOAD_DIR, ministry)
    os.makedirs(ministry_dir, exist_ok=True)
    file.save(os.path.join(ministry_dir, safe_name))

    conn = get_db()
    conn.execute(
        "INSERT INTO gallery_images (ministry, filename, caption, uploaded_by) "
        "VALUES (?, ?, ?, ?)",
        (ministry, safe_name, caption, session["username"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "filename": safe_name})


@app.route("/api/gallery/<ministry>/<int:image_id>", methods=["DELETE"])
@login_required
def delete_image(ministry, image_id):
    if ministry not in VALID_MINISTRIES:
        return jsonify({"error": "Unknown ministry"}), 404
    if not can_manage_ministry(ministry):
        return jsonify({"error": "You don't have permission to manage this gallery"}), 403

    conn = get_db()
    row = conn.execute(
        "SELECT filename FROM gallery_images WHERE id = ? AND ministry = ?",
        (image_id, ministry),
    ).fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "Image not found"}), 404

    filepath = os.path.join(UPLOAD_DIR, ministry, row["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    conn.execute("DELETE FROM gallery_images WHERE id = ?", (image_id,))
    conn.commit()
    conn.close()

    return jsonify({"ok": True})


@app.route("/uploads/<ministry>/<filename>")
def serve_upload(ministry, filename):
    return send_from_directory(os.path.join(UPLOAD_DIR, ministry), filename)


# ---------------------------------------------------------------------------
# Site-wide assets (Super Admin only) — home background image, latest sermon
# ---------------------------------------------------------------------------

@app.route("/api/site-assets/home-background", methods=["GET"])
def get_home_background():
    """Public — index.html calls this to know which image to show."""
    conn = get_db()
    row = conn.execute(
        "SELECT value FROM site_assets WHERE key = 'home_background'"
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"url": None})  # frontend falls back to its default CSS image
    return jsonify({"url": f"/uploads/site/{row['value']}"})


@app.route("/api/site-assets/home-background", methods=["POST"])
@superadmin_required
def set_home_background():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["file"]
    if file.filename == "" or not allowed_image(file.filename):
        return jsonify({"error": "Invalid or missing image file"}), 400

    ext = file.filename.rsplit(".", 1)[1].lower()
    safe_name = f"home-background-{uuid.uuid4().hex}.{ext}"

    site_dir = os.path.join(UPLOAD_DIR, "site")
    os.makedirs(site_dir, exist_ok=True)
    file.save(os.path.join(site_dir, safe_name))

    conn = get_db()
    conn.execute(
        "INSERT INTO site_assets (key, asset_type, value, updated_by) "
        "VALUES ('home_background', 'image', ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
        "updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP",
        (safe_name, session["username"]),
    )
    conn.commit()
    conn.close()

    return jsonify({"ok": True, "url": f"/uploads/site/{safe_name}"})


@app.route("/api/site-assets/sermon", methods=["GET"])
def get_sermon():
    """Public — sermons.html calls this to know what to embed/play."""
    conn = get_db()
    row = conn.execute(
        "SELECT asset_type, value FROM site_assets WHERE key = 'latest_sermon'"
    ).fetchone()
    conn.close()
    if not row:
        return jsonify({"type": None})

    if row["asset_type"] == "youtube":
        return jsonify({"type": "youtube", "youtube_id": row["value"]})
    else:
        return jsonify({"type": "video", "url": f"/uploads/site/{row['value']}"})


@app.route("/api/site-assets/sermon", methods=["POST"])
@superadmin_required
def set_sermon():
    """
    Two ways to set the latest sermon:
      1. JSON body: {"type": "youtube", "youtube_id": "abc123"}
      2. multipart form with a "file" field (a video) and type=upload
    """
    if request.content_type and "multipart/form-data" in request.content_type:
        file = request.files.get("file")
        if not file or file.filename == "" or not allowed_video(file.filename):
            return jsonify({"error": "Invalid or missing video file "
                                      "(allowed: mp4, webm, mov)"}), 400

        ext = file.filename.rsplit(".", 1)[1].lower()
        safe_name = f"sermon-{uuid.uuid4().hex}.{ext}"

        site_dir = os.path.join(UPLOAD_DIR, "site")
        os.makedirs(site_dir, exist_ok=True)
        file.save(os.path.join(site_dir, safe_name))

        conn = get_db()
        conn.execute(
            "INSERT INTO site_assets (key, asset_type, value, updated_by) "
            "VALUES ('latest_sermon', 'video', ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET asset_type = 'video', value = excluded.value, "
            "updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP",
            (safe_name, session["username"]),
        )
        conn.commit()
        conn.close()
        return jsonify({"ok": True, "type": "video", "url": f"/uploads/site/{safe_name}"})

    data = request.get_json(silent=True) or {}
    youtube_id = data.get("youtube_id", "").strip()
    if not youtube_id:
        return jsonify({"error": "youtube_id is required"}), 400

    conn = get_db()
    conn.execute(
        "INSERT INTO site_assets (key, asset_type, value, updated_by) "
        "VALUES ('latest_sermon', 'youtube', ?, ?) "
        "ON CONFLICT(key) DO UPDATE SET asset_type = 'youtube', value = excluded.value, "
        "updated_by = excluded.updated_by, updated_at = CURRENT_TIMESTAMP",
        (youtube_id, session["username"]),
    )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "type": "youtube", "youtube_id": youtube_id})

init_db()
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)
