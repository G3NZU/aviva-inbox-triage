#!/usr/bin/env node
/**
 * docs-check — keeps the Markdown docs small enough to hand to an agent.
 *
 * The rules live in AGENTS.md, section "## Docs map": one line per doc (or
 * directory) ending in a cap such as `**≤ 4 KB.**` or `**≤ 2 files, ≤ 8 KB
 * each.**`, plus a `**Total ≤ N KB.**` line. This script only enforces them.
 * Requires Node ≥ 18. No dependencies.
 *
 * Checks
 *   1. every .md in the repo is listed in the map (or under a listed directory)
 *   2. every doc is under its cap; the total is under the total cap
 *   3. directory file-count caps (docs/plans/ ≤ N, docs/scratch/ ≤ 0)
 *   4. every repo path a doc mentions (<top-level dir>/...file.ext) exists;
 *      lines that say the path was deleted/removed/does not exist are skipped
 *
 * Modes
 *   --strict              CLI / pre-commit: report, exit 1 on problems
 *   --hook=session-start  Claude Code: print problems as context, exit 0
 *   --hook=post-edit      Claude Code: after Write/Edit of a .md, exit 2 + stderr
 *   --hook=stop           Claude Code: refuse the first stop while problems remain
 *
 * Pipe-test (generate the JSON with Node; `echo` mangles backslashes on Windows):
 *   node -e "process.stdout.write(JSON.stringify({tool_input:{file_path:require('path').resolve('docs/memory.md')}}))" | node scripts/docs-check.mjs --hook=post-edit
 *   node -e "process.stdout.write(JSON.stringify({stop_hook_active:false}))" | node scripts/docs-check.mjs --hook=stop
 */
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const args = process.argv.slice(2);
const hook = (args.find((a) => a.startsWith("--hook=")) ?? "").slice(7);
const SKIP_DIRS = new Set([
  "node_modules", "vendor", "dist", "build", "out", "coverage", "target",
  ".next", ".venv", "venv", "__pycache__",
]);
const skipDir = (name) => SKIP_DIRS.has(name) || name.startsWith(".");

const rel = (p) => relative(ROOT, p).replace(/\\/g, "/");
const kb = (bytes) => `${(bytes / 1024).toFixed(1)} KB`;

// ---------- 1. read the map from AGENTS.md ----------
const agentsPath = join(ROOT, "AGENTS.md");
const agents = existsSync(agentsPath) ? readFileSync(agentsPath, "utf8") : "";
const mapSection = agents.split(/^## Docs map/m)[1]?.split(/^## /m)[0] ?? "";
const entries = []; // { path, isDir, capKb, maxFiles }
for (const line of mapSection.split("\n")) {
  const m = line.match(/^- ([\w./()-]+) — /);
  if (!m) continue;
  const capKb = line.match(/≤ (\d+) KB/)?.[1];
  const maxFiles = line.match(/≤ (\d+) files?/)?.[1];
  entries.push({
    path: m[1],
    isDir: m[1].endsWith("/"),
    capKb: capKb ? Number(capKb) : null,
    maxFiles: maxFiles ? Number(maxFiles) : null,
  });
}
const totalCapKb = Number(mapSection.match(/Total ≤ (\d+) KB/)?.[1] ?? 0);

const problems = []; // { file, msg }
const add = (file, msg) => problems.push({ file, msg });

if (entries.length === 0 || !entries.some((e) => e.capKb)) {
  add("AGENTS.md", "the `## Docs map` section has no `**≤ N KB**` caps — restore the map before anything else.");
}

// ---------- 2. collect every .md ----------
function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    if (skipDir(name)) continue;
    const p = join(dir, name);
    const st = statSync(p);
    if (st.isDirectory()) walk(p, out);
    else if (/\.md$/i.test(name)) out.push(p);
  }
  return out;
}
const docs = walk(ROOT).map((p) => ({ abs: p, path: rel(p), bytes: statSync(p).size }));

const entryFor = (docPath) =>
  entries.find((e) => (e.isDir ? docPath.startsWith(e.path) : e.path === docPath));

