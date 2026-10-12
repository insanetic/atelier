// core/parse.ts
var ENTRY_ID = /\b([A-Z][A-Z0-9]*)-(\d{3})\b/g;
var HEADING = /^### ([A-Z][A-Z0-9]*)-(\d{3}) \[(MUST|SHOULD|RETIRED)\] (\S.*)$/;
var ENTRY_LIKE = /^### [A-Z][A-Z0-9]*-\d+\b/;
var unquote = (value) => value.trim().replace(/^(['"])(.*)\1$/, "$2");
function parseFrontmatter(text) {
  const lines = text.split("\n");
  if (lines[0]?.trim() !== "---") return { paths: void 0, otherKeys: [], isUnclosed: false, lines: 0 };
  const end = lines.findIndex((line, index) => index > 0 && line.trim() === "---");
  if (end === -1) return { paths: void 0, otherKeys: [], isUnclosed: true, lines: 0 };
  let paths;
  const otherKeys = [];
  let isInPaths = false;
  for (const line of lines.slice(1, end)) {
    const key = /^([A-Za-z_][\w-]*):(.*)$/.exec(line);
    if (key !== null) {
      isInPaths = key[1] === "paths";
      if (!isInPaths) otherKeys.push(key[1] ?? "");
      else {
        const inline = (key[2] ?? "").trim().replace(/^\[(.*)\]$/, "$1");
        paths = inline === "" ? [] : inline.split(",").map(unquote).filter((glob) => glob !== "");
      }
    } else if (isInPaths) {
      const item = /^\s*-\s+(.+)$/.exec(line);
      if (item !== null) paths?.push(unquote(item[1] ?? ""));
    }
  }
  return { paths, otherKeys, isUnclosed: false, lines: end + 1 };
}
function parseCheckedBy(value) {
  return value.replace(/\([^)]*\)/g, "").split(";").map((part) => part.trim()).filter((part) => part !== "").map((part) => ({
    kind: (part.split(/\s/, 1)[0] ?? "").replace(/^`|[`:,.]+$/g, ""),
    names: [...part.matchAll(/`([^`]+)`/g)].map((match) => match[1] ?? "")
  }));
}
var isReview = (check2) => check2.kind === "review";
function parseRulesFile(file) {
  const entries = [];
  const malformed = [];
  let isFenced = false;
  let open;
  const close = () => {
    if (open === void 0) return;
    const body = open.body.join("\n").replace(/\s+$/, "");
    const checkedBy = /^- Checked by: ((?:.|\n {2,}\S)*)/m.exec(body)?.[1]?.replace(/\n\s+/g, " ");
    entries.push({ ...open, file: file.path, body, checks: checkedBy === void 0 ? [] : parseCheckedBy(checkedBy) });
    open = void 0;
  };
  file.text.split("\n").forEach((line, index) => {
    if (line.trimStart().startsWith("```")) isFenced = !isFenced;
    if (isFenced) {
      open?.body.push(line);
      return;
    }
    if (!line.startsWith("#")) {
      open?.body.push(line);
      return;
    }
    close();
    const heading = HEADING.exec(line);
    if (heading !== null) {
      const prefix = heading[1] ?? "";
      open = { id: `${prefix}-${heading[2] ?? ""}`, prefix, level: heading[3], title: heading[4] ?? "", line: index + 1, body: [] };
    } else if (ENTRY_LIKE.test(line)) malformed.push({ line: index + 1, text: line });
  });
  close();
  return { path: file.path, frontmatter: parseFrontmatter(file.text), entries, malformed };
}
function entryText(entry) {
  const heading = `### ${entry.id} [${entry.level}] ${entry.title}`;
  return entry.body.trim() === "" ? heading : `${heading}
${entry.body.replace(/^\n+/, "\n")}`;
}

// core/check.ts
var LINE_ORDER = ["Good", "Bad", "Checked by", "Waiver", "Why"];
var LABEL = /^- (Good|Bad|Checked by|Waiver|Why):/gm;
var FILE_PATH = /^\.?[\w@+-][\w.@+-]*(?:\/[\w.@+-]+)+\.[A-Za-z]\w*$/;
function loadCatalog(files) {
  const parsed = [...files].sort((a, b) => a.path.localeCompare(b.path)).map(parseRulesFile);
  return { files: parsed, entries: parsed.flatMap((file) => file.entries) };
}
function checkFiles(catalog) {
  const paths = catalog.entries.filter((entry) => entry.level !== "RETIRED").flatMap((entry) => entry.checks.flatMap((check2) => [check2.kind, ...check2.names])).filter((name) => FILE_PATH.test(name));
  return [...new Set(paths)].sort();
}
function structure(catalog) {
  const issues = [];
  for (const file of catalog.files) {
    const { frontmatter } = file;
    if (frontmatter.isUnclosed) issues.push({ file: file.path, line: 1, message: "the frontmatter has no closing `---`, so the file loads in every session; close it" });
    if (frontmatter.otherKeys.length > 0)
      issues.push({ file: file.path, line: 1, message: `the frontmatter holds ${frontmatter.otherKeys.map((key) => `\`${key}:\``).join(", ")}; only \`paths:\` is read, remove the rest` });
    if (frontmatter.paths?.length === 0) issues.push({ file: file.path, line: 1, message: "`paths:` is empty; list the globs or remove the frontmatter" });
    for (const heading of file.malformed)
      issues.push({ file: file.path, line: heading.line, message: "an entry heading reads `### <AREA>-<nnn> [MUST|SHOULD|RETIRED] <rule>`, the number three digits" });
  }
  const first = /* @__PURE__ */ new Map();
  for (const entry of catalog.entries) {
    const earlier = first.get(entry.id);
    if (earlier === void 0) first.set(entry.id, entry);
    else issues.push({ file: entry.file, line: entry.line, id: entry.id, message: `the ID is already used at ${earlier.file}:${earlier.line}; take the next free number (\`rulebook next ${entry.prefix}\`)` });
  }
  return issues;
}
function grammar(entry, missing) {
  if (entry.level === "RETIRED") return [];
  const at = { file: entry.file, line: entry.line, id: entry.id };
  const issues = [];
  if (entry.checks.length === 0) issues.push({ ...at, message: "add a `- Checked by:` line that names the check, or `review`" });
  else if (entry.checks.every(isReview) && !/^- (?:Good|Bad):/m.test(entry.body))
    issues.push({ ...at, message: "an entry checked only by review needs a `- Good:` or a `- Bad:` line" });
  const order = [...entry.body.matchAll(LABEL)].map((match) => LINE_ORDER.indexOf(match[1] ?? ""));
  if (order.some((position, index) => index > 0 && position < (order[index - 1] ?? 0)))
    issues.push({ ...at, message: "the lines come in the order Good, Bad, Checked by, Waiver, Why" });
  if (entry.level === "SHOULD" && !/\bOutweighed\b/.test(entry.body))
    issues.push({ ...at, message: "a SHOULD says what can outweigh it, in a sentence that starts with `Outweighed`" });
  for (const name of entry.checks.flatMap((check2) => [check2.kind, ...check2.names]))
    if (missing.has(name)) issues.push({ ...at, message: `\`Checked by:\` names ${name}, which does not exist; name the check that enforces the entry, or \`review\`` });
  return issues;
}
function citations(catalog, sources) {
  const byId = new Map(catalog.entries.map((entry) => [entry.id, entry]));
  const prefixes = new Set(catalog.entries.map((entry) => entry.prefix));
  const retiredLines = new Set(catalog.entries.filter((entry) => entry.level === "RETIRED").map((entry) => `${entry.file}:${entry.line}`));
  const malformed = new Set(catalog.files.flatMap((file) => file.malformed.map((heading) => `${file.path}:${heading.line}`)));
  const issues = [];
  for (const source of sources) {
    let isFenced = false;
    source.text.split("\n").forEach((line, index) => {
      if (line.trimStart().startsWith("```")) isFenced = !isFenced;
      if (isFenced && /^\s*### /.test(line)) return;
      if (malformed.has(`${source.path}:${index + 1}`)) return;
      const isRetiredHeading = retiredLines.has(`${source.path}:${index + 1}`);
      for (const match of line.matchAll(ENTRY_ID)) {
        const id = match[0];
        if (!prefixes.has(match[1] ?? "")) continue;
        const cited = byId.get(id);
        if (cited === void 0) issues.push({ file: source.path, line: index + 1, message: `cites ${id}, which is no entry; cite an existing ID` });
        else if (cited.level === "RETIRED" && !isRetiredHeading) issues.push({ file: source.path, line: index + 1, message: `cites ${id}, which is retired (${cited.title}); cite its replacement or drop the citation` });
      }
    });
  }
  return issues;
}
function check(files, citing = [], missing = /* @__PURE__ */ new Set()) {
  const catalog = loadCatalog(files);
  const issues = [...structure(catalog), ...catalog.entries.flatMap((entry) => grammar(entry, missing)), ...citations(catalog, [...files, ...citing])];
  return issues.sort((a, b) => a.file.localeCompare(b.file) || a.line - b.line);
}
function renderIssues(issues) {
  return issues.map((issue) => `${issue.file}:${issue.line} ${issue.id === void 0 ? "" : `${issue.id}: `}${issue.message}`).join("\n");
}

// core/glob.ts
var SPECIAL = /[.+^$()|\\]/;
function globToRegExp(glob) {
  const pattern = glob.replace(/^\.\//, "");
  let out = "";
  let depth = 0;
  for (let at = 0; at < pattern.length; at++) {
    const char = pattern[at] ?? "";
    if (char === "*" && pattern[at + 1] === "*") {
      const isSegment = (at === 0 || pattern[at - 1] === "/") && pattern[at + 2] === "/";
      out += isSegment ? "(?:.*/)?" : ".*";
      at += isSegment ? 2 : 1;
    } else if (char === "*") out += "[^/]*";
    else if (char === "?") out += "[^/]";
    else if (char === "{") {
      depth++;
      out += "(?:";
    } else if (char === "}" && depth > 0) {
      depth--;
      out += ")";
    } else if (char === "," && depth > 0) out += "|";
    else if (char === "[") {
      const end = pattern.indexOf("]", at + 1);
      if (end === -1) out += "\\[";
      else {
        out += `[${pattern.slice(at + 1, end).replace(/^!/, "^").replace(/\\/g, "\\\\")}]`;
        at = end;
      }
    } else out += SPECIAL.test(char) ? `\\${char}` : char;
  }
  return new RegExp(`^${out}$`);
}
function matchesGlob(path, glob) {
  return globToRegExp(glob).test(path.replace(/^\.\//, ""));
}

// core/select.ts
function rulesFor(catalog, changed) {
  const applied = [];
  for (const file of catalog.files) {
    const { paths } = file.frontmatter;
    if (paths === void 0) applied.push({ file: file.path, because: "always" });
    else {
      const hit = paths.flatMap((glob) => changed.filter((path) => matchesGlob(path, glob)).map((path) => `${glob} matches ${path}`))[0];
      if (hit !== void 0) applied.push({ file: file.path, because: hit });
    }
  }
  const files = new Set(applied.map((item) => item.file));
  const live = catalog.entries.filter((entry) => files.has(entry.file) && entry.level !== "RETIRED");
  const review = live.filter((entry) => entry.checks.length === 0 || entry.checks.some(isReview));
  return { applied, review, machineOnly: live.length - review.length };
}
function renderSelection(selection, isIdsOnly) {
  const head = [
    `Rule files that apply (${selection.applied.length}):`,
    ...selection.applied.map((item) => `- ${item.file} (${item.because})`),
    "",
    `Entries for review (${selection.review.length}); machine-checked in full and left to the gate: ${selection.machineOnly}`
  ];
  const entries = selection.review.map(
    (entry) => isIdsOnly ? `- ${entry.id} [${entry.level}] ${entry.title} (${entry.file}:${entry.line})` : `
<!-- ${entry.file}:${entry.line} -->
${entryText(entry)}`
  );
  return [...head, ...entries].join("\n");
}
function nextId(catalog, prefix) {
  const used = catalog.entries.filter((entry) => entry.prefix === prefix).map((entry) => Number(entry.id.slice(prefix.length + 1)));
  return `${prefix}-${String(Math.max(0, ...used) + 1).padStart(3, "0")}`;
}

// core/workspace.ts
var RULES_DIR = ".claude/rules";
var SKILLS_DIR = ".claude/skills";
var CITING_FILES = ["CLAUDE.md", "AGENTS.md", ".claude/CLAUDE.md"];
async function markdownUnder(io, root, dir) {
  const found = [];
  for (const item of await io.list(`${root}/${dir}`)) {
    const path = `${dir}/${item.name}`;
    if (item.isDir) found.push(...await markdownUnder(io, root, path));
    else if (item.name.endsWith(".md")) found.push({ path, text: await io.readText(`${root}/${path}`) ?? "" });
  }
  return found.sort((a, b) => a.path.localeCompare(b.path));
}
async function openWorkspace(io, root) {
  const rules = await markdownUnder(io, root, RULES_DIR);
  const catalog = loadCatalog(rules);
  return {
    rules,
    catalog,
    async issues() {
      const citing = await markdownUnder(io, root, SKILLS_DIR);
      for (const path of CITING_FILES) {
        const text = await io.readText(`${root}/${path}`);
        if (text !== void 0) citing.push({ path, text });
      }
      const missing = /* @__PURE__ */ new Set();
      for (const path of checkFiles(catalog)) if (!await io.exists(`${root}/${path}`)) missing.add(path);
      return check(rules, citing, missing);
    }
  };
}
export {
  RULES_DIR,
  check,
  checkFiles,
  entryText,
  globToRegExp,
  isReview,
  loadCatalog,
  matchesGlob,
  nextId,
  openWorkspace,
  parseCheckedBy,
  parseFrontmatter,
  parseRulesFile,
  renderIssues,
  renderSelection,
  rulesFor
};
