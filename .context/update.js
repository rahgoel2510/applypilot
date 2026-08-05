#!/usr/bin/env node
/**
 * .context/update.js — Auto-refresh contextGraph.db
 *
 * Scans the project and updates the contextGraph.db file with:
 * - New/removed files in fileMap
 * - Updated lastUpdated timestamp
 * - Dependency changes from pyproject.toml, requirements.txt, package.json
 *
 * Usage:
 *   node .context/update.js              # Full refresh
 *   node .context/update.js --check      # Dry-run — report what changed
 *   node .context/update.js --watch      # Watch mode — auto-update on file changes
 *
 * Designed to run as a git pre-commit hook or manually after changes.
 */

const fs = require("fs");
const path = require("path");
const { execSync } = require("child_process");

// ─── Configuration ──────────────────────────────────────────────────────────

const PROJECT_ROOT = path.resolve(__dirname, "..");
const CONTEXT_FILE = path.join(__dirname, "contextGraph.db");

/** Directories to skip when scanning */
const IGNORE_DIRS = new Set([
  "node_modules",
  ".git",
  "__pycache__",
  ".pytest_cache",
  "dist",
  "build",
  ".venv",
  "venv",
  "env",
  ".context",
  "screenshots",
  "tmp",
  "linkedin_job_agent.egg-info",
  ".coverage",
  "data",
]);

/** File extensions to include in fileMap */
const SOURCE_EXTENSIONS = new Set([
  ".py",
  ".js",
  ".jsx",
  ".ts",
  ".tsx",
  ".yaml",
  ".yml",
  ".toml",
  ".json",
  ".sh",
  ".ps1",
  ".bat",
  ".md",
  ".html",
  ".css",
  ".sql",
  ".txt",
  ".dockerfile",
]);

/** Files to always skip */
const IGNORE_FILES = new Set([
  ".DS_Store",
  "package-lock.json",
  ".coverage",
  ".env",
]);

// ─── Helpers ────────────────────────────────────────────────────────────────

function loadContextGraph() {
  if (!fs.existsSync(CONTEXT_FILE)) {
    console.error("❌ contextGraph.db not found. Run the initial scan first.");
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(CONTEXT_FILE, "utf8"));
}

function saveContextGraph(graph) {
  fs.writeFileSync(CONTEXT_FILE, JSON.stringify(graph, null, 2) + "\n");
}

function getRelativePath(absPath) {
  return path.relative(PROJECT_ROOT, absPath).replace(/\\/g, "/");
}

function shouldIncludeFile(filePath) {
  const basename = path.basename(filePath);
  if (IGNORE_FILES.has(basename)) return false;
  const ext = path.extname(filePath).toLowerCase();
  return SOURCE_EXTENSIONS.has(ext);
}

function shouldIncludeDir(dirName) {
  return !IGNORE_DIRS.has(dirName) && !dirName.startsWith(".");
}

// ─── Scanners ───────────────────────────────────────────────────────────────

/**
 * Recursively scan the project for source files.
 * Returns a Set of relative paths.
 */
function scanSourceFiles(dir = PROJECT_ROOT, results = new Set()) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });

  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (shouldIncludeDir(entry.name)) {
        scanSourceFiles(path.join(dir, entry.name), results);
      }
    } else if (entry.isFile()) {
      const fullPath = path.join(dir, entry.name);
      if (shouldIncludeFile(fullPath)) {
        results.add(getRelativePath(fullPath));
      }
    }
  }

  return results;
}

/**
 * Parse Python dependencies from pyproject.toml (basic parser).
 */
function parsePythonDeps() {
  const tomlPath = path.join(PROJECT_ROOT, "pyproject.toml");
  if (!fs.existsSync(tomlPath)) return null;

  const content = fs.readFileSync(tomlPath, "utf8");
  const deps = [];
  let inDeps = false;

  for (const line of content.split("\n")) {
    if (line.match(/^dependencies\s*=/)) {
      inDeps = true;
      continue;
    }
    if (inDeps) {
      if (line.trim() === "]") {
        inDeps = false;
        continue;
      }
      const match = line.match(/"([^"]+)"/);
      if (match) deps.push(match[1]);
    }
  }

  return deps;
}

/**
 * Parse frontend dependencies from package.json.
 */
function parseFrontendDeps() {
  const pkgPath = path.join(PROJECT_ROOT, "tracker", "frontend", "package.json");
  if (!fs.existsSync(pkgPath)) return null;

  const pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  return {
    dependencies: pkg.dependencies || {},
    devDependencies: pkg.devDependencies || {},
  };
}

/**
 * Infer role from file path.
 */
function inferRole(filePath) {
  if (filePath.includes("test")) return "Test";
  if (filePath.includes("config") || filePath.endsWith(".yaml") || filePath.endsWith(".toml")) return "Configuration";
  if (filePath.includes("/pages/")) return "Frontend page";
  if (filePath.includes("/components/")) return "Frontend component";
  if (filePath.includes("/hooks/")) return "Frontend hook";
  if (filePath.includes("/layout/")) return "Frontend layout";
  if (filePath.includes("routes")) return "API routes";
  if (filePath.includes("resilience/")) return "Resilience pattern";
  if (filePath.includes("graph/")) return "Graph module";
  if (filePath.endsWith(".sh") || filePath.endsWith(".ps1") || filePath.endsWith(".bat")) return "Script";
  if (filePath.endsWith(".md")) return "Documentation";
  if (filePath.endsWith(".py")) return "Python module";
  if (filePath.endsWith(".jsx") || filePath.endsWith(".js")) return "Frontend module";
  return "Source file";
}

