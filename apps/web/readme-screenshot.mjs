import { chromium } from "playwright";

const browser = await chromium.launch({
  headless: true,
  args: ["--single-process", "--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
});
const context = await browser.newContext({
  viewport: { width: 1600, height: 1000 },
  deviceScaleFactor: 2,
});
const page = await context.newPage();

const BASE = "http://127.0.0.1:13000";
const shots = [];

async function snapshot(name, url, opts = {}) {
  const { waitMs = 3000, selector = null, fullPage = false } = opts;
  console.log(`→ ${name}: ${url}`);
  try {
    await page.goto(url, { waitUntil: "networkidle", timeout: 30000 });
  } catch (e) {
    console.log(`  goto timeout, continuing...`);
  }
  await page.waitForTimeout(waitMs);
  if (selector) {
    try {
      await page.waitForSelector(selector, { timeout: 10000 });
      await page.waitForTimeout(500);
    } catch (e) {
      console.log(`  selector ${selector} not found`);
    }
  }
  const path = `images/readme/${name}.png`;
  await page.screenshot({ path, fullPage, type: "png" });
  console.log(`  saved ${path}`);
  shots.push(name);
}

// 1. 首页（已有 home-hero.png，但可能需要更新）
await snapshot("home-hero", `${BASE}/`, { waitMs: 2000 });

// 2. 数据分析工作区 — 看看里面有什么
const wsId = "45f75da8f4a5";
const sessionId = "2269e7c462a66d7a";
await snapshot("demo-workspace-overview", `${BASE}/workspace?session_id=${sessionId}&workspace_id=${wsId}`, {
  waitMs: 4000,
});

// 3. 工业监控工作区
const indWs = "1801c4eedabf";
const indSs = "3a38ff9e780d233a";
await snapshot("demo-industrial-monitor", `${BASE}/workspace?session_id=${indSs}&workspace_id=${indWs}`, {
  waitMs: 4000,
});

// 4. 知识图谱 overlay
await snapshot("demo-knowledge-graph-new", `${BASE}/workspace?workspace_id=${wsId}&overlay=knowledge_graph`, {
  waitMs: 4000,
});

// 5. 知识库 overlay
await snapshot("demo-knowledge-base-new", `${BASE}/workspace?workspace_id=${wsId}&overlay=knowledge_base`, {
  waitMs: 4000,
});

// 6. 资源管理
await snapshot("demo-resource-management", `${BASE}/workspace?workspace_id=${wsId}&overlay=resources`, {
  waitMs: 3000,
});

console.log("\n=== Screenshots taken ===");
for (const s of shots) console.log(`  ${s}`);

await context.close();
await browser.close();
