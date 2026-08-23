"""
J.A.R.V.I.S Media Generator — text to image (free, no key) + text to video (free key).
Run: python3 app.py  ->  http://localhost:5000
"""
import os, time, uuid, threading
from flask import Flask, request, jsonify, send_from_directory, Response
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder="static")

# ---------- IMAGE (Pollinations, free, no key) ----------
@app.route("/api/image", methods=["POST"])
def gen_image():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "a luxury hotel at night, cinematic")
    w = int(data.get("width", 768))
    h = int(data.get("height", 512))
    safe = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?width={w}&height={h}&nologo=true&model=flux"
    try:
        r = requests.get(url, timeout=90)
        if r.status_code == 200 and r.content[:4] in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\x89PNG"):
            path = f"static/img_{uuid.uuid4().hex}.jpg"
            with open(path, "wb") as f:
                f.write(r.content)
            return jsonify({"ok": True, "url": "/" + path, "source": "pollinations"})
        return jsonify({"ok": False, "error": f"image gen failed: HTTP {r.status_code}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ---------- VIDEO (MiniMax H3, free key) ----------
MINIMAX_BASE = "https://api.minimax.io"
@app.route("/api/video", methods=["POST"])
def gen_video():
    data = request.get_json(force=True)
    model = data.get("model", "minimax")
    prompt = data.get("prompt", "a spinning globe with city lights")
    duration = int(data.get("duration", 5))

    if model == "minimax":
        key = os.getenv("MINIMAX_API_KEY")
        if not key:
            return jsonify({"ok": False, "error": "MINIMAX_API_KEY not set. Get free key at platform.minimax.io"})
        headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
        payload = {"model": "MiniMax-H3", "content": [{"type": "text", "text": prompt}],
                   "duration": duration, "resolution": "768P", "ratio": "16:9"}
        try:
            r = requests.post(f"{MINIMAX_BASE}/v2/video_generation", headers=headers, json=payload, timeout=60)
            if r.status_code != 200:
                return jsonify({"ok": False, "error": f"MiniMax submit failed: {r.status_code} {r.text[:300]}"})
            task_id = r.json().get("task_id")
            if not task_id:
                return jsonify({"ok": False, "error": "no task_id returned"})
            # poll
            for _ in range(60):  # up to ~10 min
                time.sleep(10)
                q = requests.get(f"{MINIMAX_BASE}/v2/query/video_generation/{task_id}", headers=headers, timeout=30)
                t = q.json().get("task", {})
                if t.get("status") == "succeeded":
                    vid_url = t.get("content", {}).get("url")
                    return jsonify({"ok": True, "url": vid_url, "source": "minimax"})
                if t.get("status") in ("failed", "cancelled"):
                    return jsonify({"ok": False, "error": f"MiniMax failed: {t.get('error')}"})
            return jsonify({"ok": False, "error": "timed out waiting for video"})
        except Exception as e:
            return jsonify({"ok": False, "error": str(e)})

    return jsonify({"ok": False, "error": f"unknown model {model}"})

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
