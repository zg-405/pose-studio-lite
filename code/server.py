#!/usr/bin/env python3
"""Pose Studio Lite — 最小可运行复现（仅标准库，无第三方依赖）

启动:
    python3 server.py            # 默认 http://localhost:8765
    PORT=9000 python3 server.py

生成分两种模式:
  1) demo 模式: 密钥栏填 demo（或留空点生成）→ 返回占位图，不花钱，用来跑通交互
  2) 真实模式: 填 OpenAI API Key → 代理调用 /v1/images/edits

可用环境变量:
    PORT              端口, 默认 8765
    OPENAI_BASE_URL   默认 https://api.openai.com/v1（可换成任意兼容中转）
    MODEL_FAST        默认 gpt-image-2.5-flare
    MODEL_QUALITY     默认 gpt-image-2.5-sunburst
    POSE_IMAGE=1      把姿势线稿作为第二张参考图一起发给上游（需上游支持 image[] 多图）
"""
import base64
import json
import mimetypes
import os
import re
import ssl
import sys
import urllib.request
import urllib.error
import urllib.parse
import uuid
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

ROOT = os.path.dirname(os.path.abspath(__file__))

# 默认加载仓库自带的 6 条样例；本地自建/自行抓取的完整库放到 data/catalog.json 即可自动生效
CATALOG_PATH = os.environ.get("CATALOG_PATH") or (
    os.path.join(ROOT, "data/catalog.json")
    if os.path.exists(os.path.join(ROOT, "data/catalog.json"))
    else os.path.join(ROOT, "data/catalog.sample.json")
)
CATALOG = json.load(open(CATALOG_PATH, encoding="utf-8"))
BY_ID = {p["id"]: p for p in CATALOG}

PORT = int(os.environ.get("PORT", "8765"))
BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL_FAST = os.environ.get("MODEL_FAST", "gpt-image-2.5-flare")
MODEL_QUALITY = os.environ.get("MODEL_QUALITY", "gpt-image-2.5-sunburst")
POSE_IMAGE = os.environ.get("POSE_IMAGE", "0") == "1"

ANGLE_EN = {
    "front": "front view, camera at eye level",
    "diag": "three-quarter view, camera slightly to the side",
    "side": "side profile view",
    "above": "high angle shot, camera looking down",
    "below": "low angle shot, camera looking up",
}

SYSTEM_RULE = (
    "You are an image editor. Keep the identity of the person in the first reference photo: "
    "same face, facial features, hairstyle, skin tone and body proportions. "
    "Only change the pose, framing, clothing and environment as instructed."
)


def build_prompt(pose, angle, user_prompt):
    parts = [
        SYSTEM_RULE,
        f"Pose to reproduce exactly: {pose['name_en']}. {pose['desc_en']}.",
        f"Camera: {ANGLE_EN.get(angle, ANGLE_EN['front'])}.",
    ]
    if user_prompt.strip():
        parts.append(f"Scene / styling: {user_prompt.strip()}.")
    parts.append("Photorealistic, natural lighting, single subject, no text, no watermark.")
    return " ".join(parts)


def multipart(fields, files):
    """fields: dict[str,str]；files: list[(name, filename, mime, bytes)]"""
    boundary = "----PoseStudio" + uuid.uuid4().hex
    out = []
    for k, v in fields.items():
        out.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode())
    for name, filename, mime, data in files:
        out.append(
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\"; filename=\"{filename}\"\r\n"
            f"Content-Type: {mime}\r\n\r\n".encode() + data + b"\r\n"
        )
    out.append(f"--{boundary}--\r\n".encode())
    return b"".join(out), f"multipart/form-data; boundary={boundary}"


def call_upstream(api_key, model, prompt, size, image_bytes, pose_bytes=None):
    files = [("image", "person.jpg", "image/jpeg", image_bytes)]
    if pose_bytes:
        files = [("image[]", "person.jpg", "image/jpeg", image_bytes),
                 ("image[]", "pose.webp", "image/webp", pose_bytes)]
    body, ctype = multipart({"model": model, "prompt": prompt, "size": size, "n": "1"}, files)
    req = urllib.request.Request(
        f"{BASE_URL}/images/edits", data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": ctype},
    )
    ctx = ssl.create_default_context()
    try:
        with urllib.request.urlopen(req, timeout=240, context=ctx) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="ignore")[:600]
        raise RuntimeError(f"上游返回 HTTP {e.code}: {detail}")


