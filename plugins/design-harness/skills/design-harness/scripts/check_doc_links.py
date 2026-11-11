import sys
from pathlib import Path

from discover_workspace import resolve_or_report
from workspace import local_md_targets


def check_links(docs_root):
    docs_root = Path(docs_root).resolve()
    problems = []
    for md in sorted(docs_root.rglob("*.md")):
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            for target in local_md_targets(line):
                resolved = (md.parent / target).resolve()
                # 安全检查：resolve 后的路径必须在 docs_root 内
                try:
                    resolved.relative_to(docs_root)
                except ValueError:
                    problems.append(
                        f"{md.relative_to(docs_root)}:{lineno} -> {target} "
                        f"(resolves outside workspace)")
                    continue
                if not resolved.exists():
                    problems.append(f"{md.relative_to(docs_root)}:{lineno} -> {target}")
    return problems


def main(argv):
    root = argv[1] if len(argv) > 1 else resolve_or_report(".")
    if root is None:
        return 1
    problems = check_links(root)
    for problem in problems:
        print(f"DANGLING {problem}")
    print(f"{'ok: no dangling links under ' + str(root) if not problems else f'{len(problems)} dangling link(s)'}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
