#!/usr/bin/env python3
"""按编号生成单个/批量测试包：线稿 PNG + 中英提示词 + 可复制的测试卡

用法:
    python3 make_kit.py S008 S018
    python3 make_kit.py P002 --views front,diag,side
"""
import argparse
import html
import json
import os
import subprocess
import urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = {p["id"]: p for p in json.load(open(os.path.join(ROOT, "data/catalog.json"), encoding="utf-8"))}
ASSET = "https://yyta.tech/api/poses-assets/line/"
VIEW_CN = {"front": "正面", "diag": "斜侧", "side": "侧面", "above": "俯视", "below": "仰视"}
CAM = {"front": "正面平视机位", "diag": "斜侧 45 度机位", "side": "正侧面机位",
       "above": "俯拍机位，镜头从上往下", "below": "仰拍机位，镜头从下往上"}
CAM_EN = {"front": "front view at eye level", "diag": "three-quarter view",
          "side": "side profile", "above": "high angle looking down", "below": "low angle looking up"}
SERIES_CN = {"std": "全身", "upper": "半身", "sexy": "风格姿势", "duo": "双人"}
FRAME = {"std": "全身入镜", "upper": "半身入镜", "sexy": "全身入镜", "duo": "双人全身入镜"}

ZH = ("图1是人物照片，图2是姿势参考线稿。以图1中的人物为唯一主体，保持其面部特征、发型、肤色、体型完全一致，"
      "不要改变长相。让人物摆出图2线稿的姿势：{pose}。{cam}，{frame}。"
      "写实摄影风格，自然柔和光线，背景干净，无文字无水印。场景/服装补充：")
EN = ("Image 1 is the person; image 2 is the pose reference. Keep the person in image 1 identical: same face, "
      "hairstyle, skin tone, body proportions. Make the person hold the pose shown in image 2: {desc} "
      "Camera: {cam}, {frame}. Photorealistic, natural lighting, clean background, no text, no watermark.")


def pose_zh(p):
    """把「站立竖叉・手抓脚踝（I字）」这类名字整理成可读的中文动作句"""
    name = p["name_cn"].replace("・", "，").replace("·", "，")
    return f"{p.get('class_cn','')}——{name}" if p.get("class_cn") else name


