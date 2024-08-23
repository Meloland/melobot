import asyncio as aio

import pytest as pt
import pytest_asyncio as ptaio
from pytest import fixture
from pytest_asyncio import fixture as aiofixture

# Auto use "package" loop_scope (not pytest fixture scope) for all async test functions
pytestmark = pt.mark.asyncio(loop_scope="package")
