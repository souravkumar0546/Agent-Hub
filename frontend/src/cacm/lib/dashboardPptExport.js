// Build a PowerPoint deck from the LIVE Stage-6 dashboard DOM.
//
// We screenshot each chart card (and the KPI tile row) using html-to-image
// and embed each as a slide image. This way the deck matches whatever the
// user sees on screen — same charts, colours, theme — instead of the
// kiddish native pptxgenjs charts we tried first.

import PptxGenJS from "pptxgenjs";
import { toPng } from "html-to-image";

// PPT slide geometry (LAYOUT_WIDE = 13.333" × 7.5").
const SLIDE_W = 13.333;
const SLIDE_H = 7.5;
const TITLE_BLOCK_H = 1.0;     // header (title + subtitle)
const MARGIN_X = 0.4;
const MARGIN_Y_BOTTOM = 0.3;
const IMAGE_BOX_W = SLIDE_W - 2 * MARGIN_X;
const IMAGE_BOX_H = SLIDE_H - TITLE_BLOCK_H - MARGIN_Y_BOTTOM - 0.2;

const ACCENT = "8B5CF6";
const INK = "111827";
const INK_DIM = "6B7280";

function resolveBackground(node) {
  // Walk up until we find a non-transparent background-color so the screenshot
  // doesn't render with a see-through background (which dom-to-image fills
  // with black by default in some browsers).
  let cur = node;
  while (cur && cur !== document.body) {
    const bg = window.getComputedStyle(cur).backgroundColor;
    if (bg && bg !== "rgba(0, 0, 0, 0)" && bg !== "transparent") return bg;
    cur = cur.parentElement;
  }
  return window.getComputedStyle(document.body).backgroundColor || "#ffffff";
}

async function captureNode(node, scale = 2) {
  return await toPng(node, {
    pixelRatio: scale,
    backgroundColor: resolveBackground(node),
    cacheBust: true,
    // Skip decorative elements that don't render well in a static snapshot
    // (e.g. recharts tooltips that may be open at capture time).
    filter: (el) => {
      if (!el || !el.classList) return true;
      const skip = ["recharts-tooltip-wrapper"];
      return !skip.some((c) => el.classList.contains(c));
    },
  });
}

function getImageDimensions(dataUrl) {
  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => resolve({ w: img.naturalWidth, h: img.naturalHeight });
    img.onerror = () => resolve({ w: IMAGE_BOX_W, h: IMAGE_BOX_H });
    img.src = dataUrl;
  });
}

function fitToBox(srcW, srcH, boxW, boxH) {
  if (!srcW || !srcH) return { w: boxW, h: boxH };
  const sourceRatio = srcW / srcH;
  const boxRatio = boxW / boxH;
  if (sourceRatio > boxRatio) {
    return { w: boxW, h: boxW / sourceRatio };
  }
  return { w: boxH * sourceRatio, h: boxH };
}

function addHeader(slide, title, subtitle) {
  slide.addText(title, {
    x: MARGIN_X,
    y: 0.3,
    w: SLIDE_W - 2 * MARGIN_X,
    h: 0.55,
    fontSize: 22,
    bold: true,
    color: INK,
    fontFace: "Calibri",
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: MARGIN_X,
      y: 0.85,
      w: SLIDE_W - 2 * MARGIN_X,
      h: 0.35,
      fontSize: 12,
      color: INK_DIM,
      fontFace: "Calibri",
    });
  }
}

async function addImageSlide(pptx, { title, subtitle, dataUrl }) {
  const slide = pptx.addSlide();
  slide.background = { color: "FFFFFF" };
  addHeader(slide, title, subtitle);
  if (!dataUrl) return;
  const dims = await getImageDimensions(dataUrl);
  const { w, h } = fitToBox(dims.w, dims.h, IMAGE_BOX_W, IMAGE_BOX_H);
  const x = (SLIDE_W - w) / 2;
  const y = TITLE_BLOCK_H + (IMAGE_BOX_H - h) / 2;
  slide.addImage({ data: dataUrl, x, y, w, h });
}

