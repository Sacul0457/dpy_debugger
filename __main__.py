from __future__ import annotations

import ast
import sys

from typing import Generator, Any
from collections.abc import Iterator
from collections import deque

def _debug_print(msg: str, colour: str) -> None:
    RESET = "\033[0m"
    colour = colour.casefold()
    colour_mapping = {
        "red": "\033[31m",
        "green": "\033[32m",
        "purple": "\033[35m",
    }
    try:
        print(f"{colour_mapping[colour]}{msg}{RESET}")
    except KeyError:
        print(msg)


class Parser:
    __slots__ = (
        'node_classes',
        'nodes'
    )

    def __init__(self) -> None:
        self.node_classes: dict[str, ast.ClassDef] | None = None
        self.nodes: ast.AST | None = None
    
    @staticmethod
    def _find_function(tree: Iterator[ast.AST] | ast.ClassDef, func_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
        if isinstance(tree, Iterator):
            for node in tree:
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == func_name:
                    return node
        else:
            for func in tree.body:
                if isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)) and func.name == func_name:
                    return func
        return None
    
    @staticmethod
    def _get_exact_surroundings(source_code_lines: list[str], to_find: str, *, surroundings_size: int, count: int = 1):
        EOF_LINE = len(source_code_lines)
        for i, line in enumerate(source_code_lines, start=1):
            if count <= 0:
                break
            if to_find in line:
                ret: str = ""
                for t_down in range(i - surroundings_size, i):
                    ret += source_code_lines[t_down]
                for t_up in range(i, min(i + surroundings_size, EOF_LINE)):
                    ret += source_code_lines[t_up]
                yield (ret, i)
                count -= 1

    def deep_search_find_func(self, lines: list[str], func_name: str, cls_node: ast.ClassDef, classes: dict[str, ast.ClassDef]) -> Generator[tuple[str, int]]:
        EOF_LINE = len(lines)

        parent_classes = deque(cls_node.bases)
        seen = set()
        while parent_classes:
            parent_cls = classes.get(getattr(parent_classes.popleft(), "id", None)) # type: ignore
            if parent_cls is None:
                continue
            if parent_cls.name in seen:
                continue
            seen.add(parent_cls.name)
            func_node = self._find_function(parent_cls, func_name)
            if parent_cls.bases:
                parent_classes.extend(parent_cls.bases) # type: ignore
            if func_node is not None:
                yield ("".join(lines[func_node.lineno - 1: func_node.end_lineno or EOF_LINE]), func_node.lineno)

    def find_code(self, source_code: str, kwargs: dict[str, Any]) -> Generator[tuple[str, int]]:
        exact, surr_size, func_name, cls_name, deep_search, cache_classes, count, cache_source = self.parse_attributes(kwargs)
        source_code_lines = source_code.splitlines(keepends=True)

        if exact:
            yield from self._get_exact_surroundings(source_code_lines, exact, surroundings_size=surr_size, count=count)
            return

        EOF_LINE = len(source_code_lines)
        if self.nodes is None:
            nodes = ast.parse(source_code)
            if cache_source:
                self.nodes = nodes
        elif cache_source:
            nodes = self.nodes

        tree = ast.walk(nodes)

        if cls_name:
            if cache_classes and self.node_classes is not None:
                node_classes = self.node_classes
            else:
                node_classes: dict[str, ast.ClassDef] = {node.name: node for node in tree if isinstance(node, ast.ClassDef)}
                if cache_classes:
                    self.node_classes = node_classes
        
        cls_node = None
        while count > 0:
            if cls_name:
                # Must be inside a class
                cls_node = node_classes.get(cls_name)
                if cls_node is None:
                    return

                if func_name is None:
                    yield "".join(source_code_lines[cls_node.lineno -1 : cls_node.end_lineno or EOF_LINE]), cls_node.lineno
                    count -= 1
                    continue
                else:
                    func_node = self._find_function(cls_node, func_name)
                    if func_node is not None:
                        count -= 1
                        yield "".join(source_code_lines[func_node.lineno - 1: func_node.end_lineno or EOF_LINE]), func_node.lineno
                        
                    if deep_search:
                        for res in self.deep_search_find_func(source_code_lines, func_name, cls_node, node_classes):
                            if count < 1:
                                return
                            yield res
                            count -= 1
            else:
                func_node = self._find_function(tree, func_name)
                if not func_node:
                    return
                count -= 1
                yield "".join(source_code_lines[func_node.lineno - 1: func_node.end_lineno or EOF_LINE]), func_node.lineno


    @staticmethod
    def parse_attributes(kwargs: dict[str, Any]) -> tuple:

        exact = kwargs.get("exact")
        surr_size = kwargs.get("surrounding_size", 6)

        if exact and surr_size:
            return exact, surr_size, None, None,  None, None, None, None

        func_name = kwargs.get("function")
        cls_name = kwargs.get("class")
        deep_search = kwargs.get("deep_search", False)
        count = kwargs.get("count", 1)
        cache_classes = kwargs.get("cache_classes", False)
        cache_source = kwargs.get("cache_source", False)

        return None, None, func_name, cls_name,  deep_search, cache_classes, count, cache_source

