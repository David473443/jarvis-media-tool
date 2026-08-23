"""
J.A.R.V.I.S Media Generator
- Images: Pollinations (free, no key; key = higher limit)
- Voice (TTS): EasyVoice (free key, kokoro-82m) -> fallback MiniMax if funded
- Video: fal.ai (free key, t2v-turbo) -> fallback MiniMax H3 if funded
Run: uv run --with flask --with requests --with python-dotenv python3 app.py
"""
import os, time, uuid
from flask import Flask, request, jsonify, send_from_directory
import requests
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__, static_folder="static")

# ---------- IMAGE (Pollinations, free, no key) ----------
@app.route("/api/image", methods=["POST"])
def gen_image():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "a luxury hotel at night, cinematic")
    w = int(data.get("width", 768)); h = int(data.get("height", 512))
    safe = requests.utils.quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{safe}?width={w}&height={h}&nologo=true&model=flux"
    headers = {}
    key = os.getenv("POLLINATIONS_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        r = requests.get(url, headers=headers, timeout=90)
        if r.status_code == 200 and r.content[:4] in (b"\xff\xd8\xff\xe0", b"\xff\xd8\xff\xe1", b"\x89PNG"):
            path = f"static/img_{uuid.uuid4().hex}.jpg"
            open(path, "wb").write(r.content)
            return jsonify({"ok": True, "url": "/" + path, "source": "pollinations"})
        return jsonify({"ok": False, "error": f"image gen failed: HTTP {r.status_code}"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)})

# ---------- VOICE (EasyVoice free, MiniMax fallback) ----------
@app.route("/api/voice", methods=["POST"])
def gen_voice():
    data = request.get_json(force=True)
    text = data.get("text", "Hello, J.A.R.V.I.S online.")
    voice = data.get("voice", "af_aoede")
    # 1) EasyVoice (free)
    ev = os.getenv("EASYVOICE_API_KEY")
    if ev:
        try:
            r = requests.post("https://easyvoice.ae/api/v1/audio/speech",
                              headers={"Authorization": f"Bearer {ev}", "Content-Type": "application/json"},
                              json={"model": "kokoro-82m", "input": text, "voice": voice}, timeout=60)
            # EasyVoice returns mp3 (starts with ID3 or ftyp); validate it's real audio (>= 1KB)
            if r.status_code == 200 and len(r.content) > 1000:
                path = f"static/voice_{uuid.uuid4().hex}.mp3"
                open(path, "wb").write(r.content)
                return jsonify({"ok": True, "url": "/" + path, "source": "easyvoice"})
        except Exception as e:
            pass  # fall through to MiniMax
    # 2) MiniMax (only if funded)
    mm = os.getenv("MINIMAX_API_KEY")
    if mm:
        try:
            r = requests.post("https://api.minimax.io/v1/t2a_v2",
                              headers={"Authorization": f"Bearer {mm}", "Content-Type": "application/json"},
                              json={"model": "speech-02-hd", "text": text,
                                    "voice_setting": {"voice_id": "male-qn-qingse", "speed": 1.0, "vol": 1.0, "pitch": 0},
                                    "audio_setting": {"sample_rate": 32000, "bitrate": 128000, "format": "mp3"}}, timeout=40)
            # MiniMax returns JSON on error (not audio) — only accept if body looks like mp3
            if r.status_code == 200 and r.content[:4] in (b"ID3", b"\xff\xfb", b"\xfa", b"\xfb"):
                path = f"static/voice_{uuid.uuid4().hex}.mp3"
                open(path, "wb").write(r.content)
                return jsonify({"ok": True, "url": "/" + path, "source": "minimax"})
        except Exception as e:
            pass
    return jsonify({"ok": False, "error": "no working voice provider (EasyVoice key missing or MiniMax unfunded)"})


# ---------- VIDEO (fal.ai primary, MiniMax fallback) ----------
@app.route("/api/video", methods=["POST"])
def gen_video():
    data = request.get_json(force=True)
    prompt = data.get("prompt", "a spinning glowing earth in space, sci-fi")
    duration = int(data.get("duration", 5))
    # 1) fal.ai (free tier key)
    fal = os.getenv("FAL_KEY")
    if fal:
        try:
            headers = {"Authorization": f"Key {fal}", "Content-Type": "application/json"}
            # submit
            r = requests.post("https://queue.fal.run/fal-ai/t2v-turbo",
                              headers=headers, json={"prompt": prompt, "num_frames": duration*8}, timeout=60)
            if r.status_code in (200, 201):
                rid = r.json().get("request_id") or r.json().get("id")
                # poll
                for _ in range(40):
                    time.sleep(8)
                    q = requests.get(f"https://queue.fal.run/fal-ai/t2v-turbo/requests/{rid}/status", headers=headers, timeout=30)
                    st = q.json()
                    if st.get("status") == "COMPLETED":
                        vid = st.get("response", {}).get("video", {}).get("url") or st.get("response", {}).get("url")
                        return jsonify({"ok": True, "url": vid, "source": "fal"})
                    if st.get("status") == "FAILED":
                        break
                return jsonify({"ok": False, "error": "fal video timed out/failed"})
            return jsonify({"ok": False, "error": f"fal submit failed: {r.status_code} {r.text[:200]}"})
        except Exception as e:
            pass  # fall to MiniMax
    # 2) MiniMax (only if funded)
    mm = os.getenv("MINIMAX_API_KEY")
    if mm:
        try:
            headers = {"Authorization": f"Bearer {mm}", "Content-Type": "application/json"}
            r = requests.post("https://api.minimax.io/v2/video_generation", headers=headers,
                              json={"model": "MiniMax-H3", "content": [{"type": "text", "text": prompt}],
                                    "duration": duration, "resolution": "768P", "ratio": "16:9"}, timeout=60)
            if r.status_code == 200:
                task_id = r.json().get("task_id")
                for _ in range(60):
                    time.sleep(10)
                    q = requests.get(f"https://api.minimax.io/v2/query/video_generation/{task_id}", headers=headers, timeout=30)
                    t = q.json().get("task", {})
                    if t.get("status") == "succeeded":
                        return jsonify({"ok": True, "url": t.get("content", {}).get("url"), "source": "minimax"})
                    if t.get("status") in ("failed", "cancelled"):
                        break
                return jsonify({"ok": False, "error": "MiniMax video failed"})
            return jsonify({"ok": False, "error": f"MiniMax submit failed: {r.status_code}"})
        except Exception as e:
            pass
    return jsonify({"ok": False, "error": "no working video provider (need FAL_KEY or funded MINIMAX_API_KEY)"})

@app.route("/")
def index():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    os.makedirs("static", exist_ok=True)
    app.run(host="0.0.0.0", port=5000)
