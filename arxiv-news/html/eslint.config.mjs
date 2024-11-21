import globals from "globals";
import pluginJs from "@eslint/js";
import htmlPlugin from "eslint-plugin-html";

/** @type {import('eslint').Linter.Config[]} */
export default [
  {
    files: ["**/*.{js,html}"],
    languageOptions: { globals: globals.browser },
    plugins: {
      html: htmlPlugin,
    },
  },
  pluginJs.configs.recommended,
];
