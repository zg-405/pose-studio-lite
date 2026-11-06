# 姿态图鉴 · Pose Atlas

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Poses](https://img.shields.io/badge/poses-280-brightgreen.svg)](#里面有什么)
[![Static](https://img.shields.io/badge/no%20build-plain%20HTML-blue.svg)](index.html)

**280 个人物姿势参考（pose reference）**，每个都配好编号、分类和可直接复制的提示词。选一张姿势线稿，配上你的人物照片，就能让同一个人摆出任意姿态——用于 AI 绘画的图生图、换姿势、角色设定与分镜。

> Pose Atlas is a curated library of **280 pose reference sheets** for pose-guided image-to-image: pair a pose line art with a portrait, and the same person shows up in that pose. Every entry ships with a copy-ready prompt.

![姿态图鉴预览](docs/images/preview.jpg)

浏览方式：下载仓库，直接打开根目录的 [`index.html`](index.html)（纯静态，双击即看，无后端、无依赖、无需构建）

## 里面有什么

| 大类             |  数量 | 说明                            |
| -------------- | --: | ----------------------------- |
| 正常姿势 `normal/` | 107 | 坐、站、跪、躺、双人合影等，适合写真、电商、健身等内容场景 |
| 成人风格 `adult/`  | 173 | 姿态更具暗示性，页面默认模糊，点右上角「显示成人线稿」查看 |

每个姿势卡片包含：

- **编号 + 中文名**，如 `D042-踮脚单脚后踢站立`
- **分类与系列**（全身 / 半身 / 风格 / 双人；坐姿、站姿、躺姿…）
- **姿势线稿**（木偶人，白底线条，可直接当参考图喂给模型）
- **现成中文提示词**，已按「图1=人物照片、图2=姿势线稿」写好，一键复制
- **英文提示词**，喂 GPT-Image 等英文模型用
- 线稿下载

页面左侧是**两层目录**（大类 → 编号-姿势名），点条目直接跳到对应卡片；顶部可搜索、可按「只看正常 / 只看成人」筛选。

## 适用场景

| 场景 | 怎么用这个库 |
|---|---|
| AI 换姿势 / 图生图 | 一张人物照 + 一张线稿，保持长相换动作 |
| 人像写真、电商模特图 | 挑站姿 / 坐姿，配场景描述词批量出图 |
| 角色设定、漫画分镜 | 同一角色换不同姿势，快速对齐构图 |
| 健身 / 瑜伽 / 舞蹈动作参考 | 用动作幅度大的姿势做视觉参考 |
| 学习提示词写法 | 中英双语 + 结构化模板，可直接抄 |

## 怎么用

### 豆包 / 即梦

1. 对话框点 `＋`，一次传两张：**先传你的人物照片（图1）**，**再传这里的线稿（图2）**
2. 粘贴卡片里的中文提示词，末尾补一句场景/服装
3. 比例选 2:3 竖版 → 发送

> 豆包没有「人物参考」开关，靠多图 + 提示词里的编号点名用途，一定要写清「图1」「图2」，否则容易把两张图混成一个人。

### GPT-Image / 其他 API

同一套线稿与提示词，作为 `images/edits` 的第二张参考图提交即可（`image[]` 放人物照和线稿两张）。

## 效果示例

<table>
  <tr>
    <td align="center"><img src="docs/images/example-input.jpg" width="230"><br><sub>图1 · 人物照片</sub></td>
    <td align="center"><img src="docs/images/example-pose.png" width="230"><br><sub>图2 · 姿势线稿</sub></td>
    <td align="center"><img src="docs/images/example-output.jpg" width="230"><br><sub>生成结果（豆包）</sub></td>
  </tr>
</table>

一次真实使用（豆包，S008 站立竖叉）：保持人脸、服装、背景一致，仅重构姿势。

豆包里的实际对话——两张图一起传，复制本库卡片里的提示词，一次生成：

<img src="docs/images/example-chat.png" width="620" alt="豆包对话截图">

## 目录结构

```
.
├── index.html        # 总览页（目录 + 卡片墙 + 复制提示词）
├── normal/           # 正常姿势线稿 107 张（webp）
├── adult/            # 成人风格线稿 173 张（webp）
├── docs/images/      # 效果示例图
├── README.md
└── LICENSE
```

## 说明

- 本仓库全部内容**按 Apache License 2.0 完全公开**，可自由使用、修改、分发与商用（含专利授权）；再分发时保留 [LICENSE](LICENSE) 与版权声明即可。
- 用他人照片生成图像需取得肖像权授权；生成内容请依规添加 AI 生成标识（见《人工智能生成合成内容标识办法》）。
- 主流模型对「真人照片 + 性暗示姿势」类请求普遍会拒绝，属平台策略，与库本身无关。

## License

[Apache License 2.0](LICENSE) —— **全部公开**。页面代码、目录结构、280 张姿势线稿、提示词模板，一律可自由使用、修改、分发与商用，含明确专利授权；唯一要求是再分发时保留许可证与版权声明。

---

<sub>关键词：姿势参考 · 姿势库 · 人物姿势 · 线稿 · 图生图 · 换姿势 · AI 绘画参考图 · 提示词模板 · 豆包 · 即梦 · GPT-Image · Stable Diffusion · pose reference · pose library · pose sheet · image-to-image · character sheet · prompt template</sub>