function addCoverSlide(pptx, { title, subtitle, runId }) {
  const slide = pptx.addSlide();
  slide.background = { color: "F5F3FF" };
  slide.addText(title, {
    x: 0.6,
    y: 2.2,
    w: SLIDE_W - 1.2,
    h: 1.2,
    fontSize: 40,
    bold: true,
    color: INK,
    fontFace: "Calibri",
  });
  if (subtitle) {
    slide.addText(subtitle, {
      x: 0.6,
      y: 3.4,
      w: SLIDE_W - 1.2,
      h: 0.6,
      fontSize: 18,
      color: ACCENT,
      fontFace: "Calibri",
    });
  }
  slide.addText(`Run #${runId}  ·  Stage 6 — Dashboard`, {
    x: 0.6,
    y: 4.1,
    w: SLIDE_W - 1.2,
    h: 0.5,
    fontSize: 14,
    color: INK_DIM,
    fontFace: "Calibri",
  });
  slide.addText(`Generated ${new Date().toLocaleString()}`, {
    x: 0.6,
    y: SLIDE_H - 0.7,
    w: SLIDE_W - 1.2,
    h: 0.4,
    fontSize: 10,
    color: INK_DIM,
    fontFace: "Calibri",
  });
}

// ── Public ────────────────────────────────────────────────────────────────

/**
 * Export the live Stage-6 dashboard to a PowerPoint deck.
 *
 * @param {Object} args
 * @param {HTMLElement} args.dashboardEl - root DOM node holding the dashboard
 *   (the element with class `cacm-dashboard`, or any ancestor of it).
 * @param {string} [args.kpiName] - title shown on the cover.
 * @param {string|number} [args.runId] - run id for filename + cover.
 * @param {string} [args.kpiType] - just for filename slug.
 */
export async function exportDashboardToPpt({ dashboardEl, kpiName, runId, kpiType }) {
  if (!dashboardEl) {
    throw new Error("Dashboard not yet rendered — open the Dashboard stage first.");
  }
  const dashboardRoot =
    dashboardEl.classList && dashboardEl.classList.contains("cacm-dashboard")
      ? dashboardEl
      : dashboardEl.querySelector(".cacm-dashboard") || dashboardEl;

  const pptx = new PptxGenJS();
  pptx.layout = "LAYOUT_WIDE";
  pptx.title = `${kpiName || "Dashboard"} — Run ${runId}`;
  pptx.subject = "Prism CACM dashboard export";
  pptx.company = "Uniqus Labs";

  addCoverSlide(pptx, {
    title: kpiName || "Prism Dashboard",
    subtitle: kpiType || "",
    runId,
  });

  // 1. KPI tile row — one summary slide.
  const kpiRow = dashboardRoot.querySelector(".cacm-dash-kpi-row");
  if (kpiRow) {
    try {
      const png = await captureNode(kpiRow);
      await addImageSlide(pptx, {
        title: "Summary KPIs",
        subtitle: "Aggregated risk and exposure metrics",
        dataUrl: png,
      });
    } catch (e) {
      // Skip silently if a node fails — the rest of the deck still renders.
      // Errors usually mean a font or image inside failed CORS — we don't
      // want one bad node to abort the whole export.
      // eslint-disable-next-line no-console
      console.warn("KPI capture failed:", e);
    }
  }

  // 2. Each chart card — one slide per card, in document order.
  const cards = dashboardRoot.querySelectorAll(".cacm-dash-card");
  for (const card of cards) {
    const titleEl = card.querySelector(".cacm-dash-card-title");
    const subEl = card.querySelector(".cacm-dash-card-sub");
    const title = (titleEl?.textContent || "Chart").trim();
    const subtitle = (subEl?.textContent || "").trim();
    try {
      // Capture the body only so the duplicated header doesn't appear inside
      // the slide image (we already render the title above as PPT text).
      const body = card.querySelector(".cacm-dash-card-body") || card;
      const png = await captureNode(body);
      await addImageSlide(pptx, { title, subtitle, dataUrl: png });
    } catch (e) {
      // eslint-disable-next-line no-console
      console.warn(`Capture failed for "${title}":`, e);
    }
  }

  const safeName = (kpiName || kpiType || "dashboard")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_|_$/g, "");
  const fileName = `${safeName || "dashboard"}_run_${runId}.pptx`;
  await pptx.writeFile({ fileName });
}
