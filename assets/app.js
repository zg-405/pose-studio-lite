const ASSET = (view) => `https://yyta.tech/api/poses-assets/line/${view}`;
const VIEWS = { front: "正面", diag: "斜侧", side: "侧面", above: "俯视", below: "仰视" };
const SERIES = { all: "全部姿势", std: "全身", upper: "半身", sexy: "风格姿势", duo: "双人" };

const state = {
  poses: [],
  series: "all",
  category: "全部分类",
  keyword: "",
  limit: 24,
  adult: false,
  selected: null,
  angle: "front",
  file: null,
  imageData: "",
  size: "1024x1536",
  model: "fast",
  busy: false,
};

const $ = (id) => document.getElementById(id);
const el = {
  grid: $("grid"), search: $("search"), tabs: $("tabs"), category: $("category"),
  adult: $("adult"), count: $("poseCount"), count2: $("poseCount2"), total: $("poseTotal"),
  loadMore: $("loadMore"), poseRef: $("poseRef"), poseSelected: $("poseSelected"),
  upload: $("upload"), file: $("file"), prompt: $("prompt"), sizes: $("sizes"),
  models: $("models"), modelHint: $("modelHint"), key: $("key"), generate: $("generate"),
  msg: $("msg"), result: $("result"), resultBox: $("resultBox"), resultMeta: $("resultMeta"),
};

init();

async function init() {
  bind();
  try {
    const poses = await (await fetch("/api/catalog")).json();
    state.poses = poses.filter((p) => Object.keys(VIEWS).some((v) => p.views?.[v]));
    el.total.textContent = state.poses.length;
    render();
  } catch (e) {
    el.grid.innerHTML = `<p class="note err">姿势库加载失败：${e.message}</p>`;
  }
}

function bind() {
  el.search.addEventListener("input", (e) => {
    state.keyword = e.target.value.trim().toLowerCase();
    state.limit = 24;
    render();
  });

  el.tabs.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-series]");
    if (!btn) return;
    [...el.tabs.children].forEach((b) => b.classList.toggle("active", b === btn));
    state.series = btn.dataset.series;
    state.category = "全部分类";
    state.limit = 24;
    render();
  });

  el.category.addEventListener("change", (e) => {
    state.category = e.target.value;
    state.limit = 24;
    render();
  });

  el.adult.addEventListener("change", (e) => {
    state.adult = e.target.checked;
    render();
  });

  el.loadMore.addEventListener("click", () => {
    state.limit += 24;
    render();
  });

  el.grid.addEventListener("click", (e) => {
    const card = e.target.closest("[data-id]");
    if (!card) return;
    selectPose(state.poses.find((p) => p.id === card.dataset.id));
  });

  el.upload.addEventListener("click", () => el.file.click());
  el.upload.addEventListener("dragover", (e) => e.preventDefault());
  el.upload.addEventListener("drop", (e) => {
    e.preventDefault();
    takeFile(e.dataTransfer.files?.[0]);
  });
  el.file.addEventListener("change", (e) => takeFile(e.target.files?.[0]));

  el.sizes.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-size]");
    if (!btn) return;
    [...el.sizes.children].forEach((b) => b.classList.toggle("on", b === btn));
    state.size = btn.dataset.size;
  });

  el.models.addEventListener("click", (e) => {
    const btn = e.target.closest("button[data-model]");
    if (!btn) return;
    [...el.models.children].forEach((b) => b.classList.toggle("on", b === btn));
    state.model = btn.dataset.model;
    el.modelHint.textContent = state.model === "fast" ? "更快出图" : "细节更好";
  });

  el.generate.addEventListener("click", generate);
  $("composite").addEventListener("click", exportComposite);
}

