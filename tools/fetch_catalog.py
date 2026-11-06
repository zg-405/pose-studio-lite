#!/usr/bin/env python3
"""把姿势库目录抓成本地 data/catalog.json（仅供本地研究/自建姿势库参考）

⚠️ 该目录数据来源为第三方站点，版权不归本项目所有。
   请勿把抓取结果提交到公开仓库，也不要随产品对外分发。

用法:
    python3 tools/fetch_catalog.py
"""
import json
import os
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.environ.get("CATALOG_SOURCE", "https://yyta.tech/api/catalog")
DST = os.path.join(ROOT, "data/catalog.json")


def main():
    req = urllib.request.Request(SRC, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read().decode())
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(DST, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    general = sum(1 for p in data if p.get("rating") == "general")
    print(f"已写入 {DST}：共 {len(data)} 条（general {general} 条）")
    print("提醒：仅本地研究使用，勿提交到公开仓库。")


if __name__ == "__main__":
    main()
