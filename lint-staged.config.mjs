/** @type {import('lint-staged').Configuration} */
export default {
  "backend/**/*.py": "sh scripts/lint-staged-ruff.sh",
  "frontend/**/*.{ts,tsx}": (filenames) => {
    const rel = filenames.map((f) => f.replace(/^frontend\//, ""));
    const args = rel.map((r) => JSON.stringify(r)).join(" ");
    return `cd frontend && npx eslint --fix ${args}`;
  },
};
