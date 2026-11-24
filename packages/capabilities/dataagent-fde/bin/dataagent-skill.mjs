#!/usr/bin/env node
import { existsSync } from 'node:fs';
import { mkdir, realpath, symlink } from 'node:fs/promises';
import { homedir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const hosts = new Map([
  ['codex', { folder: '.agents', invocation: '$fde-engineer' }],
  ['claude', { folder: '.claude', invocation: '/fde-engineer' }],
  ['zcode', { folder: '.agents', invocation: '/skill fde-engineer' }],
  ['dsh', { folder: '.agents', invocation: '/fde-engineer' }],
]);
const usage = `用法：dataagent-skill <${[...hosts.keys()].join('|')}> [--project]\n默认安装到个人技能目录。--project 只安装到当前项目。`;

function dshProjectRoot(cwd) {
  // dsh discovers project skills only at the nearest .git marker, including worktree files.
  for (let path = cwd; ; path = dirname(path)) {
    if (existsSync(join(path, '.git'))) return path;
    if (dirname(path) === path) return cwd;
  }
}

function skillHome(host, folder, scope) {
  if (scope === '--project') {
    const cwd = process.cwd();
    return join(host === 'dsh' ? dshProjectRoot(cwd) : cwd, folder);
  }
  const override = process.env.DSH_AGENTS_HOME;
  if (host === 'dsh' && override?.trim()) {
    if (override === '~') return homedir();
    if (/^~[/\\]/.test(override)) return join(homedir(), override.slice(2));
    return resolve(override);
  }
  return join(homedir(), folder);
}

async function install(args) {
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log(usage);
    return;
  }
  const [host, scope] = args;
  const config = hosts.get(host);
  if (!config || args.length > 2 || (scope !== undefined && scope !== '--project')) {
    throw new Error(usage);
  }

  const source = await realpath(fileURLToPath(new URL('../skills/fde-engineer/', import.meta.url)));
  const directory = join(skillHome(host, config.folder, scope), 'skills');
  const entry = join(directory, 'fde-engineer');
  await mkdir(directory, { recursive: true });
  try {
    await symlink(source, entry, process.platform === 'win32' ? 'junction' : 'dir');
  } catch (error) {
    if (error.code !== 'EEXIST') throw error;
    const existing = await realpath(entry).catch((cause) => {
      if (cause.code === 'ENOENT') return null;
      throw cause;
    });
    if (existing !== source) {
      throw new Error(`同名入口已存在：${entry}。如要改用 npm 版本，请先移走原入口，再运行此命令。`);
    }
  }
  console.log(`Skill 已就绪：${entry}\n在新对话中输入 ${config.invocation} 即可使用。`);
}

install(process.argv.slice(2)).catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