// ─── Update Logic ───────────────────────────────────────────────────────────

function updateFileMap(graph, currentFiles) {
  const existingFiles = new Set(Object.keys(graph.fileMap));
  const added = [];
  const removed = [];

  // Find new files
  for (const file of currentFiles) {
    if (!existingFiles.has(file)) {
      added.push(file);
      graph.fileMap[file] = {
        role: inferRole(file),
        description: "NEEDS_VERIFICATION — auto-detected, review description.",
      };
    }
  }

  // Find removed files
  for (const file of existingFiles) {
    if (!currentFiles.has(file)) {
      removed.push(file);
      delete graph.fileMap[file];
    }
  }

  return { added, removed };
}

function updateDependencies(graph) {
  const changes = [];

  // Check Python deps
  const pyDeps = parsePythonDeps();
  if (pyDeps) {
    const currentPyCore = Object.keys(graph.techStack.dependencies.python_core || {});
    for (const dep of pyDeps) {
      const depName = dep.split(/[>=<]/)[0].trim();
      if (!currentPyCore.some((k) => dep.toLowerCase().includes(k.toLowerCase()))) {
        changes.push(`New Python dep detected: ${dep}`);
      }
    }
  }

  // Check frontend deps
  const feDeps = parseFrontendDeps();
  if (feDeps) {
    const currentFe = Object.keys(graph.techStack.dependencies.frontend || {});
    for (const [dep, ver] of Object.entries(feDeps.dependencies)) {
      if (!currentFe.includes(dep)) {
        changes.push(`New frontend dep: ${dep}@${ver}`);
      }
    }
  }

  return changes;
}

// ─── Main Commands ──────────────────────────────────────────────────────────

function runUpdate(options = {}) {
  const { dryRun = false } = options;
  const graph = loadContextGraph();

  console.log("🔍 Scanning project...");
  const currentFiles = scanSourceFiles();

  console.log(`   Found ${currentFiles.size} source files`);

  // Update fileMap
  const { added, removed } = updateFileMap(graph, currentFiles);

  // Check dependencies
  const depChanges = updateDependencies(graph);

  // Report
  if (added.length > 0) {
    console.log(`\n📁 New files (${added.length}):`);
    added.forEach((f) => console.log(`   + ${f}`));
  }

  if (removed.length > 0) {
    console.log(`\n🗑️  Removed files (${removed.length}):`);
    removed.forEach((f) => console.log(`   - ${f}`));
  }

  if (depChanges.length > 0) {
    console.log(`\n📦 Dependency changes:`);
    depChanges.forEach((c) => console.log(`   ⚡ ${c}`));
  }

  if (added.length === 0 && removed.length === 0 && depChanges.length === 0) {
    console.log("\n✅ No changes detected. contextGraph.db is up to date.");
    return;
  }

  if (dryRun) {
    console.log("\n🏁 Dry run complete. No changes written.");
    return;
  }

  // Update metadata
  graph._meta.lastUpdated = new Date().toISOString().split("T")[0];

  // Append session log
  const summary = [];
  if (added.length > 0) summary.push(`Added ${added.length} files to fileMap`);
  if (removed.length > 0) summary.push(`Removed ${removed.length} files from fileMap`);
  if (depChanges.length > 0) summary.push(`${depChanges.length} dependency changes noted`);

  graph.sessionLog.push({
    date: new Date().toISOString().split("T")[0],
    summary: `[auto-update] ${summary.join(". ")}.`,
  });

  saveContextGraph(graph);
  console.log(`\n✅ contextGraph.db updated successfully.`);
}

function runWatch() {
  console.log("👁️  Watching for file changes...");
  console.log("   Press Ctrl+C to stop.\n");

  let debounceTimer = null;

  fs.watch(PROJECT_ROOT, { recursive: true }, (eventType, filename) => {
    if (!filename) return;
    if (filename.includes("node_modules")) return;
    if (filename.includes("__pycache__")) return;
    if (filename.includes(".context")) return;
    if (filename.includes(".git")) return;

    // Debounce — wait 2s after last change
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
      console.log(`\n🔄 Change detected: ${filename}`);
      runUpdate();
    }, 2000);
  });
}

// ─── CLI Entry ──────────────────────────────────────────────────────────────

const args = process.argv.slice(2);

if (args.includes("--help") || args.includes("-h")) {
  console.log(`
.context/update.js — Auto-refresh contextGraph.db

Usage:
  node .context/update.js              Full refresh
  node .context/update.js --check      Dry-run (report changes, don't write)
  node .context/update.js --watch      Watch mode (auto-update on changes)
  node .context/update.js --help       Show this help
`);
  process.exit(0);
}

if (args.includes("--watch")) {
  runWatch();
} else if (args.includes("--check")) {
  runUpdate({ dryRun: true });
} else {
  runUpdate();
}
