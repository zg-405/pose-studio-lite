#!/usr/bin/env python3
"""导出姿势库为「可在豆包/即梦/其他工具手动测试」的素材包

用法:
    python3 export_poses.py                       # 全部姿势，只导正面图
    python3 export_poses.py --views all           # 每个姿势导 5 个机位（包会大 5 倍）
    python3 export_poses.py --series std,upper    # 只导全身/半身
    python3 export_poses.py --limit 20            # 先导 20 个试水

产出 exports/：
    images/            姿势线稿（webp）
    poses.csv          表格（Excel 可直接打开，含中英文提示词）
    prompts.json       结构化数据（给脚本/API 用）
    gallery.html       本地画廊：看图 + 一键复制提示词
    poses.zip          整个素材包
"""
import argparse
import csv
import html
import json
import os
import re
import shutil
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = json.load(open(os.path.join(ROOT, "data/catalog.json"), encoding="utf-8"))
ASSET = "https://yyta.tech/api/poses-assets/line/"

VIEW_CN = {"front": "正面", "diag": "斜侧", "side": "侧面", "above": "俯视", "below": "仰视"}
VIEW_CAM = {
    "front": "正面平视机位",
    "diag": "斜侧 45 度机位",
    "side": "正侧面机位",
    "above": "俯拍机位，镜头从上往下",
    "below": "仰拍机位，镜头从下往上",
}
SERIES_CN = {"std": "全身", "upper": "半身", "sexy": "风格姿势", "duo": "双人"}
FRAME = {"std": "全身入镜", "upper": "半身入镜", "sexy": "全身入镜", "duo": "双人全身入镜"}

TEMPLATE_ZH = (
    "以参考图中的人物为唯一主体，保持其面部特征、发型、肤色、体型完全一致，不要改变长相。"
    "让人物摆出「{name}」的姿势（{cls}），{cam}，{frame}。"
    "写实摄影风格，自然柔和光线，背景干净，无文字无水印。"
)
TEMPLATE_EN = (
    "Keep the person in the reference photo identical: same face, hairstyle, skin tone, body proportions. "
    "Pose: {name_en}. {desc} Camera: {cam_en}. Photorealistic, natural lighting, clean background, no text, no watermark."
)
PROMPT_TAIL = "场景/服装补充：{scene}"


def keywords(name_cn):
    parts = [p for p in re.split(r"[・·、，,\s]+", name_cn) if p]
    return "、".join(parts)


def build(idx, pose, view):
    name = pose["name_cn"]
    tmpl = TEMPLATE_ZH.format(
        name=name,
        cls=pose.get("class_cn") or "",
        cam=VIEW_CAM[view],
        frame=FRAME.get(pose["series"], "全身入镜"),
    )
    en = TEMPLATE_EN.format(
        name_en=pose.get("name_en") or name,
        desc=(pose.get("desc_en") or "").strip().rstrip(".") + ".",
        cam_en={"front": "front view at eye level", "diag": "three-quarter view",
                "side": "side profile", "above": "high angle looking down",
                "below": "low angle looking up"}[view],
    )
    return {
        "no": idx,
        "id": pose["id"],
        "series": pose["series"],
        "series_cn": SERIES_CN.get(pose["series"], pose["series"]),
        "rating": pose["rating"],
        "class_cn": pose.get("class_cn", ""),
        "name_cn": name,
        "name_en": pose.get("name_en", ""),
        "keywords": keywords(name),
        "view": view,
        "view_cn": VIEW_CN[view],
        "image": f"images/{pose['id']}_{view}.webp",
        "prompt_zh": tmpl,
        "prompt_en": en,
        "desc_en": pose.get("desc_en", ""),
    }


def download(url, path, retries=2):
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return True
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 1024:
                continue
            open(path, "wb").write(data)
            return True
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ! 下载失败 {url}: {e}")
    return False


def pick_views(pose, want_views):
    """只导正面时，若该姿势没有正面图，退回它实际拥有的第一个机位"""
    if want_views == ["front"]:
        v = "front" if pose["views"].get("front") else next(
            (k for k in VIEW_CN if pose["views"].get(k)), None)
        return [v] if v else []
    return [v for v in want_views if pose["views"].get(v)]



