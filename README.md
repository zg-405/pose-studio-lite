# Pose Studio Lite

> 用「姿势线稿 + 人物照片」双参考做图生图的最小可运行实现。纯 Python 标准库 + 原生 JS，零依赖、零构建。

A minimal, dependency-free implementation of **pose-guided image-to-image**: pick a pose reference, upload a portrait, get the same person in that pose. Python stdlib backend + vanilla frontend.

---

## 效果示例

一次真实使用：**图1（人物照片）+ 图2（姿势线稿）+ 一段提示词 → 成片**。姿势线稿来自本项目导出的测试包（站立竖叉・手抓脚踝），模型用的是豆包（即梦同源模型），人物长相、服装、室内背景保持一致，仅姿势被重构。

| 图1 · 人物照片 | 图2 · 姿势线稿 | 生成结果 |
|:---:|:---:|:---:|
| ![人物照片](docs/images/example-input.jpg) | ![姿势线稿](docs/images/example-pose.png) | ![生成结果](docs/images/example-output.jpg) |

提示词（本项目的模板 + 场景补充）：

```text
图1是人物照片，图2是姿势参考线稿。以图1中的人物为唯一主体，保持其面部特征、
发型、肤色、体型完全一致，不要改变长相。让人物摆出图2线稿的姿势：站姿——站立
竖叉，手抓脚踝（I字）。正面平视机位，全身入镜。写实摄影风格，自然柔和光线，背
景干净，无文字无水印。场景/服装补充：人物是带着口罩的，两只脚都穿着黑色红底高
跟鞋，背景继续使用图1中的。
```

豆包里的实际对话（两张图上传 + 上面这段提示词，一次生成成功）：

![豆包对话截图](docs/images/example-chat.png)

> 同样的「线稿 + 提示词」组合也可以喂给 GPT-Image、即梦、可灵等任何支持参考图的模型，`make_kit.py` 导出的测试包就是为这种横向对比准备的。

---

## 它解决什么问题

多数图生图工具让用户用文字描述姿势，结果不可控。这里把姿势变成**结构化的参考图**：每个姿势带多机位线稿 + 英文动作描述，模型只需回答"让这个人摆出这张图的姿势"，姿势准确率大幅提升，用户也不用学写 prompt。

## 特性

- **姿势库**：多机位（正面 / 斜侧 / 侧面 / 俯视 / 仰视）、分类筛选、搜索、分级开关
- **双参考图管线**：人物照 → `image`，姿势线稿 → 第二张参考（`POSE_IMAGE=1`），或用文字描述姿势
- **提示词模板**：把姿势的英文 `desc` + 机位 + 用户场景拼成结构化 prompt，避免用户手写
- **DEMO 模式**：不填密钥也能跑通全流程（返回占位图，不产生费用）
- **上游可替换**：任何兼容 OpenAI `images/edits` 的服务或中转都行，一个环境变量切过去
- **素材导出**：`export_poses.py` / `make_kit.py` 可导出「线稿 + 中英提示词」测试包，用于人工对比不同模型

## 快速开始

```bash
git clone <your-repo> && cd pose-studio-lite
python3 server.py          # 默认 http://127.0.0.1:8765
```

打开页面 → 选姿势 → 上传照片 → 密钥留空直接点生成（DEMO 模式）。

接真实模型：

```bash
OPENAI_BASE_URL=https://api.openai.com/v1 \
MODEL_FAST=gpt-image-2.5-flare \
MODEL_QUALITY=gpt-image-2.5-sunburst \
POSE_IMAGE=1 \
python3 server.py
```

然后在页面「API 密钥」里填入你的 key（只存浏览器 localStorage，不上传服务器）。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `PORT` | `8765` | 监听端口 |
| `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 上游地址，可换任意兼容服务 |
| `MODEL_FAST` | `gpt-image-2.5-flare` | 「速度更快」档 |
| `MODEL_QUALITY` | `gpt-image-2.5-sunburst` | 「质量更高」档 |
| `POSE_IMAGE` | `0` | `1` = 把线稿作为第二张参考图一起发给上游 |
| `CATALOG_PATH` | 自动 | 自定义姿势库 JSON 路径 |

## 接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/catalog` | 姿势库全量 JSON |
| GET | `/api/config` | 当前模型映射、姿势数量 |
| GET | `/api/pose-image?id=P002&view=front` | 同源代理姿势图（用于 canvas 合成参考图） |
| POST | `/api/generate` | `{image, poseId, angle, prompt, size, model, apiKey}` → `{url}` |

## 自己加姿势

姿势库就是一个 JSON 数组，字段见 `data/catalog.sample.json`。最小要求：

```json
{
  "id": "M001", "series": "std", "rating": "general",
  "class_cn": "坐姿", "name_cn": "盘腿坐", "name_en": "Cross-legged sitting",
  "desc_en": "sitting on the floor cross-legged, hands resting on knees, back straight",
  "views": { "front": "mypose_M001_front.webp" }
}
```

`desc_en` 是效果的关键——写清肢体朝向、支撑点、躯干角度，模型才摆得准。线稿图放在你能访问的地址，改 `server.py` 里的 `ASSET` 前缀即可。

> 有完整库时放到 `data/catalog.json`（已被 `.gitignore` 忽略），服务会自动优先加载；`tools/fetch_catalog.py` 仅用于本地研究抓取。

## 导出测试包

```bash
python3 make_kit.py P002 S008 --views front,diag   # 单姿势测试卡
python3 export_poses.py --series std --limit 50    # 批量导出 CSV + 画廊
```

产出包含线稿 PNG、中英提示词、可直接复制提示词的 `index.html`，适合拿去豆包 / 即梦 / 其他模型做人工 A/B。

## 设计取舍

- **单文件后端**：不上框架，是为了让人 10 分钟读完、能直接改。要上生产请自行加队列、限流、鉴权。
- **密钥存前端**：省掉账号体系，适合内部工具；面向公众的产品建议换成登录 + 服务端计费。
- **同步生成**：GPT-Image 一次 10~60s，长连接容易超时；生产建议改异步任务 + 轮询（`/api/result` 模式）。

## 已知限制

- 无用户系统、无计费、无结果持久化（图片链接有有效期，需及时保存）
- 并发能力有限（`ThreadingHTTPServer` 够个人用，不够多用户）
- 上游内容审核会拒绝「真人照片 + 性暗示姿势」类请求，这是平台策略，不是代码问题

## 素材与数据声明

本仓库**不包含**任何第三方姿势线稿或完整姿势库数据：

- `data/catalog.sample.json` 仅为字段格式示例
- 线稿图需自行创作（3D 人偶渲染 / 手绘 / OpenPose 骨骼图）或取得授权
- README 示例图中的人物为项目作者本人（已授权展示）
- 用于生成他人肖像需获得授权；生成内容请遵守当地法律与平台规则，并依规添加 AI 生成标识

## License

MIT，见 [LICENSE](LICENSE)。
