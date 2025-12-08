from __future__ import annotations

from typing import Generator, Self
import ast
import sys


class ParserV2:
    __slots__ = (
        "source_code",
        "data",
        "to_search_for",
        "cls",
        "_node_mapping",
        "exact",
    )

    def __init__(
        self,
        source_code: str,
        to_search_for: str,
        cls: str | None = None,
        exact: bool = False,
    ) -> None:
        self.to_search_for = to_search_for
        self.data = ast.parse(source_code)
        self.cls = cls
        self.source_code = source_code
        self.exact = exact
        if not self.exact:  # We only build this mapping when 'exact' is False
            self._node_mapping: dict[str, ast.ClassDef] = {
                node.name: node
                for node in ast.walk(self.data)
                if isinstance(node, ast.ClassDef)
            }

    def _reload(
        self, to_search_for: str | None, cls: str | None = None, exact: bool = False
    ):
        self.to_search_for = to_search_for
        self.cls = cls
        self.exact = exact
        if not self.exact:  # We only build this mapping when 'exact' is False
            self._node_mapping: dict[str, ast.ClassDef] = {
                node.name: node
                for node in ast.walk(self.data)
                if isinstance(node, ast.ClassDef)
            }

    def filter_parent_classes(self, text: str) -> list[str]:
        parent_classes = text[text.find("(") + 1 : text.rfind(")")]
        return [
            parent_class
            for parent_class in parent_classes.split(", ")
            if parent_class in self._node_mapping
        ]

    def get_all_parent_classes(
        self, subclasses: list[str], current_nodes: list[ast.ClassDef]
    ) -> list[ast.ClassDef]:
        """This method fetches all Parent Classes"""

        lines = self.source_code.splitlines()
        queue = subclasses.copy()

        while queue:
            subclass = queue.pop(0)
            new_parent_class = self._node_mapping.get(subclass)
            if new_parent_class is None:
                continue
            new_parent_class_text = lines[(new_parent_class.lineno or 1) - 1]
            new_parent_classes = self.filter_parent_classes(new_parent_class_text)
            current_nodes.append(new_parent_class)  # type: ignore
            queue.extend(new_parent_classes)
        return current_nodes

    def parse_data(
        self, count: int = 1, allow_parent_class: bool = True
    ) -> Generator[tuple[str, int]]:
        """
        The main method to get the content of the code.

        paremeters
        -----------
        :class:`int` count:
            How many occurrences to yield. Defaults to 1.
        allow_parent_class: :class:`bool`
            Whether to search for methods in the parent class or just the child class. Defaults to False

        Yields
        -------
        The content of the string
        """
        data = self.data
        to_seach_for = self.to_search_for
        _cls = self.cls
        lines = self.source_code.splitlines()

        already_searched: int = 0  # type: ignore

        if self.exact:
            already_searched: set[tuple[int, int | None]] = set()  # type: ignore
            new_lines = ("\n".join(lines).lstrip().rstrip()).splitlines()
            for node in ast.walk(self.data):
                if isinstance(
                    node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                ):
                    start, end = node.lineno - 1, node.end_lineno
                    for i in range(start, end):  # type: ignore
                        if to_seach_for == new_lines[i].lstrip().rstrip():
                            if not to_seach_for.startswith("class ") and isinstance( # type: ignore
                                node, ast.ClassDef
                            ):
                                for func_node in node.body:
                                    if (
                                        isinstance(
                                            func_node,
                                            (ast.AsyncFunctionDef, ast.FunctionDef),
                                        )
                                        and start <= func_node.lineno < end
                                    ):  # type: ignore
                                        func_start, func_end = (
                                            func_node.lineno - 1,
                                            func_node.end_lineno,
                                        )
                                        for i in range(func_start, func_end):
                                            if len(already_searched) == count:
                                                return
                                            elif (
                                                func_node.lineno,
                                                func_node.end_lineno,
                                            ) in already_searched:
                                                continue
                                            if to_seach_for == new_lines[i]:
                                                yield (
                                                    "\n".join(
                                                        new_lines[func_start:func_end]
                                                    ),
                                                    func_start,
                                                )
                                                already_searched.add(
                                                    (
                                                        func_node.lineno,
                                                        func_node.end_lineno,
                                                    )
                                                )
                            else:
                                if len(already_searched) == count:
                                    return
                                if (start, end) in already_searched:
                                    continue
                                yield "\n".join(new_lines[start:end]), start
                                already_searched.add((start, end))
        else:
            # Check _cls outside the loop
            if _cls is not None:
                node = self._node_mapping.get(_cls)
                if node is None:
                    return

                new_nodes = [node]
                if allow_parent_class:
                    parent_classes = self.filter_parent_classes(
                        lines[node.lineno - 1]
                    )  # node.lineno = class ...
                    new_nodes = self.get_all_parent_classes(parent_classes, [node])
                for node in new_nodes:
                    if already_searched == count:
                        return
                    for body_item in node.body:
                        if (
                            isinstance(
                                body_item, (ast.AsyncFunctionDef, ast.FunctionDef)
                            )
                            and body_item.name == to_seach_for
                        ):
                            yield (
                                "\n".join(
                                    lines[body_item.lineno - 1 : body_item.end_lineno]
                                ),
                                body_item.lineno - 1,
                            )
                            already_searched += 1 # type: ignore
            else:
                for function in ast.walk(data):
                    if already_searched == count:
                        break
                    if (
                        isinstance(
                            function,
                            (ast.AsyncFunctionDef, ast.FunctionDef, ast.ClassDef),
                        )
                        and function.name == to_seach_for
                    ):
                        yield (
                            "\n".join(lines[function.lineno - 1 : function.end_lineno]),
                            function.lineno - 1,
                        )
                        already_searched += 1 # type: ignore
        return None

    @staticmethod
    def parse_attributes(
        index: str | dict[str, str],
        exact: bool = False,
        *,
        instance: ParserV2 | None = None,
    ):
        if exact and isinstance(index, dict):
            raise ValueError("Cannot be exact and use attributes!")

        parent_class = None
        if not exact:
            if isinstance(index, dict):
                if "function" in index:
                    ret = index["function"]
                    if "class" in index:
                        parent_class = index["class"]
                else:
                    ret = index["class"]
            else:
                attributes: list[str] = index.split(".")

                if attributes[0].startswith("discord"):
                    attributes.remove("discord")
                if len(attributes) == 2:
                    if attributes[0][0].isupper():
                        parent_class = attributes[0]
                    ret = attributes[1]
                elif len(attributes) == 1:
                    ret = attributes[0]
                else:
                    raise ValueError(f"Unable to parse {index!r}")
            ret = ret.strip(
                "()"
            )  # If people do func(), this will make sure ast searches for it properly
        else:
            ret = index
        assert isinstance(ret, str)
        if instance is not None:
            instance._reload(ret, parent_class, exact)
        else:
            return ret, parent_class, exact

    @classmethod
    def create_class(
        cls, source_code: str, index: str | dict[str, str], exact: bool = False
    ) -> Self:
        ret, parent_class, exact = cls.parse_attributes(index, exact, instance=None)  # type: ignore
        return cls(source_code, ret, parent_class, exact)


