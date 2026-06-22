// D4: cross-platform desktop static build (Windows cmd cannot do VAR=1 cmd inline)
const { spawnSync } = require("child_process");
const result = spawnSync("npx", ["next", "build"], {
  stdio: "inherit",
  shell: true,
  env: { ...process.env, DESKTOP_STATIC: "1" },
});
process.exit(result.status ?? 1);