def print_help_command():
    _debug_print("Usage: dpy_debugger [-h | --help] [files]\n\nArgs:\n  - [-h | --help], Prints this command.\n  - [files], python files you want to check, space seperated",
                 "purple")
    _debug_print("Examples:\n  - python -m dpy_debugger -h\n  - python -m dpy_debugger main.py bot.py", "green")
    print("\nWant to contribute or found a mistake, open a PR/Issue on github: https://github.com/Sacul0457/dpy_debugger")
    

def command_parser(args: list[str] | tuple[str, ...]) -> list[str] | tuple[str, ...]:
    if any(flag in args for flag in ('-h', '--help')):
        print_help_command()
        sys.exit(0)
    return args


def run(*given_args):
    """
    This can be run through `python -m dpy_debugger file.py` or through directly running this function

    Parameters
    ----------
    *given_args:
        - `-h` or `--help`: which would print the help command.
        - `files`: Spacing separated files you want to check. (e.g `run("main.py", "bot.py")`)
    
    Raises
    -------

    """
    args: list[str] | tuple[str, ...] = given_args or sys.argv[1:]

    files = command_parser(args)
    if not files:
        _debug_print(f"Invalid command: {sys.argv[1:]!r}, use 'python -m dpy_debugger -h' for help", "red")
        sys.exit(1)
    
    for file in files:
        try:
            with open(file, encoding="utf-8", mode="r") as f:
                source_code = f.read()
            if not source_code:
                _debug_print(f"No content was found in {file!r}, skipping", "red")
                f.close()
                continue

            # this contains the reason as why something is a bad practice if not stated in tests (see below)
            basic_reasons = {
                "change_presence": "- Change presence has a low ratelimit and can easily ratelimit your bot!\n- Use the activity/status kwargs in your Client/Bot class",
                "tree.sync": "- Sycning has a low ratelimit and can easily ratelimit your bot!\n- Use a message command to sync",
                "Intents.all()": "- Most of the time, your bot only needs a few intents. Using all intents increases memory usage.\n- Enabled the intents you only need",
                "eval": "- Using eval/exec can be dangerous and perform harmful code to your system.\n- Avoid allowing executing arbitrary/user-inputted code",
                "exec": "- Using eval/exec can be dangerous and perform harmful code to your system.\n- Avoid allowing executing arbitrary/user-inputted code",
                "wait_for": "- Using 'wait_for' or 'wait_until_ready' requires a websocket connection. However, 'setup_hook' is called before a connection is made, which will therefore cause a deadlock, meaning your program will stop infinitely.",
                "process_commands": "- When using the 'on_message' event, you override how the library handles prefix commands and your prefix commands you will no longer work without 'bot.process_commands(message)'\n- Add the 'bot.process_commands(message)' in your 'on_message' event.",
                "time.sleep": "- Using 'time.sleep()' is a blocking function.\n- Use 'asyncio.sleep()' instead",
                "datetime.now()": "- Using 'datetime.now()' without setting the timezone can cause uninteded bevahiour as it will be based on your timezone.\n- Consider 'discord.utils.utcnow()' which is UTC-based.",
                "token": "- Avoid hard coding the bot token, it's recommended to store it in a separate file. (e.g .env)",
                "import requests": "-'requests' is a non-asynchronous module, hence using it in an async-environment will make it a blocking function.\n- Use 'aiohttp' instead which is asynchronous",
                "author.send": "- Sending multiple DMs to users is not only annoying but can get your bot easily ratelimited or even quarantined.- Consider using mentions instead",
                "user.send": "- Sending multiple DMs to users is not only annoying but can get your bot easily ratelimited or even quarantined.- Consider using mentions instead",
                "member.send": "- Sending multiple DMs to users is not only annoying but can get your bot easily ratelimited or even quarantined.- Consider using mentions instead",
                ".ban(": "- Instead of banning members each time in a for loop, use 'Guild.bulk_ban' which bans a many members (max 200) at at time",
                'message.author.id == ': '- If you send a message in your `on_message` event, the bot will respond to itself infinitely.\n- Add a check either using user_ids or check that the message author is not a bot',
                'message.author.bot': '- If you send a message in your `on_message` event, the bot will respond to itself infinitely.\n- Add a check either using user_ids or check that the message author is not a bot',
            }

            # 'tests_not_inside' is to check for function to ensure that certain statements are not inside
            tests_not_inside: dict[str, tuple[str, ...]] = {
                "on_ready": ("tree.sync", "change_presence"),
                "setup_hook": (
                    "tree.sync",
                    "change_presence",
                    "wait_for",
                    "wait_until_ready",
                )
            }

            tests_inside: dict[str, tuple[str, ...]] = {
                "on_message": ("process_commands", 'message.author.id ==', 'message.author.bot'),
            }
            parser = Parser()
            payload = {
                "cache_source": True,
                "cache_classes": True,
            }
            for function, function_tests in tests_not_inside.items():
                payload['function'] = function # type: ignore
                function_code = next(parser.find_code(source_code, payload), None)
                if function_code is None:
                    continue
                line_num = function_code[1] + 1
                for test in function_tests:
                    line = function_code[0].strip()
                    if line.startswith("#"):
                        continue
                    if test not in line:
                        continue
                    to_print = f"Do not use {test!r} in your {function!r} function (Line {line_num})\n{basic_reasons.get(test, '- There are no suggested changes')}\n"
                    _debug_print(f"{file}#{line_num}", "red")
                    _debug_print(to_print, "purple")
                    print("---" * 25)
                    print()

            for function, function_tests in tests_inside.items():
                parser.parse_attributes(function, instance=parser) #type: ignore
                function_code = next(parser.parse_data(), None) #type: ignore
                if function_code is None:
                    continue
                line_num = function_code[1] + 1
                for test in function_tests:
                    line = function_code[0].strip()
                    if line.startswith("#"):
                        continue
                    if test in line:
                        continue
                    to_print = f"Please add {test!r} in your {function!r} function (Line {line_num})\n{basic_reasons.get(test, '- There are no suggested changes')}\n"
                    _debug_print(f"{file}#{line_num}", "red")
                    _debug_print(to_print, "purple")
                    print("---" * 25)
                    print()

        except FileNotFoundError:
            _debug_print(f"Could not find: {file!r}, skipping", "red")
            continue
        except Exception as e:
            _debug_print(f"An error occurred: {e}, skipping {file!r}", "red")
            f.close()

    print("\nWant to contribute or found a mistake, open a PR/Issue on github: https://github.com/Sacul0457/dpy_debugger")
    sys.exit(0)

if __name__ == "__main__":
    run()
