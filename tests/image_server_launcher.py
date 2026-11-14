"""测试用启动脚本：把 `api._adapter` 换成会返回图片的假适配器，再启动真正的 MCP 服务（stdio）。

只给 tests/test_mcp_images.py 用。`error` 模式下假适配器的 `read` 抛异常。
用法：python tests/image_server_launcher.py [--error] --root <仓库根目录>
"""

import sys

from refcov import api
from refcov.adapters import markdown
from refcov.sources import Image
from refcov_mcp.server import main

PNG = Image(b"\x89PNG\r\n\x1a\nfake-png-bytes\x00\xff", "image/png")
JPG = Image(b"\xff\xd8\xfffake-jpeg-bytes\x00", "image/jpeg")
ERROR = "--error" in sys.argv


class Adapter:
    name = markdown.name
    kinds = markdown.kinds
    split = staticmethod(markdown.split)
    facts = staticmethod(markdown.facts)

    def read(self, data, name, unit_id):
        if ERROR:
            raise RuntimeError("视频变了")
        return [f"镜头 {unit_id}", PNG, JPG]


api._adapter = lambda name: Adapter()

if __name__ == "__main__":
    raise SystemExit(main([a for a in sys.argv[1:] if a != "--error"]))
