from __future__ import annotations

import pytest

from pyupgrade._data import Settings
from pyupgrade._main import _fix_plugins


@pytest.mark.parametrize(
    's',
    (
        # already a reduced mode
        'open("foo", "w")',
        'open("foo", mode="w")',
        'open("foo", "rb")',
        # nonsense mode
        'open("foo", "Uw")',
        'open("foo", qux="r")',
        'open("foo", 3)',
        'open(mode="r")',
        # TODO: could maybe be rewritten to remove t?
        'open("foo", "wt")',
        # don't remove this, they meant to use `encoding=`
        'open("foo", "r", "utf-8")',
    ),
)
def test_fix_open_mode_noop(s):
    assert _fix_plugins(s, settings=Settings(min_version=(3,))) == s


@pytest.mark.parametrize(
    ('s', 'expected'),
    (
        ('open("foo")', 'open("foo")'),
        ('open("foo", "U")', 'open("foo", "r")'),
        ('open("foo", mode=\'U\')', 'open("foo", mode=\'r\')'),
        ('open("foo", "Ur")', 'open("foo", "r")'),
        ('open("foo", mode="Ur")', 'open("foo", mode="r")'),
        ('open("foo", "Ub")', 'open("foo", "rb")'),
        ('open("foo", mode="Ub")', 'open("foo", mode="rb")'),
        ('open("foo", "rUb")', 'open("foo", "rb")'),
        ('open("foo", mode="rUb")', 'open("foo", mode="rb")'),
        ('open("foo", "r")', 'open("foo", "r")'),
        ('open("foo", mode="r")', 'open("foo", mode="r")'),
        ('open("foo", "rt")', 'open("foo", "r")'),
        ('open("foo", mode="rt")', 'open("foo", mode="r")'),
        ('open("f", "r", encoding="UTF-8")', 'open("f", "r", encoding="UTF-8")'),
        (
            'open("f", mode="r", encoding="UTF-8")',
            'open("f", mode="r", encoding="UTF-8")',
        ),
        (
            'open(file="f", mode="rU", encoding="UTF-8")',
            'open(file="f", mode="r", encoding="UTF-8")',
        ),
        (
            'open("f", encoding="UTF-8", mode="rt")',
            'open("f", encoding="UTF-8", mode="r")',
        ),
        (
            'open(file="f", encoding="UTF-8", mode="tr")',
            'open(file="f", encoding="UTF-8", mode="r")',
        ),
        (
            'open(mode="Ur", encoding="UTF-8", file="t.py")',
            'open(mode="r", encoding="UTF-8", file="t.py")',
        ),
        pytest.param('open(f, u"r")', 'open(f, u"r")', id='string with u flag'),
        pytest.param(
            'io.open("foo", "r")',
            'open("foo", "r")',
            id='io.open also rewrites modes in a single pass',
        ),
    ),
)
def test_fix_open_mode(s, expected):
    ret = _fix_plugins(s, settings=Settings(min_version=(3,)))
    assert ret == expected
