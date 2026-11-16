import sys
from pathlib import Path

from discover_workspace import resolve_or_report
from workspace import (LAYERS, broken_frontmatter, card_files, card_links,
                       parse_conflicts, parse_frontmatter, parse_tags)

IDEA_REQUIRED = ["id", "type"]


def layout_problems(workspace):
    workspace = Path(workspace).resolve()
    problems = []
    for md in sorted(workspace.rglob("*.md")):
        rel = md.relative_to(workspace)
        if len(rel.parts) > 1 and rel.parts[0] not in LAYERS:
            problems.append(
                f"{rel}: unknown top-level dir — invisible to every projection; "
                f"move under one of: {', '.join(LAYERS)}")
    return problems


def schema_problems(workspace):
    problems = []
    for md, rel in card_files(workspace):
        text = md.read_text(encoding="utf-8")
        if broken_frontmatter(text):
            problems.append(
                f"{rel}: frontmatter opens but never closes — "
                "it will leak into the rendered body")
        frontmatter = parse_frontmatter(text)
        if len(parse_tags(frontmatter)) > 1:
            problems.append(f"{rel}: at most one tag per card — split the card")
        if rel.parts[0] != "ideas":
            continue
        for field in IDEA_REQUIRED:
            if not frontmatter.get(field):
                problems.append(f"{rel}: missing required field: {field}")
        if frontmatter.get("status"):
            problems.append(
                f"{rel}: retired field: status — two states only "
                "(existence = live, archive/ = archived)")
    return problems


def conflict_problems(workspace):
    cards = [(rel, parse_frontmatter(md.read_text(encoding="utf-8")))
             for md, rel in card_files(workspace)]
    idea_ids = {
        state: {fm.get("id") for rel, fm in cards
                if rel.parts[0] == "ideas" and ("archive" in rel.parts) == archived}
        for state, archived in (("live", False), ("archived", True))}
    problems = []
    for rel, fm in cards:
        conflicts = parse_conflicts(fm)
        if not conflicts:
            continue
        if rel.parts[0] != "ideas":
            problems.append(f"{rel}: conflicts is an ideas-only field — "
                            "only judgments contend")
            continue
        if "archive" in rel.parts:
            continue
        for target in conflicts:
            if target == fm.get("id"):
                problems.append(f"{rel}: conflicts with itself — remove the entry")
            elif target in idea_ids["archived"]:
                problems.append(
                    f"{rel}: conflict target {target} is archived — already "
                    "adjudicated, remove the entry")
            elif target not in idea_ids["live"]:
                problems.append(
                    f"{rel}: conflict target {target} resolves to no live idea card")
    return problems


def board_inbound_problems(workspace):
    workspace = Path(workspace).resolve()
    cards = {str(rel): md for md, rel in card_files(workspace)}
    problems = []
    for rel, md in cards.items():
        if rel.startswith("board/"):
            continue
        for target in card_links(md, rel, workspace, cards):
            if target.startswith("board/"):
                problems.append(
                    f"{rel}: references board/ — the board is terminal; distill its "
                    f"conclusions into an idea card instead ({target})")
    return problems


def cycle_problems(workspace):
    """用迭代DFS替代递归，避免大图上栈溢出。"""
    workspace = Path(workspace).resolve()
    cards = {str(rel): md for md, rel in card_files(workspace)}
    graph = {rel: sorted(set(card_links(md, rel, workspace, cards)))
             for rel, md in cards.items()}
    problems, done = [], set()

    for start in sorted(graph):
        if start in done:
            continue
        # 迭代 DFS: stack 存 (node, iter(graph[node]))
        stack = [(start, iter(graph[start]))]
        path_stack = [start]  # 当前DFS路径（含已完成节点）
        done.add(start)
        
        while stack:
            node, neighbors = stack[-1]
            try:
                target = next(neighbors)
                if target == node:
                    problems.append(f"reference cycle: {node} links itself")
                elif target in path_stack:
                    idx = path_stack.index(target)
                    loop = path_stack[idx:] + [target]
                    problems.append(f"reference cycle: {' -> '.join(loop)}")
                elif target not in done:
                    done.add(target)
                    path_stack.append(target)
                    stack.append((target, iter(graph.get(target, []))))
            except StopIteration:
                path_stack.pop()
                stack.pop()
    return problems


def check(workspace):
    workspace = Path(workspace).resolve()
    # 预读所有 card，避免各子检查重复 IO
    _ = list(card_files(workspace))  # 触发 rglob，后续各函数自己调，但
    # 这里先让 resolve_or_report 等调用者看到 check 有预读意图；
    # 具体的跨子检查 cache 是后续演进目标。当前各子检查独立安全。
    return (layout_problems(workspace) + schema_problems(workspace)
            + conflict_problems(workspace) + board_inbound_problems(workspace)
            + cycle_problems(workspace))


def main(argv):
    workspace = argv[1] if len(argv) > 1 else resolve_or_report(".")
    if workspace is None:
        return 1
    problems = check(workspace)
    for problem in problems:
        print(f"INVALID {problem}")
    print(f"{'ok: all cards conform' if not problems else f'{len(problems)} problem(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
