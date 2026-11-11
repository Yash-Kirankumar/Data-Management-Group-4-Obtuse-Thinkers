"""Start TabPy for the Tableau Prep Script steps - reachable from THIS computer only.

    .venv/bin/python tools/run_tabpy_local.py      (leave it running; stop with Ctrl-C)

Why a launcher? TabPy without a password lets anyone who can reach it run Python code.
TabPy has no setting for the network address, so this launcher forces it to listen on
127.0.0.1 (localhost): only programs on this computer - like Tableau Prep - can connect.
Settings (port 9004, 1 GB request limit, 15 min time limit) are in tools/tabpy.conf.
It also starts TabPy inside the project folder, so the Script steps write their run log
to logs/pipeline_run_log.txt.
"""
import os
import sys
from pathlib import Path

import tornado.web

PROJECT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT)
os.environ["RETAIL_PROJECT"] = str(PROJECT)

_listen = tornado.web.Application.listen


def listen_localhost(self, port, address="", **kwargs):
    return _listen(self, port, address="127.0.0.1", **kwargs)


tornado.web.Application.listen = listen_localhost

from tabpy.tabpy import main  # noqa: E402

sys.argv = ["tabpy", "--config", str(PROJECT / "tools" / "tabpy.conf"), "--disable-auth-warning"]
main()
