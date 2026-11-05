"""B02 表格 TEDS：树编辑距离相似度。

实现要点（对齐 TEDS 论文口径）：
- HTML 解析成有序树，标签名小写；属性只保留 colspan/rowspan；文本叶子归一空白；
- 代价：插入/删除 1，替换 0/1（标签或文本不同为 1）；
- TEDS = 1 - 树编辑距离 / max(节点数)。
金标来自 expected.tables[*].html；产出的表优先取 output.tables，其次 output.html。
"""
from __future__ import annotations

from html.parser import HTMLParser

from .common import missing, norm_text, result

VOID = {"br", "img", "hr", "meta", "link", "input"}
KEEP_ATTRS = ("colspan", "rowspan")


class _Builder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = {"label": "#root", "children": []}
        self.stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = {"label": tag.lower(), "children": []}
        for key, value in attrs:
            if key.lower() in KEEP_ATTRS and value:
                node["label"] += f"[{key.lower()}={value}]"
        self.stack[-1]["children"].append(node)
        if tag.lower() not in VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        if len(self.stack) > 1:
            self.stack.pop()

    def handle_data(self, data):
        text = norm_text(data)
        if text:
            self.stack[-1]["children"].append({"label": "#text:" + text, "children": []})


def parse_html(html: str) -> dict:
    builder = _Builder()
    builder.feed(html or "")
    builder.close()
    root = builder.root
    # 去掉合成根，让分母贴近 TEDS 的“表格节点数”口径
    if len(root["children"]) == 1:
        return root["children"][0]
    return root


def _postorder(root: dict):
    out = []

    def walk(node):
        for child in node["children"]:
            walk(child)
        out.append(node)

    walk(root)
    return out


def _lmd(nodes: list[dict]) -> list[int]:
    """1-based 后序编号下，每个节点的最左叶子编号。"""
    index = {id(n): i + 1 for i, n in enumerate(nodes)}
    left = [0] * (len(nodes) + 1)
    for i, node in enumerate(nodes, 1):
        if not node["children"]:
            left[i] = i
        else:
            left[i] = left[index[id(node["children"][0])]]
    return left


def tree_edit_distance(root_a: dict, root_b: dict) -> int:
    a, b = _postorder(root_a), _postorder(root_b)
    la, lb = _lmd(a), _lmd(b)
    td = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]

    keyroots_a = sorted({max(i for i in range(1, len(a) + 1) if la[i] == l) for l in set(la[1:])})
    keyroots_b = sorted({max(i for i in range(1, len(b) + 1) if lb[i] == l) for l in set(lb[1:])})

    for i in keyroots_a:
        for j in keyroots_b:
            _forest(a, b, i, j, la, lb, td)
    return td[len(a)][len(b)]


def _forest(a, b, i, j, la, lb, td):
    li, lj = la[i], lb[j]
    m, n = i - li + 1, j - lj + 1
    fd = [[0] * (n + 1) for _ in range(m + 1)]
    for x in range(1, m + 1):
        fd[x][0] = fd[x - 1][0] + 1
    for y in range(1, n + 1):
        fd[0][y] = fd[0][y - 1] + 1
    for x in range(1, m + 1):
        for y in range(1, n + 1):
            ai, bj = li + x - 1, lj + y - 1
            if la[ai] == li and lb[bj] == lj:
                cost = 0 if a[ai - 1]["label"] == b[bj - 1]["label"] else 1
                fd[x][y] = min(fd[x - 1][y] + 1, fd[x][y - 1] + 1, fd[x - 1][y - 1] + cost)
                td[ai][bj] = fd[x][y]
            else:
                fd[x][y] = min(
                    fd[x - 1][y] + 1,
                    fd[x][y - 1] + 1,
                    fd[la[ai] - li][lb[bj] - lj] + td[ai][bj],
                )


def teds(gold_html: str, pred_html: str) -> float:
    root_a, root_b = parse_html(gold_html), parse_html(pred_html)
    n_a = len(_postorder(root_a))
    n_b = len(_postorder(root_b))
    if not n_a and not n_b:
        return 1.0
    return 1.0 - tree_edit_distance(root_a, root_b) / max(n_a, n_b)


def _pred_tables(output: dict) -> list[str]:
    tables = output.get("tables")
    if isinstance(tables, list):
        return [t.get("html") if isinstance(t, dict) else str(t) for t in tables if t]
    html = output.get("html") or output.get("table_html")
    if isinstance(html, str) and html.strip():
        return [html]
    table = output.get("table")
    if isinstance(table, dict) and isinstance(table.get("html"), str):
        return [table["html"]]
    return []


def grade(case: dict, output: dict, cfg: dict) -> dict:
    gold = (case.get("expected") or {}).get("tables") or []
    gold_html = [t.get("html") for t in gold if isinstance(t, dict) and t.get("html")]
    if not gold_html:
        return missing("table_teds", "金标无表格，记入 missing")
    pred = _pred_tables(output)
    if not pred:
        return result("table_teds", 0.0, 0.0, len(gold_html), "产出无表格")
    scores = []
    for i, html in enumerate(gold_html):
        scores.append(teds(html, pred[i]) if i < len(pred) else 0.0)
    mean = sum(scores) / len(scores)
    return result("table_teds", mean, round(mean * len(scores), 6), len(scores))