/* 把「人物照片 + 姿势线稿」拼成一张，给只支持单图参考的模型用 */
async function exportComposite() {
  if (!state.selected) return setMsg("请先选择一个姿势", true);
  if (!state.imageData) return setMsg("请先上传人物照片", true);

  setMsg("正在合成参考图…");
  const W = 1600, H = 1100, PAD = 20, GAP = 16;
  const panelW = (W - PAD * 2 - GAP) / 2;
  const canvas = document.createElement("canvas");
  canvas.width = W;
  canvas.height = H;
  const ctx = canvas.getContext("2d");
  ctx.fillStyle = "#ffffff";
  ctx.fillRect(0, 0, W, H);

  const fit = (img, x) => {
    const s = Math.min(panelW / img.width, (H - PAD * 2) / img.height);
    const w = img.width * s, h = img.height * s;
    ctx.drawImage(img, x + (panelW - w) / 2, PAD + (H - PAD * 2 - h) / 2, w, h);
  };

  try {
    const [person, pose] = await Promise.all([
      loadImage(state.imageData),
      loadImage(`/api/pose-image?id=${state.selected.id}&view=${state.angle}`),
    ]);
    fit(person, PAD);
    fit(pose, PAD + panelW + GAP);
    ctx.strokeStyle = "#e8e7e1";
    ctx.beginPath();
    ctx.moveTo(PAD + panelW + GAP / 2, 40);
    ctx.lineTo(PAD + panelW + GAP / 2, H - 40);
    ctx.stroke();

    const a = document.createElement("a");
    a.href = canvas.toDataURL("image/jpeg", 0.92);
    a.download = `ref-${state.selected.id}-${state.angle}.jpg`;
    a.click();
    setMsg("已合成：左边人物、右边线稿。提示词写「左半部分的人物摆出右半部分线稿的姿势」");
  } catch (e) {
    setMsg("合成失败：" + e.message, true);
  }
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.crossOrigin = "anonymous";
    img.onload = () => resolve(img);
    img.onerror = () => reject(new Error("图片加载失败"));
    img.src = src;
  });
}

function currentList() {
  return state.poses.filter((p) => {
    if (state.series !== "all" && p.series !== state.series) return false;
    if (state.category !== "全部分类" && p.class_cn !== state.category) return false;
    if (state.keyword) {
      const hay = `${p.name_cn} ${p.id} ${p.class_cn} ${p.name_en}`.toLowerCase();
      if (!hay.includes(state.keyword)) return false;
    }
    return true;
  });
}

function render() {
  // 分类下拉跟随当前 series
  const cats = [...new Set(state.poses.filter((p) => state.series === "all" || p.series === state.series)
    .map((p) => p.class_cn).filter(Boolean))];
  el.category.innerHTML = ["全部分类", ...cats].map((c) => `<option${c === state.category ? " selected" : ""}>${c}</option>`).join("");

  const list = currentList();
  el.count.textContent = list.length;
  el.count2.textContent = String(list.length).padStart(2, "0");

  el.grid.innerHTML = list.slice(0, state.limit).map((p) => {
    const view = Object.keys(VIEWS).find((v) => p.views[v]);
    const masked = p.rating === "suggestive" && !state.adult;
    const selected = state.selected?.id === p.id;
    return `
      <button class="pose-card ${selected ? "selected" : ""}" data-id="${p.id}" title="${p.name_cn}">
        <div class="pose-image">
          <img class="${masked ? "blur" : ""}" loading="lazy" src="${ASSET(p.views[view])}" alt="${p.name_cn}" />
          ${masked ? '<span class="blur-label">成人风格</span>' : ""}
          <span class="pose-number">${p.id}</span>
        </div>
        <div class="pose-caption"><span>${p.name_cn}</span><small>${p.class_cn || ""}</small></div>
      </button>`;
  }).join("");

  el.loadMore.hidden = list.length <= state.limit;
  el.loadMore.textContent = `查看更多姿势（还有 ${Math.max(0, list.length - state.limit)} 个）`;
}

