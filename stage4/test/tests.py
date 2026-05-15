import ast
import re

from hstest import CheckResult, StageTest, TestedProgram, dynamic_test


class LangGraphTest(StageTest):
    expected_nodes = {
        "__start__",
        "user_preferences",
        "generate_riddle",
        "display_riddle",
        "reveal_hint",
        "victory",
        "defeat",
        "__end__",
    }
    required_edges = {
        ("__start__", "user_preferences", False),
        ("user_preferences", "generate_riddle", False),
        ("generate_riddle", "display_riddle", False),
        ("display_riddle", "__end__", False),
    }
    first_user = "stage-four-player-a-7f3c9a"
    second_user = "stage-four-player-b-9d4e8b"
    first_preferences = ("nature", "medium")
    second_preferences = ("geography", "hard")
    updated_preferences = ("logic", "easy")
    quest_guesses = (
        (
            "stage-four-first-wrong-1-7f3c9a",
            "stage-four-first-wrong-2-7f3c9a",
            "stage-four-first-wrong-3-7f3c9a",
            "stage-four-first-wrong-4-7f3c9a",
        ),
        (
            "stage-four-second-wrong-1-9d4e8b",
            "stage-four-second-wrong-2-9d4e8b",
            "stage-four-second-wrong-3-9d4e8b",
            "stage-four-second-wrong-4-9d4e8b",
        ),
        (
            "stage-four-third-wrong-1-4a6f2d",
            "stage-four-third-wrong-2-4a6f2d",
            "stage-four-third-wrong-3-4a6f2d",
            "stage-four-third-wrong-4-4a6f2d",
        ),
        (
            "stage-four-fourth-wrong-1-8b5e1c",
            "stage-four-fourth-wrong-2-8b5e1c",
            "stage-four-fourth-wrong-3-8b5e1c",
            "stage-four-fourth-wrong-4-8b5e1c",
        ),
    )
    graph_instruction = (
        "Print the compiled graph before gameplay, for example with "
        "`print(graph.get_graph())`, so its nodes and edges can be graded."
    )
    history_instruction = (
        "Could not grade the final StateSnapshot history. Print "
        "`list(graph.get_state_history(config=...))` after the game, using the "
        "final quest's config."
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
        graph_match = re.search(r"\bGraph\s*\(", output)
        if graph_match is None:
            return self.graph_instruction

        graph_start = output.find("(", graph_match.start())
        graph_output = self._extract_balanced(output, graph_start, "(", ")")
        if graph_output is None:
            return self.graph_instruction

        node_ids = set(re.findall(
            r"\bNode\s*\(\s*id\s*=\s*['\"]([^'\"]+)['\"]",
            graph_output,
        ))
        if not node_ids:
            return self.graph_instruction

        missing_nodes = sorted(self.expected_nodes - node_ids)
        unexpected_nodes = sorted(node_ids - self.expected_nodes)
        if missing_nodes or unexpected_nodes:
            details = []
            if missing_nodes:
                details.append(f"missing nodes: {missing_nodes}")
            if unexpected_nodes:
                details.append(f"unexpected nodes: {unexpected_nodes}")
            return "The compiled Stage 4 graph has " + "; ".join(details) + "."

        actual_edges = set()
        for marker in re.finditer(r"\bEdge\s*\(", graph_output):
            edge_start = graph_output.find("(", marker.start())
            edge_output = self._extract_balanced(
                graph_output, edge_start, "(", ")"
            )
            if edge_output is None:
                continue

            source_match = re.search(
                r"\bsource\s*=\s*['\"]([^'\"]+)['\"]", edge_output
            )
            target_match = re.search(
                r"\btarget\s*=\s*['\"]([^'\"]+)['\"]", edge_output
            )
            conditional_match = re.search(
                r"\bconditional\s*=\s*(True|False)", edge_output
            )
            if source_match and target_match and conditional_match:
                actual_edges.add((
                    source_match.group(1),
                    target_match.group(1),
                    conditional_match.group(1) == "True",
                ))

        missing_edges = sorted(self.required_edges - actual_edges)
        if missing_edges:
            readable_edges = [
                f"{source} -> {target} (unconditional)"
                for source, target, _ in missing_edges
            ]
            return (
                "The compiled Stage 4 graph is missing required backbone edges: "
                + ", ".join(readable_edges)
            )

        return None

    @staticmethod
    def _execute(main, value, context):
        try:
            return main.execute(value), None
        except Exception as error:
            return None, (
                f"The Stage 4 flow stopped while trying to {context}. Ensure the "
                "program consumes the required preference and gameplay inputs in "
                f"order. Details: {error}"
            )

    def _literal_field(self, snapshot, field, opening, closing):
        field_match = re.search(rf"\b{field}\s*=\s*", snapshot)
        if field_match is None:
            return None, False

        value_start = field_match.end()
        value_output = self._extract_balanced(
            snapshot, value_start, opening, closing
        )
        if value_output is None:
            return None, False

        try:
            return ast.literal_eval(value_output), True
        except (SyntaxError, TypeError, ValueError):
            return None, False

    def _parse_history_candidate(self, history_output):
        snapshot_markers = list(
            re.finditer(r"\bStateSnapshot\s*\(", history_output)
        )
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

            values, values_ok = self._literal_field(
                snapshot_output, "values", "{", "}"
            )
            next_nodes, next_ok = self._literal_field(
                snapshot_output, "next", "(", ")"
            )
            if not values_ok or not next_ok or not isinstance(values, dict):
                return None
            snapshots.append({"values": values, "next": next_nodes})

        return snapshots

    def _state_history(self, output):
        history_markers = list(
            re.finditer(r"\[\s*StateSnapshot\s*\(", output)
        )
        for marker in reversed(history_markers):
            history_output = self._extract_balanced(
                output, marker.start(), "[", "]"
            )
            if history_output is None:
                continue
            snapshots = self._parse_history_candidate(history_output)
            if snapshots is not None:
                return snapshots, None

        return None, self.history_instruction

    @staticmethod
    def _next_contains(snapshot, node):
        next_nodes = snapshot["next"]
        if next_nodes == node:
            return True
        try:
            return node in next_nodes
        except TypeError:
            return False

    @staticmethod
    def _next_is_empty(snapshot):
        next_nodes = snapshot["next"]
        if next_nodes is None:
            return True
        try:
            return len(next_nodes) == 0
        except TypeError:
            return False

    @staticmethod
    def _same_choice(actual, expected):
        try:
            return actual.strip().casefold() == expected.casefold()
        except AttributeError:
            return actual == expected

    def _preferences_match(self, values, category, difficulty):
        return (
            self._same_choice(values.get("preferred_category"), category)
            and self._same_choice(
                values.get("preferred_difficulty"), difficulty
            )
        )

    @staticmethod
    def _sequence_matches(actual, expected):
        try:
            return tuple(actual) == tuple(expected)
        except TypeError:
            return False

    @staticmethod
    def _find_snapshot(snapshots, predicate, start=0):
        for index in range(start, len(snapshots)):
            if predicate(snapshots[index]):
                return index
        return None

    def _history_error(self, output, guesses):
        history, parse_error = self._state_history(output)
        if parse_error is not None:
            return parse_error

        snapshots = list(reversed(history))
        category, difficulty = self.updated_preferences

        preferences_input_index = self._find_snapshot(
            snapshots,
            lambda snapshot: self._next_contains(
                snapshot, "user_preferences"
            ),
        )
        if preferences_input_index is None:
            return (
                "The final history must show the compiled graph entering the "
                "user_preferences node."
            )

        preferences_index = self._find_snapshot(
            snapshots,
            lambda snapshot: (
                self._preferences_match(
                    snapshot["values"], category, difficulty
                )
                and self._next_contains(snapshot, "generate_riddle")
            ),
            preferences_input_index + 1,
        )
        if preferences_index is None:
            return (
                "After the original player chooses an update, user_preferences "
                "must store these updated preferences in the active state before generate_riddle."
            )

        riddle_index = self._find_snapshot(
            snapshots,
            lambda snapshot: (
                self._preferences_match(
                    snapshot["values"], category, difficulty
                )
                and "riddle" in snapshot["values"]
                and snapshot["values"]["riddle"] is not None
                and "guesses" in snapshot["values"]
                and self._sequence_matches(
                    snapshot["values"]["guesses"], ()
                )
                and self._next_contains(snapshot, "display_riddle")
            ),
            preferences_index + 1,
        )
        if riddle_index is None:
            return (
                "generate_riddle must preserve the selected user "
                "preferences and add a riddle before display_riddle."
            )

        riddle = snapshots[riddle_index]["values"]["riddle"]
        if isinstance(riddle, dict):
            if (
                "category" in riddle
                and not self._same_choice(riddle["category"], category)
            ):
                return (
                    "When the riddle stores a category, it must match the selected "
                    "category."
                )
            if (
                "difficulty" in riddle
                and not self._same_choice(riddle["difficulty"], difficulty)
            ):
                return (
                    "When the riddle stores a difficulty, it must match the "
                    "selected difficulty level."
                )

        previous_index = riddle_index
        for attempt in range(1, 5):
            expected_next = "reveal_hint" if attempt < 4 else "defeat"
            expected_guesses = guesses[:attempt]
            expected_hint = attempt - 1

            def matches_attempt(
                snapshot,
                prefix=expected_guesses,
                next_node=expected_next,
                next_hint=expected_hint,
            ):
                values = snapshot["values"]
                return (
                    self._preferences_match(values, category, difficulty)
                    and values.get("riddle") == riddle
                    and "guesses" in values
                    and self._sequence_matches(values["guesses"], prefix)
                    and values.get("next_hint") == next_hint
                    and self._next_contains(snapshot, next_node)
                )

            attempt_index = self._find_snapshot(
                snapshots, matches_attempt, previous_index + 1
            )
            if attempt_index is None:
                return (
                    f"The final history must show wrong guess {attempt} "
                    f"accumulated in order with next_hint {expected_hint}, then "
                    f"route to {expected_next}."
                )
            previous_index = attempt_index

        terminal_index = self._find_snapshot(
            snapshots,
            lambda snapshot: (
                self._preferences_match(
                    snapshot["values"], category, difficulty
                )
                and snapshot["values"].get("riddle") == riddle
                and "guesses" in snapshot["values"]
                and self._sequence_matches(
                    snapshot["values"]["guesses"], guesses
                )
                and snapshot["values"].get("next_hint") == 3
                and self._next_is_empty(snapshot)
            ),
            previous_index + 1,
        )
        if terminal_index is None:
            return (
                "After the fourth wrong guess, defeat must finish the quest while "
                "preserving all four guesses, three revealed hints, the riddle, "
                "and the updated preferences."
            )

        return None

    @dynamic_test(time_limit=0)
    def test_stage_four_output(self):
        main = TestedProgram()
        try:
            initial_output = main.start()
        except Exception as error:
            return CheckResult.wrong(
                f"Could not start the your program: {error}"
            )

        graph_error = self._graph_error(initial_output)
        if graph_error is not None:
            return CheckResult.wrong(graph_error)

        first_category, first_difficulty = self.first_preferences
        second_category, second_difficulty = self.second_preferences
        updated_category, updated_difficulty = self.updated_preferences
        sequence = [
            (self.first_user, "submit a new player ID"),
            ("history", "submit an invalid category"),
            ("impossible", "submit an invalid difficulty"),
            (first_category, "resubmit a valid category after rejection"),
            (first_difficulty, "submit the first player's valid difficulty"),
        ]
        sequence.extend(
            (guess, f"submit guess {attempt} in the first quest")
            for attempt, guess in enumerate(self.quest_guesses[0], start=1)
        )
        sequence.extend([
            ("y", "start a second graph thread"),
            (self.first_user, "submit the same player ID in the second thread"),
            ("n", "keep the first player's stored preferences"),
        ])
        sequence.extend(
            (guess, f"submit guess {attempt} in the second quest")
            for attempt, guess in enumerate(self.quest_guesses[1], start=1)
        )
        sequence.extend([
            ("y", "start a third graph thread"),
            (self.second_user, "submit a different player ID"),
            (second_category, "submit the second player's category"),
            (second_difficulty, "submit the second player's difficulty"),
        ])
        sequence.extend(
            (guess, f"submit guess {attempt} in the third quest")
            for attempt, guess in enumerate(self.quest_guesses[2], start=1)
        )
        sequence.extend([
            ("y", "start a fourth graph thread"),
            (self.first_user, "return to the original player ID"),
            ("y", "choose to update the original player's preferences"),
            (updated_category, "submit the updated category"),
            (updated_difficulty, "submit the updated difficulty"),
        ])
        sequence.extend(
            (guess, f"submit guess {attempt} in the fourth quest")
            for attempt, guess in enumerate(self.quest_guesses[3], start=1)
        )
        sequence.append(("n", "finish after the fourth quest"))

        final_output = ""
        for value, context in sequence:
            final_output, error = self._execute(main, value, context)
            if error is not None:
                return CheckResult.wrong(error)

        history_error = self._history_error(
            final_output,
            self.quest_guesses[3],
        )
        if history_error is not None:
            return CheckResult.wrong(history_error)

        return CheckResult.correct()
