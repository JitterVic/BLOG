"""开发服务器入口：python -m blog。

生产环境请使用 gunicorn blog.app:app（见 deploy/deploy.sh）。
"""

import os

from .app import app
from .env_loader import env_bool, env_int

if __name__ == "__main__":
    debug = env_bool("BLOG_DEBUG", False)
    host = os.getenv("BLOG_HOST", "127.0.0.1")
    port = env_int("BLOG_PORT", 5000, minimum=1)
    app.run(host=host, port=port, debug=debug)