// ---------- 3. mapping, caps, counts ----------
let total = 0;
for (const d of docs) {
  total += d.bytes;
  const e = entryFor(d.path);
  if (!e) {
    add(d.path, "not in the AGENTS.md Docs map. Add it there with a job and a cap, or delete it (git keeps history).");
    continue;
  }
  if (e.capKb && d.bytes > e.capKb * 1024) {
    const hint =
      d.path === "CHANGELOG.md"
        ? 'Fold the oldest entries under "Recent" into one-liners under "Earlier".'
        : "Tighten: merge entries on one subject, cut narrative, delete what the code now contradicts. Do not raise the cap.";
    add(d.path, `${kb(d.bytes)} is over its ${e.capKb} KB cap. ${hint}`);
  }
}
for (const e of entries.filter((x) => x.isDir && x.maxFiles !== null)) {
  const n = docs.filter((d) => d.path.startsWith(e.path)).length;
  if (n > e.maxFiles) {
    const hint = e.maxFiles === 0 ? "It must be empty." : "Delete what has shipped or been resolved.";
    add(e.path, `holds ${n} file(s), cap ${e.maxFiles}. ${hint}`);
  }
}
if (totalCapKb && total > totalCapKb * 1024) {
  add("(all docs)", `${kb(total)} in total, over the ${totalCapKb} KB total cap. Fold and tighten the largest files first.`);
}

// ---------- 4. paths that no longer exist ----------
const pathRoots = readdirSync(ROOT).filter((n) => !skipDir(n) && statSync(join(ROOT, n)).isDirectory());
const escapeRe = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
const PATH_RE = pathRoots.length
  ? new RegExp(`(?:^|[^\\w/.-])((?:${pathRoots.map(escapeRe).join("|")})\\/[^\\s\`'"<>|*{}\\[\\]]+)`, "g")
  : null;
const DELETED_LINE = /delet|removed|is gone|no longer|there is no|no `|not exist|used to|instead of/i;
function pathExists(token) {
  let t = token.replace(/[#:].*$/, "");
  for (;;) {
    if (existsSync(join(ROOT, t))) return true;
    const stripped = t.replace(/[.,;:)\]]+$/, "");
    if (stripped === t) return false;
    t = stripped;
  }
}
if (PATH_RE) {
  for (const d of docs) {
    if (d.path === "CHANGELOG.md" || d.path === "AGENT_BRIEF.md") continue; // history, and the verbatim brief (it names the private walkthrough), may name absent files
    const lines = readFileSync(d.abs, "utf8").split("\n");
    lines.forEach((line, i) => {
      if (DELETED_LINE.test(line)) return;
      for (const m of line.matchAll(PATH_RE)) {
        const token = m[1];
        const last = token.split("/").pop();
        if (!last || !last.includes(".")) continue; // directories are not checked
        if (!pathExists(token)) add(`${d.path}:${i + 1}`, `mentions \`${token}\`, which does not exist. The doc is stale here: fix or delete the claim.`);
      }
    });
  }
}

// ---------- report ----------
const summary = `docs-check: ${docs.length} docs, ${kb(total)}${totalCapKb ? ` of ${totalCapKb} KB` : ""}`;
function report() {
  const lines = [`docs-check: ${problems.length} problem(s) — rules in AGENTS.md, "Docs map" and "Curation".`];
  for (const p of problems) lines.push(`  • ${p.file} — ${p.msg}`);
  return lines.join("\n");
}
function readStdinJson() {
  try {
    const s = readFileSync(0, "utf8");
    return s.trim() ? JSON.parse(s) : {};
  } catch {
    return {};
  }
}

if (hook === "post-edit") {
  const input = readStdinJson();
  const fp = input?.tool_input?.file_path ?? input?.tool_response?.filePath ?? "";
  const edited = fp ? rel(resolve(fp)) : "";
  if (!/\.md$/i.test(edited) || edited.startsWith("..")) process.exit(0);
  const mine = problems.filter((p) => p.file.startsWith(edited) || p.file === "(all docs)");
  if (mine.length === 0) process.exit(0);
  process.stderr.write(
    `docs-check after editing ${edited}: ${mine.length} problem(s). Fix before moving on.\n` +
      mine.map((p) => `  • ${p.file} — ${p.msg}`).join("\n") + "\n"
  );
  process.exit(2);
}

if (hook === "stop") {
  const input = readStdinJson();
  if (problems.length === 0) process.exit(0);
  if (input?.stop_hook_active) {
    // Already continued once for this; do not loop. Tell the owner instead.
    process.stdout.write(JSON.stringify({ systemMessage: `docs-check: ${problems.length} doc problem(s) still open — run the docs check` }));
    process.exit(0);
  }
  process.stderr.write(
    "The docs are out of shape. Curate them before you finish (this is the standing rule, not a request):\n" +
      report() + "\nFold, tighten or delete. Do not raise a cap or edit the checker.\n"
  );
  process.exit(2);
}

if (hook === "session-start") {
  readStdinJson(); // drain the hook input so the runner never sees a broken pipe
  if (problems.length > 0) {
    process.stdout.write(report() + "\nCurate these first (fold, tighten, delete), then continue with the session's task.\n");
  }
  process.exit(0);
}

// --strict / default
if (problems.length > 0) {
  console.error(report());
  process.exit(1);
}
console.log(`${summary} — OK`);
