import ast
import re

from hstest import CheckResult, StageTest, TestedProgram, dynamic_test


class LangGraphTest(StageTest):
    expected_nodes = {
        "__start__",
        "user_preferences",
        "generate_vault",
        "choose_vault",
        "display_riddle",
        "reveal_hint",
        "victory",
        "defeat",
        "__end__",
    }
    first_user = "stage-five-player-a-6c2f8d"
    first_preferences = ("nature", "medium")
    first_guesses = (
        "stage-five-first-wrong-1-6c2f8d",
        "stage-five-first-wrong-2-6c2f8d",
        "stage-five-first-wrong-3-6c2f8d",
        "stage-five-first-wrong-4-6c2f8d",
    )
    second_guesses = (
        "stage-five-second-wrong-1-4e9a1c",
        "stage-five-second-wrong-2-4e9a1c",
        "stage-five-second-wrong-3-4e9a1c",
        "stage-five-second-wrong-4-4e9a1c",
    )
    graph_guidance = (
        "Could not evaluate the compiled graph. Print graph.get_graph() before "
        "the quest starts so its complete nodes and edges are available."
    )
    history_guidance = (
        "Could not evaluate the graph state history. Print "
        "list(graph.get_state_history(config)) at the end so every complete "
        "StateSnapshot, including values, next tasks, and interrupts, is available."
    )
    missing = object()

    @staticmethod
    def _extract_balanced(text, start, opening, closing):
        if start >= len(text) or text[start] != opening:
            return None

        depth = 0
        quote = None
        escaped = False

        for index in range(start, len(text)):
            character = text[index]

            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                continue

            if character in ("'", '"'):
                quote = character
            elif character == opening:
                depth += 1
            elif character == closing:
                depth -= 1
                if depth == 0:
                    return text[start:index + 1]

        return None

    @classmethod
    def _state_value(cls, state, key):
        try:
            return state[key]
        except (AttributeError, KeyError, TypeError):
            return cls.missing

    @classmethod
    def _normalized(cls, value):
        if value is cls.missing or value is None:
            return ""
        return " ".join(str(value).split()).casefold()

    @classmethod
    def _as_sequence(cls, value):
        if (
            value is cls.missing
            or isinstance(value, (str, bytes))
            or hasattr(value, "keys")
        ):
            return None
        try:
            return list(value)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _integer(cls, value):
        text = cls._normalized(value)
        if not text:
            return None
        try:
            number = float(text)
        except ValueError:
            return None
        if not number.is_integer():
            return None
        return int(number)

    @staticmethod
    def _has_interrupt(snapshot):
        return re.search(r"\bInterrupt\s*\(", snapshot["raw"]) is not None

    @classmethod
    def _parse_history(cls, output):
        history_matches = list(
            re.finditer(r"\[\s*StateSnapshot\s*\(", output)
        )
        if not history_matches:
            return None, cls.history_guidance

        history_start = history_matches[-1].start()
        history_output = cls._extract_balanced(
            output,
            history_start,
            "[",
            "]",
        )
        if history_output is None:
            return None, cls.history_guidance

        markers = list(re.finditer(r"\bStateSnapshot\s*\(", history_output))
        if not markers:
            return None, cls.history_guidance

        snapshots = []
        for marker in markers:
            snapshot_start = history_output.find("(", marker.start())
            snapshot_output = cls._extract_balanced(
                history_output,
                snapshot_start,
                "(",
                ")",
            )
            if snapshot_output is None:
                return None, cls.history_guidance

            values_header = re.match(
                r"\(\s*values\s*=\s*",
                snapshot_output,
            )
            if values_header is None:
                return None, cls.history_guidance
            values_output = cls._extract_balanced(
                snapshot_output,
                values_header.end(),
                "{",
                "}",
            )
            if values_output is None:
                return None, cls.history_guidance

            next_header = re.search(r"\bnext\s*=\s*", snapshot_output)
            if next_header is None:
                return None, cls.history_guidance
            next_output = cls._extract_balanced(
                snapshot_output,
                next_header.end(),
                "(",
                ")",
            )
            if next_output is None:
                return None, cls.history_guidance

            try:
                values = ast.literal_eval(values_output)
                next_nodes = ast.literal_eval(next_output)
                next_nodes = tuple(next_nodes)
            except (SyntaxError, TypeError, ValueError):
                return None, cls.history_guidance

            snapshots.append(
                {
                    "values": values,
                    "next": next_nodes,
                    "raw": snapshot_output,
                }
            )

        return snapshots, None

    @classmethod
    def _vault_records(cls, values, category, difficulty, context):
        riddles = cls._as_sequence(cls._state_value(values, "riddles"))
        if riddles is None or len(riddles) != 2:
            return None, f"The {context} state must contain exactly two generated vault records."

        records = {}
        for riddle in riddles:
            number = cls._integer(cls._state_value(riddle, "vault_number"))
            if number not in {1, 2} or number in records:
                return None, "Generated vault records must have unique vault numbers 1 and 2."
            records[number] = riddle

        expected_metadata = {
            1: (category, difficulty),
            2: ("general", difficulty),
        }
        for number, metadata in expected_metadata.items():
            error = cls._riddle_error(
                records[number],
                metadata[0],
                metadata[1],
                number,
                f"{context} vault {number}",
            )
            if error is not None:
                return None, error

        return records, None

    @classmethod
    def _riddles_match(cls, first, second):
        fields = (
            "vault_number",
            "category",
            "difficulty",
            "title",
            "question",
            "answer",
        )
        if any(
            cls._normalized(cls._state_value(first, field))
            != cls._normalized(cls._state_value(second, field))
            for field in fields
        ):
            return False

        first_hints = cls._as_sequence(cls._state_value(first, "hints"))
        second_hints = cls._as_sequence(cls._state_value(second, "hints"))
        if first_hints is None or second_hints is None:
            return False
        return [cls._normalized(hint) for hint in first_hints] == [
            cls._normalized(hint) for hint in second_hints
        ]

    @classmethod
    def _guesses_match(cls, values, expected_guesses):
        guesses = cls._as_sequence(cls._state_value(values, "guesses"))
        if guesses is None:
            return False
        return [cls._normalized(guess) for guess in guesses] == [
            cls._normalized(guess) for guess in expected_guesses
        ]

    def _graph_error(self, output):
        graph_match = re.search(r"\bGraph\s*\(", output)
        if graph_match is None:
            return self.graph_guidance

        graph_start = output.find("(", graph_match.start())
        graph_output = self._extract_balanced(output, graph_start, "(", ")")
        if graph_output is None:
            return self.graph_guidance

        node_ids = set(re.findall(
            r"\bNode\s*\(\s*id\s*=\s*['\"]([^'\"]+)['\"]",
            graph_output,
        ))
        if not node_ids:
            return self.graph_guidance

        missing_nodes = sorted(self.expected_nodes - node_ids)
        if missing_nodes:
            return (
                "The compiled graph is missing required nodes: "
                f"{missing_nodes}."
            )

        edge_entries = set(re.findall(
            r"\bEdge\s*\(\s*source\s*=\s*['\"]([^'\"]+)['\"]\s*,\s*"
            r"target\s*=\s*['\"]([^'\"]+)['\"]",
            graph_output,
        ))
        if not edge_entries:
            return self.graph_guidance
        if ("__start__", "user_preferences") not in edge_entries:
            return "The compiled graph must begin by routing __start__ to user_preferences."

        return None

    @staticmethod
    def _execute(main, value, context):
        try:
            return main.execute(value), None
        except BaseException as error:
            return None, f"Could not {context}: {error}"

    def _play_to_replay(self, main, guesses, quest_name):
        outputs = []

        for attempt, guess in enumerate(guesses, start=1):
            output, error = self._execute(
                main,
                guess,
                f"submit guess {attempt} in the {quest_name} quest",
            )
            if error is not None:
                return None, error
            outputs.append(output)

        return outputs, None

    @classmethod
    def _riddle_error(cls, riddle, category, difficulty, vault_number, context):
        if cls._integer(cls._state_value(riddle, "vault_number")) != vault_number:
            return f"The {context} record must use vault number {vault_number}."
        if cls._normalized(cls._state_value(riddle, "category")) != cls._normalized(category):
            return f"The {context} record must use the '{category}' category."
        if cls._normalized(cls._state_value(riddle, "difficulty")) != cls._normalized(difficulty):
            return f"The {context} record must use the selected '{difficulty}' difficulty."

        for field in ("title", "question", "answer"):
            if not cls._normalized(cls._state_value(riddle, field)):
                return f"The {context} record must include a non-empty {field}."

        hints = cls._as_sequence(cls._state_value(riddle, "hints"))
        if hints is None or len(hints) != 3:
            return f"The {context} record must include exactly three hints."
        if any(not cls._normalized(hint) for hint in hints):
            return f"All three hints in the {context} record must be non-empty."

        return None

    def _history_error(self, output, final_state):
        snapshots, error = self._parse_history(output)
        if error is not None:
            return error

        category = final_state["preferred_category"]
        difficulty = final_state["preferred_difficulty"]
        selected_number = final_state["selected_vault"]
        guesses = final_state["guesses"]

        fan_out = [
            snapshot
            for snapshot in snapshots
            if snapshot["next"].count("generate_vault") == 2
        ]
        if not fan_out:
            return (
                "The history must show a Send fan-out with exactly two "
                "generate_vault next tasks."
            )

        persisted_fan_out = [
            snapshot
            for snapshot in fan_out
            if self._normalized(self._state_value(
                snapshot["values"],
                "preferred_category",
            )) == self._normalized(category)
            and self._normalized(self._state_value(
                snapshot["values"],
                "preferred_difficulty",
            )) == self._normalized(difficulty)
        ]
        if not persisted_fan_out:
            return (
                "The replayed same-user quest must restore the saved category and "
                "difficulty."
            )

        choice_snapshots = [
            snapshot
            for snapshot in snapshots
            if "choose_vault" in snapshot["next"]
            and self._has_interrupt(snapshot)
        ]
        if not choice_snapshots:
            return (
                "After both workers converge, interrupt for the user to choose a vault at the choose_vault node."
            )

        choice_records = None
        vault_error = None
        for snapshot in choice_snapshots:
            records, error = self._vault_records(
                snapshot["values"],
                category,
                difficulty,
                "vault-choice",
            )
            if error is None:
                choice_records = records
                break
            vault_error = error
        if choice_records is None:
            return vault_error

        selected_snapshots = []
        for snapshot in snapshots:
            values = snapshot["values"]
            if "display_riddle" not in snapshot["next"]:
                continue
            if not self._has_interrupt(snapshot):
                continue
            if self._integer(self._state_value(
                values,
                "selected_vault",
            )) != selected_number:
                continue
            if not self._guesses_match(values, ()):
                continue
            selected_riddle = self._state_value(values, "riddle")
            if self._riddles_match(
                selected_riddle,
                choice_records[selected_number],
            ):
                selected_snapshots.append(snapshot)

        if not selected_snapshots:
            return (
                f"After rejecting the unavailable choice, selecting vault "
                f"{selected_number} must store that vault and its matching riddle "
                "before gameplay."
            )

        for hint_index in range(3):
            hint_snapshots = [
                snapshot
                for snapshot in snapshots
                if "reveal_hint" in snapshot["next"]
                and self._has_interrupt(snapshot)
                and self._guesses_match(
                    snapshot["values"],
                    guesses[:hint_index + 1],
                )
                and self._integer(self._state_value(
                    snapshot["values"],
                    "next_hint",
                )) == hint_index
            ]
            if not hint_snapshots:
                return (
                    f"The history must show the entered incorrect guess {hint_index + 1} "
                    f"flowing through reveal_hint with hint index {hint_index}."
                )

        defeat_snapshots = [
            snapshot
            for snapshot in snapshots
            if "defeat" in snapshot["next"]
            and self._guesses_match(snapshot["values"], guesses)
            and self._integer(self._state_value(
                snapshot["values"],
                "next_hint",
            )) == 3
        ]
        if not defeat_snapshots:
            return (
                "The history must route the four submitted wrong guesses through "
                "three hints and then to defeat."
            )

        terminal_error = None
        for snapshot in snapshots:
            if snapshot["next"]:
                continue
            values = snapshot["values"]
            if not self._guesses_match(values, guesses):
                continue

            records, error = self._vault_records(
                values,
                category,
                difficulty,
                "terminal",
            )
            if error is not None:
                terminal_error = error
                continue
            if self._integer(self._state_value(
                values,
                "selected_vault",
            )) != selected_number:
                terminal_error = (
                    f"The terminal state must preserve selected vault {selected_number}."
                )
                continue
            if not self._riddles_match(
                self._state_value(values, "riddle"),
                records[selected_number],
            ):
                terminal_error = (
                    "The terminal selected riddle must match the selected generated vault."
                )
                continue
            if not self._normalized(self._state_value(values, "result")):
                terminal_error = (
                    "The terminal state must record a result after the defeat flow."
                )
                continue
            return None

        if terminal_error is not None:
            return terminal_error
        return (
            "The terminal StateSnapshot must preserve the two vaults, valid "
            "selection, four guesses, and final result."
        )

    @dynamic_test(time_limit=0)
    def test_stage_five_output(self):
        main = TestedProgram()
        try:
            startup_output = main.start()
        except Exception as error:
            return CheckResult.wrong(f"Could not start stage five: {error}")

        error = self._graph_error(startup_output)
        if error is not None:
            return CheckResult.wrong(error)

        first_category, first_difficulty = self.first_preferences
        _, error = self._execute(main, self.first_user, "submit the first player ID")
        if error is not None:
            return CheckResult.wrong(error)
        _, error = self._execute(main, first_category, "submit the first category")
        if error is not None:
            return CheckResult.wrong(error)
        _, error = self._execute(
            main,
            first_difficulty,
            "submit the first difficulty",
        )
        if error is not None:
            return CheckResult.wrong(error)
        _, error = self._execute(
            main,
            "1",
            "select vault 1 in the first quest",
        )
        if error is not None:
            return CheckResult.wrong(error)

        _, error = self._play_to_replay(
            main,
            self.first_guesses,
            "first",
        )
        if error is not None:
            return CheckResult.wrong(error)

        _, error = self._execute(main, "y", "start the second quest")
        if error is not None:
            return CheckResult.wrong(error)

        _, error = self._execute(
            main,
            self.first_user,
            "submit the same player ID in a new quest",
        )
        if error is not None:
            return CheckResult.wrong(error)
        _, error = self._execute(
            main,
            "no",
            "reuse the saved preferences",
        )
        if error is not None:
            return CheckResult.wrong(error)

        _, error = self._execute(
            main,
            "3",
            "submit an unavailable vault number",
        )
        if error is not None:
            return CheckResult.wrong(error)
        _, error = self._execute(
            main,
            "2",
            "select vault 2 after the invalid selection",
        )
        if error is not None:
            return CheckResult.wrong(error)

        _, error = self._play_to_replay(
            main,
            self.second_guesses,
            "second",
        )
        if error is not None:
            return CheckResult.wrong(error)

        history_output, error = self._execute(main, "n", "finish the second quest")
        if error is not None:
            return CheckResult.wrong(error)

        expected_state = {
            "preferred_category": first_category,
            "preferred_difficulty": first_difficulty,
            "selected_vault": 2,
            "guesses": self.second_guesses,
        }
        error = self._history_error(history_output, expected_state)
        if error is not None:
            return CheckResult.wrong(error)

        return CheckResult.correct()