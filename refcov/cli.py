"""命令行 `refcov`。子命令在后面的任务里加（add：任务 4，report：任务 7，check：任务 10、11）。"""

import argparse

from refcov import __version__


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="refcov", description="Coverage for reference material.")
    parser.add_argument("--version", action="version", version=f"refcov {__version__}")
    parser.parse_args(argv)
    parser.print_help()
    return 0
