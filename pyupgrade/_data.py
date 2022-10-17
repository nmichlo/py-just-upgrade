from __future__ import annotations

import ast
import collections
import functools
import pkgutil
from dataclasses import dataclass
from typing import Callable, Optional, Set
from typing import Iterable
from typing import List
from typing import NamedTuple
from typing import Tuple
from typing import TYPE_CHECKING
from typing import TypeVar

from tokenize_rt import Offset
from tokenize_rt import Token

from pyupgrade import _plugins

if TYPE_CHECKING:
    from typing import Protocol
else:
    Protocol = object

Version = Tuple[int, ...]


class Settings(NamedTuple):
    min_version: Version = (3,)
    keep_percent_format: bool = False
    keep_mock: bool = False
    keep_runtime_typing: bool = False
    enabled_plugins: Optional[Set[str]] = None
    disabled_plugins: Optional[Set[str]] = None

    def is_plugin_enabled(self, name: str) -> bool:
        if self.enabled_plugins and self.disabled_plugins:
            raise RuntimeError
        elif self.enabled_plugins:
            return name in self.enabled_plugins
        elif self.disabled_plugins:
            return name not in self.disabled_plugins
        else:
            return True

    def get_plugin_functions(self, plugins: dict):
        # collect invalid plugins
        invalid = set()
        if self.enabled_plugins:
            for k in self.enabled_plugins:
                if k not in plugins:
                    invalid.add(k)
        if self.disabled_plugins:
            for k in self.disabled_plugins:
                if k not in plugins:
                    invalid.add(k)
        # raise errors if invalid
        if invalid:
            raise KeyError(f'invalid plugins: {sorted(invalid)}, valid plugins include: {sorted(plugins)}')
        # collect all the plugins
        funcs = collections.defaultdict(list)
        for plugin_name, plugin_items in plugins.items():
            if self.is_plugin_enabled(plugin_name):
                for plugin in plugin_items:
                    funcs[plugin.tp].append(plugin.func)
        return funcs


class State(NamedTuple):
    settings: Settings
    from_imports: dict[str, set[str]]
    in_annotation: bool = False


AST_T = TypeVar('AST_T', bound=ast.AST)
TokenFunc = Callable[[int, List[Token]], None]
ASTFunc = Callable[[State, AST_T, ast.AST], Iterable[Tuple[Offset, TokenFunc]]]

RECORD_FROM_IMPORTS = frozenset((
    '__future__',
    'os.path',
    'functools',
    'mmap',
    'select',
    'six',
    'six.moves',
    'socket',
    'subprocess',
    'sys',
    'typing',
    'typing_extensions',
))

PLUGIN_FUNCS = collections.defaultdict(list)


@dataclass
class Plugin:
    func: callable
    plugin_name: str
    tp: type


def register(tp: type[AST_T]) -> Callable[[ASTFunc[AST_T]], ASTFunc[AST_T]]:
    def register_decorator(func: ASTFunc[AST_T]) -> ASTFunc[AST_T]:
        plugin = Plugin(
            func=func,
            plugin_name=func.__module__.rsplit('.', maxsplit=1)[-1],
            tp=tp,
        )
        PLUGIN_FUNCS[plugin.plugin_name].append(plugin)
        return func
    return register_decorator


class ASTCallbackMapping(Protocol):
    def __getitem__(self, tp: type[AST_T]) -> list[ASTFunc[AST_T]]: ...


def visit(
        plugins,
        tree: ast.Module,
        settings: Settings,
) -> dict[Offset, list[TokenFunc]]:
    initial_state = State(
        settings=settings,
        from_imports=collections.defaultdict(set),
    )

    # CUSTOM: collect functions based on active or inactive plugins
    funcs: ASTCallbackMapping = settings.get_plugin_functions(plugins)

    nodes: list[tuple[State, ast.AST, ast.AST]] = [(initial_state, tree, tree)]

    ret = collections.defaultdict(list)
    while nodes:
        state, node, parent = nodes.pop()

        tp = type(node)
        for ast_func in funcs[tp]:
            for offset, token_func in ast_func(state, node, parent):
                ret[offset].append(token_func)

        if (
                isinstance(node, ast.ImportFrom) and
                not node.level and
                node.module in RECORD_FROM_IMPORTS
        ):
            state.from_imports[node.module].update(
                name.name for name in node.names if not name.asname
            )

        for name in reversed(node._fields):
            value = getattr(node, name)
            if name in {'annotation', 'returns'}:
                next_state = state._replace(in_annotation=True)
            else:
                next_state = state

            if isinstance(value, ast.AST):
                nodes.append((next_state, value, node))
            elif isinstance(value, list):
                for value in reversed(value):
                    if isinstance(value, ast.AST):
                        nodes.append((next_state, value, node))
    return ret


def _import_plugins() -> None:
    plugins_path = _plugins.__path__
    mod_infos = pkgutil.walk_packages(plugins_path, f'{_plugins.__name__}.')
    for _, name, _ in mod_infos:
        __import__(name, fromlist=['_trash'])


_import_plugins()