def gallery(rows, out):
    data = json.dumps(rows, ensure_ascii=False)
    cards = []
    for r in rows:
        mask = " adult" if r["rating"] == "suggestive" else ""
        cards.append(f"""
    <article class="card{mask}" data-series="{r['series']}" data-text="{html.escape((r['name_cn']+' '+r['id']+' '+r['class_cn']).lower())}">
      <div class="thumb"><img src="{r['image']}" loading="lazy" alt="{html.escape(r['name_cn'])}"><span class="no">{r['id']}</span></div>
      <div class="body">
        <h3>{html.escape(r['name_cn'])}</h3>
        <p class="meta">{html.escape(r['series_cn'])} · {html.escape(r['class_cn'])} · {r['view_cn']}</p>
        <div class="kw">{' '.join(f'<b>{html.escape(k)}</b>' for k in r['keywords'].split('、'))}</div>
        <div class="prompt" id="p{r['id']}">{html.escape(r['prompt_zh'])}</div>
        <div class="actions">
          <button onclick="copy('p{r['id']}',this)">复制中文提示词</button>
          <button class="ghost" onclick="copyText(this.dataset.t,this)" data-t="{html.escape(r['prompt_en'])}">英文</button>
          <a href="{r['image']}" download>下载线稿</a>
        </div>
      </div>
    </article>""")

    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>姿势素材包 · {len(rows)} 条</title>
