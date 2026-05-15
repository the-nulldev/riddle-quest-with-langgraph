import ast
import re

from hstest import CheckResult, StageTest, TestedProgram, dynamic_test


_MISSING = object()


class LangGraphTest(StageTest):
    expected_nodes = {
        "__start__",
        "generate_riddle",
        "display_riddle",
        "reveal_hint",
        "victory",
        "defeat",
        "__end__",
    }
    expected_edges = {
        ("__start__", "generate_riddle"): False,
        ("generate_riddle", "display_riddle"): False,
        ("display_riddle", "defeat"): True,
        ("display_riddle", "reveal_hint"): True,
        ("display_riddle", "victory"): True,
        ("reveal_hint", "defeat"): True,
        ("reveal_hint", "reveal_hint"): True,
        ("reveal_hint", "victory"): True,
        ("defeat", "__end__"): False,
        ("victory", "__end__"): False,
    }
    first_quest_guesses = (
        "stage-three-first-wrong-1-7f3c9a",
        "stage-three-first-wrong-2-7f3c9a",
        "stage-three-first-wrong-3-7f3c9a",
        "stage-three-first-wrong-4-7f3c9a",
    )
    second_quest_guesses = (
        "stage-three-second-wrong-1-9d4e8b",
        "stage-three-second-wrong-2-9d4e8b",
        "stage-three-second-wrong-3-9d4e8b",
        "stage-three-second-wrong-4-9d4e8b",
    )
    thread_pattern = (
        r"quest-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
        r"[0-9a-f]{4}-[0-9a-f]{12}"
    )
    graph_help = (
        "Could not read the compiled graph. Print the compiled graph with "
        "print(graph.get_graph()) before starting the quest."
    )
    history_help = (
        "Could not read the graph state history. Print "
        "list(graph.get_state_history(config=config)) after the final quest."
    )

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

    def _graph_error(self, output):
        graph_output = None
        for marker in re.finditer(r"\bGraph\s*\(", output):
            start = output.find("(", marker.start())
            graph_call = self._extract_balanced(output, start, "(", ")")
            if graph_call is not None:
                graph_output = graph_call
                break

        if graph_output is None:
            return self.graph_help

        node_ids = set(re.findall(
            r"\bNode\s*\(\s*id\s*=\s*['\"]([^'\"]+)['\"]",
            graph_output,
        ))
        if not node_ids:
            return self.graph_help

        missing_nodes = sorted(self.expected_nodes - node_ids)
        if missing_nodes:
            return (
                "Add the missing stage-three graph nodes before compiling: "
                f"{', '.join(missing_nodes)}."
            )

        actual_edges = set()
        for marker in re.finditer(r"\bEdge\s*\(", graph_output):
            start = graph_output.find("(", marker.start())
            edge_call = self._extract_balanced(
                graph_output, start, "(", ")"
            )
            if edge_call is None:
                continue

            source = self._quoted_argument(edge_call, "source")
            target = self._quoted_argument(edge_call, "target")
            conditional_match = re.search(
                r"\bconditional\s*=\s*(True|False)\b", edge_call
            )
            if source is None or target is None or conditional_match is None:
                continue
            actual_edges.add(
                (source, target, conditional_match.group(1) == "True")
            )

        if not actual_edges:
            return self.graph_help

        missing_edges = [
            (source, target, conditional)
            for (source, target), conditional in self.expected_edges.items()
            if (source, target, conditional) not in actual_edges
        ]
        if missing_edges:
            connections = ", ".join(
                f"{source} -> {target}"
                + (" (conditional)" if conditional else "")
                for source, target, conditional in missing_edges
            )
            return (
                "Connect the compiled graph with the required stage-three "
                f"routing edges. Missing: {connections}."
            )

        return None

    @staticmethod
    def _quoted_argument(call, name):
        match = re.search(
            rf"\b{re.escape(name)}\s*=\s*"
            rf"(?P<quote>['\"])(?P<value>.*?)(?P=quote)",
            call,
            re.DOTALL,
        )
        return match.group("value") if match is not None else None

    @classmethod
    def _quest_ids(cls, output):
        return set(re.findall(cls.thread_pattern, output, re.IGNORECASE))

    @staticmethod
    def _runtime_error(action, error):
        return (
            f"The program raised {type(error).__name__} while {action}: {error}. "
            "Fix that runtime error and run the quest again."
        )

    def _play_defeat_quest(self, main, guesses, quest_name):
        outputs = []

        for attempt, guess in enumerate(guesses, start=1):
            try:
                output = main.execute(guess)
            except Exception as error:
                return None, self._runtime_error(
                    f"submitting guess {attempt} in the {quest_name} quest",
                    error,
                )

            outputs.append(output)

        return outputs, None

    def _field_container(self, call, field, opening, closing):
        depths = {"(": 0, "[": 0, "{": 0}
        matching_opening = {")": "(", "]": "[", "}": "{"}
        quote = None
        escaped = False
        index = 0

        while index < len(call):
            character = call[index]
            if quote is not None:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == quote:
                    quote = None
                index += 1
                continue

            if character in ("'", '"'):
                quote = character
                index += 1
                continue
            if character in depths:
                depths[character] += 1
                index += 1
                continue
            if character in matching_opening:
                depths[matching_opening[character]] -= 1
                index += 1
                continue

            at_top_level = (
                depths["("] == 1
                and depths["["] == 0
                and depths["{"] == 0
            )
            if at_top_level and call.startswith(field, index):
                field_end = index + len(field)
                before_is_word = (
                    index > 0
                    and (call[index - 1].isalnum() or call[index - 1] == "_")
                )
                after_is_word = (
                    field_end < len(call)
                    and (
                        call[field_end].isalnum()
                        or call[field_end] == "_"
                    )
                )
                value_start = field_end
                while (
                    value_start < len(call)
                    and call[value_start].isspace()
                ):
                    value_start += 1
                if (
                    not before_is_word
                    and not after_is_word
                    and value_start < len(call)
                    and call[value_start] == "="
                ):
                    value_start += 1
                    while (
                        value_start < len(call)
                        and call[value_start].isspace()
                    ):
                        value_start += 1
                    return self._extract_balanced(
                        call, value_start, opening, closing
                    )
            index += 1

        return None

    @staticmethod
    def _dictionary_node_fields(node):
        if not isinstance(node, ast.Dict):
            return None

        fields = {}
        for key_node, value_node in zip(node.keys, node.values):
            try:
                key = ast.literal_eval(key_node)
            except (SyntaxError, ValueError, TypeError):
                continue
            if isinstance(key, str):
                fields[key] = value_node
        return fields

    @classmethod
    def _dictionary_fields(cls, output):
        try:
            node = ast.parse(output, mode="eval").body
        except (SyntaxError, ValueError):
            return None
        return cls._dictionary_node_fields(node)

    @staticmethod
    def _literal(node):
        try:
            return True, ast.literal_eval(node)
        except (SyntaxError, ValueError, TypeError):
            return False, None

    @classmethod
    def _hint_count(cls, riddle_node):
        riddle_fields = cls._dictionary_node_fields(riddle_node)
        if riddle_fields is None and isinstance(riddle_node, ast.Call):
            riddle_fields = {
                keyword.arg: keyword.value
                for keyword in riddle_node.keywords
                if keyword.arg is not None
            }
        if riddle_fields is None or "hints" not in riddle_fields:
            return _MISSING

        hints_node = riddle_fields["hints"]
        if isinstance(hints_node, (ast.List, ast.Tuple, ast.Set)):
            return len(hints_node.elts)

        parsed, hints = cls._literal(hints_node)
        if parsed and isinstance(hints, (list, tuple, set)):
            return len(hints)
        return _MISSING

    def _parse_snapshot(self, snapshot):
        values_output = self._field_container(
            snapshot, "values", "{", "}"
        )
        next_output = self._field_container(snapshot, "next", "(", ")")
        config_output = self._field_container(
            snapshot, "config", "{", "}"
        )
        if None in (values_output, next_output, config_output):
            return None

        values_fields = self._dictionary_fields(values_output)
        config_fields = self._dictionary_fields(config_output)
        if values_fields is None or config_fields is None:
            return None

        try:
            next_nodes = ast.literal_eval(next_output)
        except (SyntaxError, ValueError):
            return None
        if not isinstance(next_nodes, (list, tuple)):
            return None

        parsed_values = {}
        for field in ("guesses", "next_hint"):
            node = values_fields.get(field, _MISSING)
            if node is _MISSING:
                parsed_values[field] = _MISSING
                continue
            parsed, value = self._literal(node)
            if not parsed:
                return None
            if field == "guesses" and isinstance(value, (list, tuple)):
                value = tuple(value)
            parsed_values[field] = value

        configurable_node = config_fields.get("configurable", _MISSING)
        thread_id = _MISSING
        if configurable_node is not _MISSING:
            configurable_fields = self._dictionary_node_fields(
                configurable_node
            )
            if configurable_fields is None:
                return None
            thread_node = configurable_fields.get("thread_id", _MISSING)
            if thread_node is not _MISSING:
                parsed, thread_id = self._literal(thread_node)
                if not parsed:
                    return None

        riddle_node = values_fields.get("riddle", _MISSING)
        hint_count = (
            _MISSING
            if riddle_node is _MISSING
            else self._hint_count(riddle_node)
        )

        return {
            "next": tuple(next_nodes),
            "guesses": parsed_values["guesses"],
            "next_hint": parsed_values["next_hint"],
            "thread_id": thread_id,
            "hint_count": hint_count,
            "interrupt": re.search(r"\bInterrupt\s*\(", snapshot) is not None,
        }

    def _parse_history(self, output):
        history_markers = list(re.finditer(
            r"\[\s*StateSnapshot\s*\(", output
        ))
        if not history_markers:
            return None

        history_start = history_markers[-1].start()
        history_output = self._extract_balanced(
            output, history_start, "[", "]"
        )
        if history_output is None:
            return None

        snapshot_markers = list(re.finditer(
            r"\bStateSnapshot\s*\(", history_output
        ))
        if not snapshot_markers:
            return None

        snapshots = []
        for marker in snapshot_markers:
            snapshot_start = history_output.find("(", marker.start())
            snapshot_output = self._extract_balanced(
                history_output, snapshot_start, "(", ")"
            )
            if snapshot_output is None:
                return None
            snapshot = self._parse_snapshot(snapshot_output)
            if snapshot is None:
                return None
            snapshots.append(snapshot)
        return snapshots

    def _history_error(self, output, guesses, first_quest_output):
        snapshots = self._parse_history(output)
        if snapshots is None:
            return self.history_help

        if not any(snapshot["hint_count"] == 3 for snapshot in snapshots):
            return (
                "Store exactly three hints in the generated riddle state so "
                "reveal_hint can advance through all three."
            )

        initial_routes = [
            snapshot
            for snapshot in snapshots
            if snapshot["guesses"] == ()
            and snapshot["next"] == ("display_riddle",)
        ]
        initial_checkpoints = [
            snapshot
            for snapshot in initial_routes
            if snapshot["next_hint"] == 0
        ]
        if not initial_checkpoints:
            return (
                "Initialize guesses as empty and next_hint as 0 before the "
                "display_riddle guess checkpoint."
            )
        initial_checkpoint = next(
            (
                snapshot
                for snapshot in initial_checkpoints
                if snapshot["interrupt"]
            ),
            None,
        )
        if initial_checkpoint is None:
            return (
                "Call interrupt() in display_riddle so the initial guess is "
                "recorded as a suspended StateSnapshot checkpoint."
            )

        matched_checkpoints = [initial_checkpoint]
        for completed_guesses in range(1, 4):
            expected_guesses = tuple(guesses[:completed_guesses])
            accumulated = [
                snapshot
                for snapshot in snapshots
                if snapshot["guesses"] == expected_guesses
            ]
            if not accumulated:
                return (
                    "Configure guesses with an additive reducer and have each "
                    "guess-taking node return only the newly submitted guess; "
                    f"the history must preserve the first {completed_guesses} "
                    "guesses in order."
                )

            routed = [
                snapshot
                for snapshot in accumulated
                if snapshot["next"] == ("reveal_hint",)
            ]
            if not routed:
                return (
                    "Route each of the first three wrong guesses to "
                    "reveal_hint before allowing the next guess."
                )

            hint_checkpoints = [
                snapshot
                for snapshot in routed
                if snapshot["next_hint"] == completed_guesses - 1
            ]
            if not hint_checkpoints:
                return (
                    "Advance next_hint once in each completed reveal_hint node; "
                    "the history must progress from 0 to 3 without skips."
                )

            interrupt_checkpoint = next(
                (
                    snapshot
                    for snapshot in hint_checkpoints
                    if snapshot["interrupt"]
                ),
                None,
            )
            if interrupt_checkpoint is None:
                return (
                    "Call interrupt() in reveal_hint after each of the first "
                    "three wrong guesses so every follow-up guess has a "
                    "suspended checkpoint."
                )
            matched_checkpoints.append(interrupt_checkpoint)

        all_guesses = tuple(guesses)
        completed_states = [
            snapshot
            for snapshot in snapshots
            if snapshot["guesses"] == all_guesses
        ]
        if not completed_states:
            return (
                "The reducer-backed guesses state must contain all four "
                "submitted guesses in order after the fourth attempt."
            )

        defeat_routes = [
            snapshot
            for snapshot in completed_states
            if snapshot["next"] == ("defeat",)
        ]
        if not defeat_routes:
            return (
                "Route the fourth wrong guess to the defeat node instead of "
                "revealing another hint or requesting another guess."
            )

        completed_defeat_routes = [
            snapshot
            for snapshot in defeat_routes
            if snapshot["next_hint"] == 3
        ]
        if not completed_defeat_routes:
            return (
                "The defeat checkpoint must retain next_hint as 3 after the "
                "three hint nodes have completed."
            )

        terminal_states = [
            snapshot
            for snapshot in completed_states
            if snapshot["next"] == ()
            and snapshot["next_hint"] == 3
            and not snapshot["interrupt"]
        ]
        if not terminal_states:
            return (
                "After defeat, end the graph with four guesses and three used "
                "hints; do not suspend for a fifth guess."
            )

        matched_checkpoints.extend((
            completed_defeat_routes[0],
            terminal_states[0],
        ))
        thread_id = matched_checkpoints[0]["thread_id"]
        if thread_id is _MISSING or thread_id in (None, ""):
            return (
                "Compile with a checkpointer and use one config containing a "
                "thread_id for every invocation and history lookup in a quest."
            )
        if any(
            snapshot["thread_id"] is _MISSING
            or snapshot["thread_id"] != thread_id
            for snapshot in matched_checkpoints[1:]
        ):
            return (
                "Use the same thread_id config for every invocation within one "
                "quest, including get_state_history()."
            )

        first_thread_ids = {
            quest_id.casefold()
            for quest_id in self._quest_ids(first_quest_output)
        }
        if not first_thread_ids:
            return (
                "Generate and print a quest thread ID for the first quest so "
                "the replay can be verified; the surrounding wording may be "
                "anything."
            )
        if str(thread_id).casefold() in first_thread_ids:
            return (
                "Starting another quest must create a fresh thread_id and empty "
                "guess state instead of reusing the first quest's checkpoint."
            )

        return None

    @dynamic_test(time_limit=0)
    def test_stage_three_output(self):
        main = TestedProgram()
        try:
            initial_output = main.start()
        except Exception as error:
            return CheckResult.wrong(
                self._runtime_error("starting the stage-three program", error)
            )

        graph_error = self._graph_error(initial_output)
        if graph_error is not None:
            return CheckResult.wrong(graph_error)

        first_quest_outputs, interaction_error = self._play_defeat_quest(
            main, self.first_quest_guesses, "first"
        )
        if interaction_error is not None:
            return CheckResult.wrong(interaction_error)

        try:
            main.execute("y")
        except Exception as error:
            return CheckResult.wrong(
                self._runtime_error(
                    "starting a replay after the first quest", error
                )
            )

        _, interaction_error = self._play_defeat_quest(
            main, self.second_quest_guesses, "second"
        )
        if interaction_error is not None:
            return CheckResult.wrong(interaction_error)

        try:
            final_output = main.execute("n")
        except Exception as error:
            return CheckResult.wrong(
                self._runtime_error(
                    "ending the replay loop and printing state history", error
                )
            )

        first_quest_output = "\n".join((
            initial_output,
            *first_quest_outputs,
        ))
        history_error = self._history_error(
            final_output,
            self.second_quest_guesses,
            first_quest_output,
        )
        if history_error is not None:
            return CheckResult.wrong(history_error)

        return CheckResult.correct()