function selectPose(pose) {
  if (!pose) return;
  state.selected = pose;
  if (!pose.views[state.angle]) state.angle = Object.keys(VIEWS).find((v) => pose.views[v]);
  render();
  renderPoseRef();
  el.result.hidden = true;
  el.msg.textContent = "";
  if (window.innerWidth < 1080) $("create").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderPoseRef() {
  const p = state.selected;
  if (!p) return;
  el.poseSelected.textContent = `${p.id} · ${p.class_cn || ""}`;
  el.poseRef.innerHTML = `
    <div class="pose-ref-main">
      <img src="${ASSET(p.views[state.angle] || p.views.front)}" alt="${p.name_cn}" />
      <div class="pose-ref-info">
        <b>${p.name_cn}</b>
        <small>${p.name_en || ""}</small>
        <div class="views">
          ${Object.keys(VIEWS).filter((v) => p.views[v]).map((v) => `
            <button data-view="${v}" class="${v === state.angle ? "on" : ""}">${VIEWS[v]}</button>`).join("")}
        </div>
      </div>
    </div>`;
  el.poseRef.querySelectorAll("[data-view]").forEach((b) => {
    b.addEventListener("click", () => {
      state.angle = b.dataset.view;
      renderPoseRef();
    });
  });
}

async function takeFile(file) {
  if (!file) return;
  if (!/^image\/(jpeg|png|webp)$/.test(file.type)) return setMsg("请选择 JPG / PNG / WebP 图片", true);
  if (file.size > 10 * 1024 * 1024) return setMsg("图片需小于 10 MB", true);

  state.file = file;
  const preview = URL.createObjectURL(file);
  el.upload.classList.add("has-image");
  el.upload.innerHTML = `<img src="${preview}" alt="已上传照片" /><small>点击更换图片</small>`;

  try {
    state.imageData = await compress(file, 2048, 0.88);
    setMsg("");
  } catch (err) {
    setMsg("图片处理失败，请换一张", true);
  }
}

function compress(file, maxSide, quality) {
  return new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => {
      const scale = Math.min(1, maxSide / Math.max(img.width, img.height));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext("2d").drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/jpeg", quality));
    };
    img.onerror = reject;
    img.src = URL.createObjectURL(file);
  });
}

function setMsg(text, isErr = false) {
  el.msg.textContent = text;
  el.msg.className = "note" + (isErr ? " err" : "");
}

async function generate() {
  if (state.busy) return;
  if (!state.selected) return setMsg("请先选择一个姿势", true);
  if (!state.imageData) return setMsg("请先上传人物照片", true);

  state.busy = true;
  el.generate.disabled = true;
  el.generate.textContent = "正在生成画面…";
  el.result.hidden = false;
  el.resultMeta.textContent = "";
  el.resultBox.innerHTML = `<p class="loading">正在结合人物照片与所选姿势生成图片，请稍候…</p>`;
  setMsg("");

  const started = performance.now();
  try {
    const res = await fetch("/api/generate", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({
        image: state.imageData,
        poseId: state.selected.id,
        angle: state.angle,
        prompt: el.prompt.value,
        size: state.size,
        model: state.model,
        apiKey: el.key.value.trim(),
      }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || `生成失败 HTTP ${res.status}`);

    const secs = ((performance.now() - started) / 1000).toFixed(1);
    el.resultBox.innerHTML = `<img src="${data.url}" alt="生成结果" />
      <a href="${data.url}" download="pose-studio.png" target="_blank" rel="noreferrer">打开原图保存</a>`;
    el.resultMeta.textContent = `${data.model || "demo"} · ${secs}s · ${data.requestId || ""}`;
    if (data.mock) setMsg("DEMO 模式：未调用真实模型，填入密钥后即为真实生成");
    console.log("prompt sent upstream:\n" + (data.prompt || "(demo)"));
  } catch (err) {
    el.resultBox.innerHTML = `<p class="loading">生成失败</p>`;
    setMsg(err.message, true);
  } finally {
    state.busy = false;
    el.generate.disabled = false;
    el.generate.textContent = "开始以图生图";
  }
}
