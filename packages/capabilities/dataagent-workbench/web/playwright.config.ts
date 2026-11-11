import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',timeout:15000,use:{baseURL:process.env.DATAAGENT_TEST_URL || 'http://127.0.0.1:8765',headless:true,channel:"chrome",extraHTTPHeaders:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN || ''}},reporter:'line'});
