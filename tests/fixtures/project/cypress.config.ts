import { defineConfig } from "cypress";

export default defineConfig({
  projectId: "b94pqi",
  video: true,
  viewportWidth: 1024,
  viewportHeight: 900,
  taskTimeout: 2000,
  chromeWebSecurity: false,
  retries: 1,
  e2e: {
    baseUrl: "http://localhost:4200",
    specPattern: 'cypress/e2e/**/*.spec.ts'
  }
});
