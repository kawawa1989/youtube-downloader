"""python -m ytmp3 のエントリポイント。"""

import sys

from ytmp3.cli import main

if __name__ == "__main__":
    sys.exit(main())