def mock_svg(pose, angle, note):
    img = f"https://yyta.tech/api/poses-assets/line/{pose['views'].get(angle) or pose['views']['front']}"
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="1024" height="1024" viewBox="0 0 1024 1024">
<rect width="1024" height="1024" fill="#f2f1ec"/>
<image href="{img}" x="212" y="90" width="600" height="600" preserveAspectRatio="xMidYMid meet" opacity="0.45"/>
<text x="512" y="760" text-anchor="middle" font-family="Helvetica,Arial" font-size="42" fill="#343e32">DEMO 模式 · 未调用真实模型</text>
<text x="512" y="820" text-anchor="middle" font-family="Helvetica,Arial" font-size="28" fill="#7d857a">{pose['id']} · {note}</text>
<text x="512" y="880" text-anchor="middle" font-family="Helvetica,Arial" font-size="24" fill="#9aa094">填入真实 API Key 后即可生成成片</text>
</svg>"""
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, code, obj):
        data = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path, _, query = self.path.partition("?")
        if path == "/api/catalog":
            return self._json(200, CATALOG)
        if path == "/api/config":
            return self._json(200, {"mockAvailable": True, "poses": len(CATALOG),
                                    "models": {"fast": MODEL_FAST, "quality": MODEL_QUALITY}})
        if path == "/api/pose-image":
            return self._pose_image(query)
        return super().do_GET()

    def _pose_image(self, query):
        """同源代理姿势线稿：让前端 canvas 能合成参考图（远端无 CORS 头会污染画布）"""
        qs = urllib.parse.parse_qs(query)
        pid = (qs.get("id") or [""])[0]
        view = (qs.get("view") or ["front"])[0]
        pose = BY_ID.get(pid)
        if not pose:
            return self._json(404, {"error": "姿势不存在"})
        fname = pose["views"].get(view) or pose["views"][next(iter(pose["views"]))]
        cache_dir = os.path.join(ROOT, "data/cache")
        os.makedirs(cache_dir, exist_ok=True)
        local = os.path.join(cache_dir, fname)
        if not (os.path.exists(local) and os.path.getsize(local) > 1024):
            try:
                req = urllib.request.Request("https://yyta.tech/api/poses-assets/line/" + fname,
                                             headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    open(local, "wb").write(r.read())
            except Exception as e:
                return self._json(502, {"error": f"姿势图获取失败: {e}"})
        data = open(local, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", "image/webp")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "public, max-age=86400")
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path.split("?")[0] != "/api/generate":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(length).decode() or "{}")
        except Exception:
            return self._json(400, {"error": "请求体不是合法 JSON"})

        pose = BY_ID.get(payload.get("poseId", ""))
        if not pose:
            return self._json(400, {"error": "姿势不存在"})
        angle = payload.get("angle") or "front"
        size = payload.get("size") or "1024x1024"
        model_key = payload.get("model") or "fast"
        model = MODEL_QUALITY if model_key == "quality" else MODEL_FAST
        user_prompt = payload.get("prompt") or ""
        api_key = (payload.get("apiKey") or "").strip()
        raw = payload.get("image") or ""

        m = re.match(r"^data:image/(jpeg|jpg|png|webp);base64,(.+)$", raw, re.S)
        if not m:
            return self._json(400, {"error": "请上传 JPG / PNG / WebP 人物照片"})
        try:
            image_bytes = base64.b64decode(m.group(2))
        except Exception:
            return self._json(400, {"error": "图片解码失败"})

        prompt = build_prompt(pose, angle, user_prompt)

        # demo 模式：无密钥或密钥为 demo，直接返回占位图，方便先跑通流程
        if not api_key or api_key == "demo":
            return self._json(200, {"mock": True, "url": mock_svg(pose, angle, model_key),
                                    "prompt": prompt, "requestId": "demo-" + uuid.uuid4().hex[:8]})

        pose_bytes = None
        if POSE_IMAGE:
            view = pose["views"].get(angle) or pose["views"]["front"]
            try:
                with urllib.request.urlopen(f"https://yyta.tech/api/poses-assets/line/{view}", timeout=30) as r:
                    pose_bytes = r.read()
            except Exception:
                pose_bytes = None

        try:
            data = call_upstream(api_key, model, prompt, size, image_bytes, pose_bytes)
        except RuntimeError as e:
            return self._json(502, {"error": str(e)})
        except Exception as e:
            return self._json(502, {"error": f"连接上游失败: {e}"})

        item = (data.get("data") or [{}])[0]
        url = item.get("url") or (("data:image/png;base64," + item["b64_json"]) if item.get("b64_json") else "")
        if not url:
            return self._json(502, {"error": "上游没有返回图片", "raw": str(data)[:400]})
        return self._json(200, {"url": url, "model": model, "prompt": prompt,
                                "requestId": data.get("created") or uuid.uuid4().hex[:8]})


if __name__ == "__main__":
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Pose Studio Lite → http://127.0.0.1:{PORT}")
    print(f"姿势数: {len(CATALOG)}  |  fast={MODEL_FAST}  quality={MODEL_QUALITY}  POSE_IMAGE={POSE_IMAGE}")
    srv.serve_forever()
