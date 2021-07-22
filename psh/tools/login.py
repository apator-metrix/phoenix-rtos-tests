#
# Phoenix-RTOS
#
# phoenix-rtos-tests
#
# tools for login related testing
#
# Copyright 2021 Phoenix Systems
# Author: Mateusz Niewiadomski
#
# This file is part of Phoenix-RTOS.
#
# %LICENSE%
#
from collections import namedtuple

import pexpect

from psh.tools.basic import assert_prompt, assert_prompt_fail


Credentials = namedtuple('Credentials', 'user passwd')
pshlogin_cmd = '/bin/pshlogin'


def log_in(p, login, passwd):
    p.send(login + '\n')
    assert p.expect_exact([login, pexpect.TIMEOUT]) == 0, 'Cannot enter login to login prompt'
    assert p.expect_exact(["Password:", pexpect.TIMEOUT]) == 0
    p.send(passwd + '\n')


def assert_login(p, login, passwd):
    log_in(p, login, passwd)
    assert_prompt(p, 'Login should pass but failed', timeout=1)


def assert_login_fail(p, login, passwd):
    log_in(p, login, passwd)
    assert_prompt_fail(p, 'Login should fail but passed', timeout=1)


def assert_login_empty(p, login):
    p.send(login + '\n')
    assert p.expect_exact(['Login:', pexpect.TIMEOUT]) == 0, 'Empty login doesn`t repeat logging'
