module.exports = {
  testEnvironment: 'jsdom',
  setupFilesAfterSetup: ['<rootDir>/tests/setup.js'],
  testMatch: ['**/tests/unit/**/*.test.js'],
  moduleFileExtensions: ['js', 'json'],
  collectCoverageFrom: [
    'app/static/js/**/*.js',
    '!app/static/js/pwa/**',
  ],
  coverageDirectory: 'coverage',
  verbose: true,
};