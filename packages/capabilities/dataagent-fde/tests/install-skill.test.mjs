import assert from 'node:assert/strict';
import { execFile } from 'node:child_process';
import { lstat, mkdir, mkdtemp, readFile, realpath, rm, symlink, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { fileURLToPath } from 'node:url';
import { promisify } from 'node:util';

const run = promisify(execFile);
const cli = fileURLToPath(new URL('../bin/dataagent-skill.mjs', import.meta.url));
const skill = fileURLToPath(new URL('../skills/fde-engineer/', import.meta.url));

async function project(t) {
  const cwd = await mkdtemp(join(tmpdir(), 'dataagent skill '));
  t.after(() => rm(cwd, { recursive: true, force: true }));
  return cwd;
}

function install(cwd, host) {
  return run(process.execPath, [cli, host, '--project'], { cwd });
}

for (const [host, folder] of [['codex', '.agents'], ['claude', '.claude'], ['zcode', '.agents'], ['dsh', '.agents']]) {
  test(host + ' registers the complete skill and concurrent retries are harmless', async (t) => {
    const cwd = await project(t);
    await Promise.all([install(cwd, host), install(cwd, host)]);
    const entry = join(cwd, folder, 'skills', 'fde-engineer');
    assert.equal(await realpath(entry), await realpath(skill));
    for (const name of [
      'SKILL.md', 'references/field-delivery.md', 'scripts/sample_check.py',
      'references/policy-extraction.md', 'scripts/policy_source.py',
    ]) {
      assert.deepEqual(await readFile(join(entry, name)), await readFile(join(skill, name)));
    }
  });
}

test('zcode prints the desktop skill picker and terminal command separately', async (t) => {
  const cwd = await project(t);
  const { stdout } = await install(cwd, 'zcode');
  assert.match(stdout, /桌面版[^\n]*\/fde-engineer[^\n]*SKILLS[^\n]*\$fde-engineer/);
  assert.match(stdout, /终端[^\n]*\/skill fde-engineer/);
});

test('zcode and dsh share one project entry and dsh prints its own invocation', async (t) => {
  const cwd = await project(t);
  await install(cwd, 'zcode');
  const entry = join(cwd, '.agents/skills/fde-engineer');
  const before = await lstat(entry);
  const { stdout: dsh } = await install(cwd, 'dsh');
  assert.match(dsh, /\/fde-engineer/);
  assert.equal((await lstat(entry)).ino, before.ino);
});

test('dsh selects the nearest Git root even from a nested worktree directory', async (t) => {
  const cwd = await project(t);
  await writeFile(join(cwd, '.git'), 'gitdir: ../worktree-metadata');
  const nested = join(cwd, 'a', 'b');
  await mkdir(nested, { recursive: true });
  await install(nested, 'dsh');
  assert.equal(await realpath(join(cwd, '.agents/skills/fde-engineer')), await realpath(skill));
});

test('dsh personal install follows its shared skills home override', async (t) => {
  const cwd = await project(t);
  const sharedHome = join(cwd, 'shared agents');
  await run(process.execPath, [cli, 'dsh'], { cwd, env: { ...process.env, DSH_AGENTS_HOME: sharedHome } });
  assert.equal(await realpath(join(sharedHome, 'skills/fde-engineer')), await realpath(skill));
});

test('an existing ZIP installation is preserved', async (t) => {
  const cwd = await project(t);
  const entry = join(cwd, '.agents/skills/fde-engineer');
  await mkdir(entry, { recursive: true });
  await writeFile(join(entry, 'SKILL.md'), 'custom instructions');
  await assert.rejects(install(cwd, 'codex'), (error) => error.code === 1 && error.stderr.includes(entry));
  assert.equal(await readFile(join(entry, 'SKILL.md'), 'utf8'), 'custom instructions');
});

test('a pre-existing dangling link is preserved', async (t) => {
  const cwd = await project(t);
  const directory = join(cwd, '.claude/skills');
  const entry = join(directory, 'fde-engineer');
  await mkdir(directory, { recursive: true });
  await symlink(join(cwd, 'missing'), entry, process.platform === 'win32' ? 'junction' : 'dir');
  await assert.rejects(install(cwd, 'claude'), (error) => error.code === 1 && error.stderr.includes(entry));
  assert.ok((await lstat(entry)).isSymbolicLink());
});
