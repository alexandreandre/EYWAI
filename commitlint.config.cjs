/** @type {import('@commitlint/types').UserConfig} */
module.exports = {
  extends: ['@commitlint/config-conventional'],
  rules: {
    'type-enum': [
      2,
      'always',
      [
        'feat',
        'fix',
        'chore',
        'docs',
        'refactor',
        'perf',
        'test',
        'build',
        'ci',
        'revert',
      ],
    ],
    // Scope obligatoire seulement quand présent : liste des valeurs autorisées
    'scope-enum': [
      2,
      'always',
      ['payroll', 'auth', 'frontend', 'infra', 'api', 'ci', 'scripts'],
    ],
  },
};
