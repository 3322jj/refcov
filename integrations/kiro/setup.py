"""把 RefCov 装进用户的仓库：和 `refcov init` 做同样的事（设计 2.1、4.5）。只用标准库。

用法（在用户仓库的根目录运行；RefCov 要先装好，用同一个解释器）：
    python <RefCov 目录>/integrations/kiro/setup.py [--force]
只补装，不覆盖；--force 的范围和 refcov init 一样。写出的钩子用安装好的包，不指向这个克隆目录。
"""

import argparse
import sys
from pathlib import Path

CLONE = Path(__file__).resolve().parents[2]
if str(CLONE) not in sys.path:  # 为了导入 integrations 包；钩子的探测在子进程里做，不受这一行影响
    sys.path.insert(0, str(CLONE))


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # 输出中文
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="把 RefCov 装进当前仓库（在仓库根目录运行）。")
    parser.add_argument("--force", action="store_true", help="同 refcov init 的 --force")
    args = parser.parse_args(argv)
    from integrations.kiro import init as kiro_init

    code = kiro_init.run(Path.cwd(), args.force)
    print("可以改用 refcov init（装好包以后就是这个命令）。")
    return code


if __name__ == "__main__":
    sys.exit(main())
