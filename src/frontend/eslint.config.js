// ESLint configuration of every package under packages/ (flat config).
//
// ESLint looks it up from the directory of each file it lints, so the
// `eslint .` of any package uses it. Only TypeScript is linted: the rule sets
// below apply to .ts and .tsx files alone, and the build output is ignored.
// No rule here needs type information, so the parser reads no tsconfig.
// Prettier and stylelint are configured next to it (.prettierrc.json,
// .stylelintrc.json), and the three tools are declared in package.json here.
const js = require('@eslint/js');
const tsPlugin = require('@typescript-eslint/eslint-plugin');
const tsParser = require('@typescript-eslint/parser');
const prettierRecommended = require('eslint-plugin-prettier/recommended');

const typescript = ['**/*.ts', '**/*.tsx'];

// The parser and the plugin, eslint-recommended (core rules that TypeScript
// makes redundant, off) and recommended: the plugin's eslintrc configurations,
// since version 6 has no flat ones.
const tsRecommended = [
  {
    files: typescript,
    languageOptions: { parser: tsParser, sourceType: 'module' },
    plugins: { '@typescript-eslint': tsPlugin },
    rules: {
      ...tsPlugin.configs['eslint-recommended'].overrides[0].rules,
      ...tsPlugin.configs.recommended.rules
    }
  }
];

module.exports = [
  {
    ignores: [
      '**/lib/',
      '**/dist/',
      '**/coverage/',
      '**/*.d.ts',
      'packages/labextension/noworkflow_labextension/'
    ]
  },
  { files: typescript, ...js.configs.recommended },
  ...tsRecommended,
  { files: typescript, ...prettierRecommended },
  {
    files: typescript,
    rules: {
      '@typescript-eslint/naming-convention': [
        'error',
        {
          selector: 'interface',
          format: ['PascalCase'],
          custom: {
            regex: '^I[A-Z]',
            match: true
          }
        }
      ],
      '@typescript-eslint/no-unused-vars': ['warn', { args: 'none' }],
      '@typescript-eslint/no-explicit-any': 'off',
      '@typescript-eslint/no-namespace': 'off',
      '@typescript-eslint/no-use-before-define': 'off',
      '@typescript-eslint/quotes': [
        'error',
        'single',
        { avoidEscape: true, allowTemplateLiterals: false }
      ],
      curly: ['error', 'all'],
      eqeqeq: 'error',
      'prefer-arrow-callback': 'error'
    }
  }
];
