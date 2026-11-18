import {defineConfig} from '@playwright/test';
// 并发、重试与超时均可配：多张卡并行验收时机器负载高，负载下偶发超时
// 由重试兜底（flaky 不算失败，但 verify_browser.py 会列出清单）。
// 单用例超时的用例内放大系数见 tests/support.ts 的 slowTimeout。
const workers=Number(process.env.DATAAGENT_TEST_WORKERS||4);
const retries=Number(process.env.DATAAGENT_TEST_RETRIES??'1');
const timeout=Number(process.env.DATAAGENT_TEST_TIMEOUT||30000);
const expectTimeout=Number(process.env.DATAAGENT_TEST_EXPECT_TIMEOUT||10000);
export default defineConfig({testDir:'./tests',timeout,expect:{timeout:expectTimeout},
 workers,retries,
 use:{baseURL:process.env.DATAAGENT_TEST_URL || 'http://127.0.0.1:8765',headless:true,channel:"chrome",extraHTTPHeaders:{'x-dataagent-token':process.env.DATAAGENT_TEST_TOKEN || ''}},reporter:'line'});