def run():
    for i in range(1, len(sys.argv)):
        file = sys.argv[i]
        with open(file, "r") as f:
            source_code = f.read()

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
        }

        # tests is a dict with the key being the function name and the values being the code to check
        tests: dict[str, tuple[str, ...]] = {
            "on_ready": ("tree.sync", "change_presence"),
            "setup_hook": (
                "tree.sync",
                "change_presence",
                "wait_for",
                "wait_until_ready",
            ),
            "on_message": ("process_commands",),
        }
        parser = None
        for function, function_tests in tests.items():
            if parser is None:
                parser = ParserV2(source_code, function)
            else:
                parser.parse_attributes(function, instance=parser)

            function_code = next(parser.parse_data())
            for test in function_tests:
                line = function_code[0]
                function_line_num = function_code[1] + 1
                to_print = f"Do not use {test!r} in your {function!r} function (Line {function_line_num})\n{basic_reasons.get(test, '- There are no suggested changes')}"
                if function == "on_message" and test == "process_commands":
                    if test in line:
                        continue
                    to_print = f"Did you forget a {test!r} in your {function!r} function (Line {function_line_num})\n{basic_reasons.get(test, '- There are no suggested changes')}"
                elif test not in line:
                    continue
                print(f"{file}#{function_line_num}")
                print(to_print)
                print()
                print("---" * 25)
                print()

        # This search here searches for variables
        tests_variables = (
            "Intents.all()",
            "eval",
            "exec",
            "time.sleep",
            "datetime.now()",
            "import requests",
            "author.send",
            "user.send",
            "member.send",
        )
        search_more = set(("author.send", "user.send", "member.send"))

        source_code_lines = source_code.splitlines()
        for line_num, line in enumerate(source_code_lines, start=1):
            for test_var in tests_variables:
                if test_var in line:
                    if test_var in search_more and source_code_lines[
                        min(line_num - 1, 0)
                    ].lstrip().startswith("for "):
                        jump_url = f"{file}#{line_num - 1}"
                    else:
                        jump_url = f"{file}#{line_num}"
                    print(jump_url)
                    print(
                        f"Do not use {test_var!r} in this context! (Line {line_num})\n{basic_reasons.get(test_var, '- There are no suggested changes')}"
                    )
                    print()
                    print("---" * 25)
                    print()


if __name__ == "__main__":
    run()