def fetch(fname, local):
    if os.path.exists(local) and os.path.getsize(local) > 1024:
        return True
    req = urllib.request.Request(ASSET + fname, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=45) as r:
        data = r.read()
    open(local, "wb").write(data)
    return len(data) > 1024


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ids", nargs="+")
    ap.add_argument("--views", default="front,diag")
    ap.add_argument("--out", default=os.path.join(ROOT, "exports_kits"))
    args = ap.parse_args()

    out = args.out
    os.makedirs(out, exist_ok=True)
    views = [v.strip() for v in args.views.split(",") if v.strip()]
    items = []

    for pid in args.ids:
        p = CATALOG.get(pid)
        if not p:
            print(f"跳过 {pid}：目录里没有这个编号")
            continue
        pdir = os.path.join(out, pid)
        os.makedirs(pdir, exist_ok=True)
        files = {}
        for v in views:
            fname = p["views"].get(v)
            if not fname:
                continue
            webp = os.path.join(pdir, f"{pid}_{v}.webp")
            png = os.path.join(pdir, f"{pid}_{v}.png")
            try:
                if fetch(fname, webp):
                    subprocess.run(["sips", "-s", "format", "png", webp, "--out", png],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    if os.path.exists(png):
                        files[v] = f"{pid}_{v}.png"
            except Exception as e:
                print(f"  ! {pid} {v} 下载失败: {e}")

        zh = ZH.format(pose=pose_zh(p), cam=CAM["front"], frame=FRAME.get(p["series"], "全身入镜"))
        en = EN.format(desc=(p["desc_en"] or "").strip().rstrip(".") + ".",
                       cam=CAM_EN["front"], frame=FRAME.get(p["series"], "全身入镜"))
        txt = (f"{pid} · {p['name_cn']}（{p.get('class_cn','')}｜{SERIES_CN.get(p['series'],p['series'])}）\n\n"
               f"【中文提示词】\n{zh}\n\n【英文提示词】\n{en}\n")
        open(os.path.join(pdir, f"{pid}-提示词.txt"), "w", encoding="utf-8").write(txt)
        items.append({"pose": p, "zh": zh, "en": en, "files": files})
        print(f"完成 {pid}：{p['name_cn']}  机位 {', '.join(files) or '无'}")

    # 汇总测试卡
    cards = []
    for it in items:
        p, files = it["pose"], it["files"]
        first = next(iter(files.values()), "")
        thumbs = "".join(
            f'<figure><img src="{pid_dir(p["id"])}/{fn}" alt="{VIEW_CN[v]}"><figcaption>{VIEW_CN[v]}</figcaption></figure>'
            for v, fn in files.items())
        cards.append(f"""
  <section class="card">
    <div class="head"><h2>{p['id']} · {html.escape(p['name_cn'])}</h2>
      <span class="tag">{html.escape(p.get('class_cn',''))}</span>
      <span class="tag">{SERIES_CN.get(p['series'], p['series'])}</span>
      {'<span class="tag warn">成人风格分级</span>' if p['rating'] != 'general' else ''}</div>
    <div class="body">
      <div class="thumbs">{thumbs or '<p class="note">线稿下载失败</p>'}</div>
      <div class="prompts">
        <h3>中文提示词</h3>
        <div class="prompt" id="zh{p['id']}">{html.escape(it['zh'])}</div>
        <button class="copy" onclick="cp('zh{p['id']}',this)">复制中文</button>
        <h3>英文提示词</h3>
        <div class="prompt" id="en{p['id']}">{html.escape(it['en'])}</div>
        <button class="copy" onclick="cp('en{p['id']}',this)">复制英文</button>
      </div>
    </div>
  </section>""")

    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>姿势测试包 · {len(items)} 个</title>
<style>
:root{{--bg:#f7f6f2;--card:#fff;--ink:#262b24;--ink2:#6f776c;--ink3:#9aa094;--line:#e8e7e1;--g:#343e32;--g2:#566a4f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.7 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1040px;margin:0 auto;padding:26px 20px 80px}}
h1{{font-size:20px;margin:0 0 6px}}.lead{{color:var(--ink2);font-size:13px;margin:0 0 20px}}
.usage{{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px 18px;margin-bottom:20px;font-size:13px;color:var(--ink2)}}
.usage b{{color:var(--ink)}}.usage ol{{margin:8px 0 0;padding-left:18px}}.usage li{{margin-bottom:4px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin-bottom:16px}}
.head{{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:14px}}
h2{{font-size:16px;margin:0}}.tag{{font-size:11px;background:#eef1ea;color:var(--g2);border-radius:5px;padding:2px 8px}}
.tag.warn{{background:#f7ece8;color:#a4603f}}
.body{{display:grid;grid-template-columns:260px 1fr;gap:18px;align-items:start}}
.thumbs{{display:flex;gap:10px;flex-wrap:wrap}}
figure{{margin:0;width:120px;text-align:center}}figure img{{width:120px;height:120px;object-fit:contain;background:#f1f0ea;border-radius:9px}}
figcaption{{font-size:11px;color:var(--ink3);margin-top:4px}}
h3{{font-size:12.5px;margin:0 0 6px;color:var(--ink3);font-weight:600}}
.prompt{{position:relative;background:#fbfbf9;border:1px solid var(--line);border-radius:10px;padding:10px 10px 36px;font-size:12.5px;color:var(--ink2);margin:0 0 12px;white-space:pre-wrap}}
.copy{{display:block;margin:-28px 0 12px auto;border:1px solid var(--line);background:#fff;color:var(--g2);border-radius:7px;padding:3px 10px;font-size:12px;cursor:pointer}}
.note{{font-size:12px;color:var(--ink3)}}
@media(max-width:760px){{.body{{grid-template-columns:1fr}}}}
</style></head><body><div class="wrap">
<h1>姿势测试包 · {len(items)} 个</h1>
<p class="lead">拿去豆包 / 即梦 手动测试：一张人物照片 + 一张姿势线稿</p>
<div class="usage"><b>豆包用法（没有"人物参考"开关）</b>
<ol><li>对话框点 <b>＋</b>，一次传两张：先传人物照片（图1），再传线稿（图2）</li>
<li>复制中文提示词（已按"图1/图2"写好），末尾补场景/服装</li>
<li>比例选 2:3 竖版 → 发送；不满意就追问"更忠实于图1的面部特征"</li>
<li>只能传一张图时：用 Demo 里的"合成单图参考"按钮，提示词改成"左半部分的人物，摆出右半部分线稿的姿势"</li></ol></div>
{''.join(cards)}
</div>
<script>function cp(id,b){{navigator.clipboard.writeText(document.getElementById(id).textContent.trim()).then(()=>{{const t=b.textContent;b.textContent='已复制 ✓';setTimeout(()=>b.textContent=t,1200);}});}}</script>
</body></html>"""
    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(doc)
    print(f"\n测试卡：{os.path.join(out,'index.html')}")


def pid_dir(pid):
    return pid


if __name__ == "__main__":
    main()
