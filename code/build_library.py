#!/usr/bin/env python3
"""把整库拆成「正常 / 成人」两大类，导出图片 + 带目录的单页 HTML

用法:
    python3 build_library.py                 # 全部，正面机位
    python3 build_library.py --views front,diag
    python3 build_library.py --out exports_library

产出:
    exports_library/index.html      总目录页（左侧目录 + 搜索 + 卡片墙）
    exports_library/normal/*.png    正常姿势线稿（rating=general）
    exports_library/adult/*.png     成人风格线稿（rating=suggestive，默认模糊，可一键显示）
"""
import argparse
import html
import json
import os
import re
import subprocess
import urllib.request
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.abspath(__file__))
CATALOG = json.load(open(os.path.join(ROOT, "data/catalog.json"), encoding="utf-8"))
ASSET = "https://yyta.tech/api/poses-assets/line/"
VIEW_CN = {"front": "正面", "diag": "斜侧", "side": "侧面", "above": "俯视", "below": "仰视"}
VIEW_CAM = {"front": "正面平视机位", "diag": "斜侧 45 度机位", "side": "正侧面机位",
            "above": "俯拍机位，镜头从上往下", "below": "仰拍机位，镜头从下往上"}
VIEW_EN = {"front": "front view at eye level", "diag": "three-quarter view",
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
    name = p["name_cn"].replace("・", "，").replace("·", "，")
    return f"{p.get('class_cn','')}——{name}" if p.get("class_cn") else name


def pick(p, views):
    if views == ["front"]:
        v = "front" if p["views"].get("front") else next((k for k in VIEW_CN if p["views"].get(k)), None)
        return [v] if v else []
    return [v for v in views if p["views"].get(v)]


def grab(url, path, retries=2):
    if os.path.exists(path) and os.path.getsize(path) > 1024:
        return True
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) > 1024:
                open(path, "wb").write(data)
                return True
        except Exception:
            pass
    return False


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--views", default="front")
    ap.add_argument("--out", default=os.path.join(ROOT, "exports_library"))
    ap.add_argument("--format", default="png", choices=["png", "webp"],
                    help="png=通用（体积大）；webp=保留原始线稿（体积约为 1/8，适合上仓库）")
    args = ap.parse_args()

    out = args.out
    ext = "." + args.format
    dirs = {"normal": os.path.join(out, "normal"), "adult": os.path.join(out, "adult")}
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)
    views = [v.strip() for v in args.views.split(",") if v.strip()]

    # 1) 并发下载（png 模式额外转码）
    tasks = []
    for p in CATALOG:
        bucket = "normal" if p.get("rating") == "general" else "adult"
        for v in pick(p, views):
            fname = f"{p['id']}_{v}"
            tasks.append((p, v, bucket, os.path.join(dirs[bucket], fname)))

    total = len(tasks)
    print(f"待处理 {total} 张…", flush=True)
    done = 0

    def work(t):
        p, v, bucket, base = t
        src, dst = base + ".webp", base + ext
        if os.path.exists(dst) and os.path.getsize(dst) > 1024:  # 已就绪，跳过
            return True, p, v, bucket, os.path.basename(dst)
        if not os.path.exists(src) or os.path.getsize(src) < 1024:
            if not grab(ASSET + p["views"][v], src):
                return False, p, v, bucket, os.path.basename(dst)
        if args.format == "webp":
            return True, p, v, bucket, os.path.basename(src)
        subprocess.run(["sips", "-s", "format", "png", src, "--out", dst],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return os.path.exists(dst), p, v, bucket, os.path.basename(dst)

    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        for r in pool.map(work, tasks):
            done += 1
            results.append(r)
            if done % 40 == 0:
                print(f"  {done}/{total}", flush=True)

    # 2) 组装数据
    by_pose = {}
    for ok, p, v, bucket, fname in results:
        if not ok:
            continue
        e = by_pose.setdefault(p["id"], {"pose": p, "bucket": bucket, "files": {}})
        e["files"][v] = fname

    groups = {"normal": [], "adult": []}
    for e in by_pose.values():
        groups[e["bucket"]].append(e)

    for key in groups:
        groups[key].sort(key=lambda e: (e["pose"]["series"], e["pose"]["id"]))

    # 3) 生成卡片
    def card(e, idx):
        p, bucket = e["pose"], e["bucket"]
        zh = ZH.format(pose=pose_zh(p), cam=VIEW_CAM["front"], frame=FRAME.get(p["series"], "全身入镜"))
        en = EN.format(desc=(p["desc_en"] or "").strip().rstrip(".") + ".",
                       cam=VIEW_EN["front"], frame=FRAME.get(p["series"], "全身入镜"))
        imgs = "".join(
            f'<figure><img src="{bucket}/{fn}" alt="{html.escape(p["name_cn"])}" loading="lazy">'
            f'<figcaption>{VIEW_CN[v]}</figcaption></figure>' for v, fn in e["files"].items())
        cls = "card adult" if bucket == "adult" else "card"
        return f"""
      <article class="{cls}" data-id="{p['id']}" data-cat="{html.escape(p.get('class_cn',''))}"
               data-series="{p['series']}" data-text="{html.escape((p['name_cn']+' '+p['id']+' '+(p.get('class_cn') or '')).lower())}" id="c-{p['id']}">
        <div class="thumbs">{imgs}</div>
        <div class="info">
          <div class="title"><b>{p['id']}</b><span>{html.escape(p['name_cn'])}</span></div>
          <div class="tags"><i>{SERIES_CN.get(p['series'], p['series'])}</i><i>{html.escape(p.get('class_cn',''))}</i></div>
          <div class="prompt" id="zh-{p['id']}">{html.escape(zh)}</div>
          <div class="actions">
            <button onclick="cp('zh-{p['id']}',this)">复制中文</button>
            <button class="ghost" data-en="{html.escape(en)}" onclick="cpText(this.dataset.en,this)">英文</button>
            <a href="{bucket}/{list(e['files'].values())[0]}" download>下载线稿</a>
          </div>
        </div>
      </article>"""

    sections = []
    toc_groups = []
    for key, label, desc in (
        ("normal", "正常姿势", "rating = general，可直接用于写真、电商、健身等内容场景"),
        ("adult", "成人风格", "rating = suggestive，姿态更具暗示性；默认模糊，点右上角「显示成人线稿」查看"),
    ):
        items = groups[key]
        if not items:
            continue
        sections.append(f'<section id="sec-{key}" class="section"><div class="sec-head">'
                        f'<h2>{label} <em>{len(items)}</em></h2><p>{desc}</p></div>')
        # 主区按分类分组
        cats = {}
        for e in items:
            cats.setdefault(e["pose"].get("class_cn") or "其他", []).append(e)
        for cat, arr in cats.items():
            anchor = f'{key}-{slug(cat) or "x"}'
            sections.append(f'<div class="cat" id="{anchor}"><h3>{html.escape(cat)} <span>{len(arr)}</span></h3><div class="grid">')
            sections.extend(card(e, i) for i, e in enumerate(arr))
            sections.append('</div></div>')
        sections.append('</section>')

        # 侧边目录：两层 —— 大类 → 每个姿势「编号-名称」
        lis = []
        for e in sorted(items, key=lambda x: x["pose"]["id"]):
            p = e["pose"]
            text = f"{p['id']} {p['name_cn']} {p.get('class_cn') or ''}".lower()
            lis.append(f'<li data-text="{html.escape(text)}">'
                       f'<a href="#c-{p["id"]}"><b>{p["id"]}</b>{html.escape(p["name_cn"])}</a></li>')
        open_attr = " open" if key == "normal" else ""
        toc_groups.append(
            f'<details class="toc-group" data-bucket="{key}"{open_attr}>'
            f'<summary>{label}<em>{len(items)}</em></summary>'
            f'<ul>{"".join(lis)}</ul></details>')

    total_imgs = sum(len(e["files"]) for e in by_pose.values())
    doc = f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>姿势库总览 · 正常 {len(groups['normal'])} / 成人 {len(groups['adult'])}</title>
<style>
:root{{--bg:#f7f6f2;--card:#fff;--ink:#262b24;--ink2:#6f776c;--ink3:#9aa094;--line:#e8e7e1;--g:#343e32;--g2:#566a4f;--warn:#a4603f}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:14px/1.65 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
header{{background:#fff;border-bottom:1px solid var(--line);padding:18px 26px;position:sticky;top:0;z-index:20}}
header h1{{font-size:19px;margin:0 0 4px}}
header p{{margin:0;color:var(--ink3);font-size:12.5px}}
.toolbar{{display:flex;gap:8px;align-items:center;margin-top:12px;flex-wrap:wrap}}
input[type=search]{{height:34px;border:1px solid var(--line);border-radius:9px;padding:0 12px;min-width:260px;outline:none;background:#fbfbf9}}
input[type=search]:focus{{border-color:#a1b496}}
button{{border:1px solid var(--line);background:#fbfbf9;color:var(--ink2);border-radius:8px;padding:6px 12px;font-size:13px;cursor:pointer}}
button.on{{background:var(--g);color:#fff;border-color:var(--g)}}
button.warn{{border-color:#e8d5cc;color:var(--warn)}}
.layout{{display:grid;grid-template-columns:236px minmax(0,1fr);gap:24px;max-width:1560px;margin:0 auto;padding:22px 26px 80px}}
aside{{position:sticky;top:132px;align-self:start;max-height:calc(100vh - 160px);overflow:auto;
  background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}}
aside h4{{margin:0 0 8px;font-size:12px;color:var(--ink3);letter-spacing:.08em;text-transform:uppercase}}
.toc-group{{border-bottom:1px solid #f0efea}}
.toc-group:last-child{{border-bottom:none}}
.toc-group summary{{cursor:pointer;list-style:none;padding:8px;font-size:13px;font-weight:600;color:var(--ink);
  display:flex;align-items:center;gap:7px;border-radius:8px}}
.toc-group summary::-webkit-details-marker{{display:none}}
.toc-group summary::before{{content:"▸";font-size:10px;color:var(--ink3);transition:transform .15s}}
.toc-group[open] summary::before{{transform:rotate(90deg)}}
.toc-group summary:hover{{background:#f5f6f2}}
.toc-group summary em{{margin-left:auto;font-style:normal;font-size:11px;font-weight:600;color:var(--g2);
  background:#eef1ea;border-radius:999px;padding:0 7px;min-width:24px;text-align:center}}
.toc-group ul{{list-style:none;margin:0 0 8px;padding:0 0 0 4px;max-height:44vh;overflow:auto}}
.toc-group li a{{display:flex;gap:7px;padding:4px 8px;border-radius:6px;text-decoration:none;color:var(--ink2);font-size:12px;line-height:1.5}}
.toc-group li a:hover{{background:#f2f4ef;color:var(--g)}}
.toc-group li b{{color:var(--ink3);font-weight:600;flex:0 0 auto}}
.section{{margin-bottom:34px}}
.sec-head h2{{font-size:18px;margin:0 0 4px}}
.sec-head h2 em{{font-size:12px;font-style:normal;color:var(--g2);background:#eef1ea;border-radius:999px;padding:2px 8px;margin-left:6px;vertical-align:middle}}
.sec-head p{{margin:0 0 14px;color:var(--ink3);font-size:12.5px}}
.cat h3{{font-size:13.5px;margin:18px 0 10px;color:var(--ink2);font-weight:600}}
.cat h3 span{{color:var(--ink3);font-weight:400;font-size:12px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(234px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;overflow:hidden;display:flex;flex-direction:column}}
.thumbs{{display:flex;background:#f1f0ea}}
.thumbs figure{{margin:0;flex:1;text-align:center}}
.thumbs img{{width:100%;aspect-ratio:1/1;object-fit:contain;display:block}}
.thumbs figcaption{{font-size:10.5px;color:var(--ink3);padding-bottom:5px}}
.info{{padding:10px 12px 12px;display:flex;flex-direction:column;gap:6px;flex:1}}
.title{{display:flex;gap:6px;align-items:baseline}}
.title b{{font-size:11px;background:var(--g);color:#fff;border-radius:4px;padding:1px 5px;font-weight:600}}
.title span{{font-size:13px;line-height:1.35}}
.tags{{display:flex;gap:5px;flex-wrap:wrap}}
.tags i{{font-style:normal;font-size:11px;background:#f2f4ef;color:var(--g2);border-radius:5px;padding:1px 7px}}
.prompt{{font-size:11.5px;color:var(--ink2);background:#fbfbf9;border:1px solid var(--line);border-radius:8px;padding:8px;line-height:1.55;max-height:88px;overflow:auto}}
.actions{{display:flex;gap:6px;align-items:center;margin-top:auto;padding-top:4px}}
.actions button{{padding:4px 10px;font-size:12px}}
.actions a{{font-size:12px;color:var(--g2);text-decoration:none;font-weight:600;margin-left:auto}}
/* 成人分区默认模糊 */
.adult .thumbs img{{filter:blur(12px);transition:.2s}}
body.reveal .adult .thumbs img{{filter:none}}
.empty{{padding:40px;text-align:center;color:var(--ink3);font-size:13px}}
@media(max-width:960px){{
  .layout{{grid-template-columns:1fr;padding:16px}}
  aside{{position:static;max-height:none}}
}}
</style></head><body>
<header>
  <h1>姿势库总览 · 正常 {len(groups['normal'])} 个 / 成人风格 {len(groups['adult'])} 个</h1>
  <p>共 {len(by_pose)} 个姿势、{total_imgs} 张线稿。每个姿势含编号、分类、可直接复制的中英文提示词（已按「图1人物 / 图2姿势」写好）。</p>
  <div class="toolbar">
    <input type="search" id="q" placeholder="搜索姿势名 / 编号 / 分类">
    <button class="on" data-f="all">全部</button>
    <button data-f="general">只看正常</button>
    <button data-f="adult">只看成人</button>
    <button class="warn" id="reveal">显示成人线稿</button>
  </div>
</header>
<div class="layout">
  <aside>
    <h4>目录</h4>
    <div id="toc">{''.join(toc_groups)}</div>
  </aside>
  <main id="main">
    {''.join(sections)}
    <p class="empty" id="empty" hidden>没有匹配的姿势，换个关键词试试。</p>
  </main>
</div>
<script>
const cards=[...document.querySelectorAll('.card')];
let filter='all', kw='';
function apply(){{
  let shown=0;
  cards.forEach(c=>{{
    const inBucket = filter==='all' || (filter==='general' ? !c.classList.contains('adult') : c.classList.contains('adult'));
    const hit = !kw || c.dataset.text.includes(kw);
    const ok = inBucket && hit;
    c.style.display = ok ? '' : 'none';
    if(ok) shown++;
  }});
  document.querySelectorAll('.cat').forEach(g=>{{
    const visible=[...g.querySelectorAll('.card')].some(c=>c.style.display!=='none');
    g.style.display = visible ? '' : 'none';
  }});
  document.querySelectorAll('.section').forEach(s=>{{
    const visible=[...s.querySelectorAll('.card')].some(c=>c.style.display!=='none');
    s.style.display = visible ? '' : 'none';
  }});
  document.getElementById('empty').hidden = shown>0;
  // 目录：两层结构跟随过滤
  document.querySelectorAll('.toc-group').forEach(g=>{{
    const bucketOk = filter==='all' || (filter==='normal' ? g.dataset.bucket==='normal' : g.dataset.bucket==='adult');
    let visible=0;
    g.querySelectorAll('li').forEach(li=>{{
      const hit = !kw || li.dataset.text.includes(kw);
      const ok = bucketOk && hit;
      li.style.display = ok ? '' : 'none';
      if(ok) visible++;
    }});
    g.style.display = (bucketOk && visible) ? '' : 'none';
    const em = g.querySelector('summary em');
    if(em) em.textContent = visible;
    if(kw && visible) g.open = true;
  }});
}}
document.getElementById('q').oninput=e=>{{kw=e.target.value.trim().toLowerCase();apply();}};
document.querySelectorAll('[data-f]').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('[data-f]').forEach(x=>x.classList.remove('on'));
  b.classList.add('on'); filter=b.dataset.f; apply();
}});
const rv=document.getElementById('reveal');
if(localStorage.getItem('pose-reveal')==='1'){{document.body.classList.add('reveal');rv.textContent='隐藏成人线稿';}}
rv.onclick=()=>{{
  const on=document.body.classList.toggle('reveal');
  localStorage.setItem('pose-reveal', on?'1':'0');
  rv.textContent = on ? '隐藏成人线稿' : '显示成人线稿';
}};
function cp(id,b){{navigator.clipboard.writeText(document.getElementById(id).textContent.trim()).then(()=>{{
  const t=b.textContent;b.textContent='已复制 ✓';setTimeout(()=>b.textContent=t,1200);}});}}
function cpText(t,b){{navigator.clipboard.writeText(t).then(()=>{{
  const o=b.textContent;b.textContent='✓';setTimeout(()=>b.textContent=o,1200);}});}}
apply();
</script></body></html>"""

    open(os.path.join(out, "index.html"), "w", encoding="utf-8").write(doc)
    print(f"\n完成：正常 {len(groups['normal'])} / 成人 {len(groups['adult'])}，线稿 {total_imgs} 张")
    print(f"页面：{os.path.join(out, 'index.html')}")


if __name__ == "__main__":
    main()
