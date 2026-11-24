#!/usr/bin/env node
import { mkdir, realpath, symlink } from 'node:fs/promises';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const usage = '用法：dataagent-skill <codex|claude> [--project]\n默认安装到个人技能目录。--project 只安装到当前项目。';
const hosts = new Map([['codex', '.agents'], ['claude', '.claude']]);

async function install(args) {
  if (args.length === 1 && ['--help', '-h'].includes(args[0])) {
    console.log(usage);
    return;
  }
  const [host, scope] = args;
  if (!hosts.has(host) || args.length > 2 || (scope !== undefined && scope !== '--project')) {
    throw new Error(usage);
  }

  const source = await realpath(fileURLToPath(new URL('../skills/fde-engineer/', import.meta.url)));
  const base = scope === '--project' ? process.cwd() : homedir();
  const directory = join(base, hosts.get(host), 'skills');
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
  const invocation = host === 'codex' ? '$fde-engineer' : '/fde-engineer';
  console.log(`Skill 已就绪：${entry}\n在新对话中输入 ${invocation} 即可使用。`);
}

install(process.argv.slice(2)).catch((error) => {
  console.error(error.message);
  process.exitCode = 1;
});
