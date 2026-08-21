"""
Import همه‌ی زیرماژول‌های handlers کافیه تا دکوریتورهای @client.on ثبت بشن.
main.py فقط کافیه `from bot import handlers` رو انجام بده.
"""
from . import general  # noqa: F401
from . import tools  # noqa: F401
from . import notes  # noqa: F401
from . import messages  # noqa: F401
from . import fun  # noqa: F401
from . import media  # noqa: F401
from . import audio  # noqa: F401
from . import font  # noqa: F401
from . import profile  # noqa: F401
from . import assistant  # noqa: F401
from . import ai  # noqa: F401
from . import command_router  # noqa: F401
from . import admin  # noqa: F401
from . import groupguard  # noqa: F401
from . import backup  # noqa: F401
from . import autopost  # noqa: F401
from . import stats  # noqa: F401
from . import scheduler  # noqa: F401
from . import help  # noqa: F401
from . import panel  # noqa: F401