<style>
:root{{--bg:#f7f6f2;--card:#fff;--ink:#262b24;--ink2:#6f776c;--ink3:#9aa094;--line:#e8e7e1;--g:#343e32;--g2:#566a4f}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
header{{background:#fff;border-bottom:1px solid var(--line);padding:16px 24px;position:sticky;top:0;z-index:9}}
h1{{font-size:18px;margin:0 0 4px}}header p{{margin:0;color:var(--ink3);font-size:12.5px}}
.toolbar{{display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap}}
input[type=search]{{height:34px;border:1px solid var(--line);border-radius:9px;padding:0 12px;min-width:240px;outline:none;background:#fbfbf9}}
button{{border:1px solid var(--line);background:#fbfbf9;color:var(--ink2);border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer}}
button.on{{background:var(--g);color:#fff;border-color:var(--g)}}
main{{padding:22px 24px 60px;display:grid;grid-template-columns:repeat(auto-fill,minmax(288px,1fr));gap:14px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}}
.thumb{{position:relative;background:#f1f0ea;aspect-ratio:1/1}}
.thumb img{{width:100%;height:100%;object-fit:contain;display:block}}
.card.adult .thumb img{{filter:blur(10px)}}
.card.adult:hover .thumb img{{filter:none}}
.no{{position:absolute;top:8px;left:8px;background:rgba(52,62,50,.85);color:#fff;font-size:10.5px;font-weight:700;padding:2px 7px;border-radius:5px}}
.body{{padding:12px 14px 14px;display:flex;flex-direction:column;gap:6px;flex:1}}
h3{{font-size:14px;margin:0}}p.meta{{margin:0;color:var(--ink3);font-size:11.5px}}
.kw{{display:flex;gap:4px;flex-wrap:wrap}}
.kw b{{font-weight:500;font-size:11px;background:#eef1ea;color:var(--g2);border-radius:5px;padding:1px 6px}}
.prompt{{font-size:11.5px;color:var(--ink2);background:#fbfbf9;border:1px solid var(--line);border-radius:8px;padding:8px;line-height:1.55;max-height:96px;overflow:auto}}
.actions{{display:flex;gap:6px;margin-top:auto;flex-wrap:wrap}}
.actions a{{font-size:12.5px;color:var(--g2);align-self:center;text-decoration:none;font-weight:600}}
</style></head><body>
<header>
  <h1>姿势素材包 · 共 {len(rows)} 条（可直接拿去豆包 / 即梦测）</h1>
  <p>用法：下载线稿 → 上传为「姿势参考/参考图」；上传你自己的照片 → 作为人物参考；粘贴提示词 → 生成。提示词里的「场景/服装补充」按需追加。</p>
  <div class="toolbar">
    <input type="search" id="q" placeholder="搜索姿势名 / 编号 / 分类">
    <button class="on" data-s="all">全部</button>
    <button data-s="std">全身</button><button data-s="upper">半身</button>
    <button data-s="sexy">风格</button><button data-s="duo">双人</button>
  </div>
</header>
<main id="grid">{''.join(cards)}</main>
<script>
const CARDS=[...document.querySelectorAll('.card')];
let series='all',kw='';
function apply(){{CARDS.forEach(c=>{{const okS=series==='all'||c.dataset.series===series;const okK=!kw||c.dataset.text.includes(kw);c.style.display=okS&&okK?'':'none';}});}}
document.getElementById('q').oninput=e=>{{kw=e.target.value.trim().toLowerCase();apply();}};
document.querySelectorAll('[data-s]').forEach(b=>b.onclick=()=>{{document.querySelectorAll('[data-s]').forEach(x=>x.classList.remove('on'));b.classList.add('on');series=b.dataset.s;apply();}});
function copy(id,btn){{navigator.clipboard.writeText(document.getElementById(id).textContent).then(()=>{{const t=btn.textContent;btn.textContent='已复制 ✓';setTimeout(()=>btn.textContent=t,1200);}});}}
function copyText(t,btn){{navigator.clipboard.writeText(t).then(()=>{{const o=btn.textContent;btn.textContent='✓';setTimeout(()=>btn.textContent=o,1200);}});}}
</script></body></html>"""
    open(os.path.join(out, "gallery.html"), "w", encoding="utf-8").write(doc)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="front", help="front 或 all（5 个机位）")
    ap.add_argument("--series", default="all", help="all 或 std,upper,sexy,duo 组合")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default=os.path.join(ROOT, "exports"))
    args = ap.parse_args()

    want_views = list(VIEW_CN) if args.views == "all" else ["front"]
    want_series = None if args.series == "all" else set(args.series.split(","))
    poses = [p for p in CATALOG if not want_series or p["series"] in want_series]
    if args.limit:
        poses = poses[: args.limit]
    poses.sort(key=lambda p: (p["series"] != "std", p["id"]))

    out = args.out
    img_dir = os.path.join(out, "images")
    os.makedirs(img_dir, exist_ok=True)  # 增量写入：已下载过的图会跳过，不删旧文件

    rows, ok, idx = [], 0, 0

    # 并发下载（当前网络到该站较慢，8 线程约 1~2 分钟）
    from concurrent.futures import ThreadPoolExecutor
    tasks = []
    for pose in poses:
        for view in pick_views(pose, want_views):
            tasks.append((pose, view, os.path.join(img_dir, f"{pose['id']}_{view}.webp")))

    def worker(t):
        pose, view, local = t
        return download(ASSET + pose["views"][view], local), pose, view

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        for success, pose, view in pool.map(worker, tasks):
            done += 1
            if success:
                ok += 1
                idx += 1
                rows.append(build(idx, pose, view))
            if done % 40 == 0:
                print(f"  已处理 {done}/{len(tasks)} 条…", flush=True)

    rows.sort(key=lambda r: r["no"])


    with open(os.path.join(out, "prompts.json"), "w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=1)

    with open(os.path.join(out, "poses.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["序号", "编号", "系列", "分级", "分类", "姿势名", "关键词", "机位",
                    "中文提示词", "英文提示词", "英文姿势描述", "线稿文件"])
        for r in rows:
            w.writerow([r["no"], r["id"], r["series_cn"], r["rating"], r["class_cn"], r["name_cn"],
                        r["keywords"], r["view_cn"], r["prompt_zh"], r["prompt_en"],
                        r["desc_en"], r["image"]])

    gallery(rows, out)

    zp = os.path.join(out, "poses.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(out):
            for fn in files:
                if fn == "poses.zip":
                    continue
                full = os.path.join(base, fn)
                z.write(full, os.path.relpath(full, out))

    size = sum(os.path.getsize(os.path.join(img_dir, f)) for f in os.listdir(img_dir)) / 1e6
    print(f"\n完成：{len(rows)} 条 / 图片 {ok} 张（{size:.1f} MB）")
    print(f"输出目录：{out}")
    print("   gallery.html  看图+复制提示词（双击打开）")
    print("   poses.csv     Excel 表格（含中英文提示词）")
    print("   prompts.json  结构化数据")
    print("   poses.zip     整包，可直接发给别人")


if __name__ == "__main__":
    main()
