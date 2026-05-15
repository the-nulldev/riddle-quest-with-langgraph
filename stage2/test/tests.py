import ast
import re

from hstest import CheckResult, StageTest, TestedProgram, dynamic_test


class LangGraphTest(StageTest):
    expected_nodes = {
        "__start__",
        "generate_riddle",
        "display_riddle",
        "judge_guess",
        "__end__",
    }
    expected_edges = {
        ("__start__", "generate_riddle"),
        ("generate_riddle", "display_riddle"),
        ("display_riddle", "judge_guess"),
        ("judge_guess", "__end__"),
    }
    wrong_guess = "stage-two-impossible-answer-7f3c9a"
    history_guidance = (
        "Could not read the printed graph state history. Ensure you print "
        "list(graph.get_state_history(config=...)) after the graph finishes."
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

    @dynamic_test(time_limit=0)
    def test_stage_two_output(self):
        main = TestedProgram()
        try:
            initial_output = main.start()
        except Exception as error:
            return CheckResult.wrong(
                f"Could not start the stage-two program: {error}"
            )

        graph_match = re.search(
            r"^\s*Graph\s*\(\s*nodes\s*=.*\)\s*$",
            initial_output,
            re.MULTILINE,
        )
        if graph_match is None:
            return CheckResult.wrong(
                "Could not find the printed compiled Graph(nodes=..., edges=...) "
                "output. Ensure you printed the compiled graph."
            )

        graph_output = graph_match.group(0).strip()
        nodes_match = re.search(
            r"\bnodes\s*=\s*\{(?P<nodes>.*)\}\s*,\s*edges\s*=\s*\[",
            graph_output,
        )
        edges_match = re.search(
            r"\bedges\s*=\s*\[(?P<edges>.*)\]\s*\)\s*$",
            graph_output,
        )
        if nodes_match is None or edges_match is None:
            return CheckResult.wrong(
                "Could not read the compiled graph. Ensure you print graph.get_graph() "
                "after compiling the graph."
            )

        node_ids = re.findall(
            r"\bNode\s*\(\s*id\s*=\s*['\"]([^'\"]+)['\"]",
            nodes_match.group("nodes"),
        )
        if len(node_ids) != len(self.expected_nodes) or set(node_ids) != self.expected_nodes:
            return CheckResult.wrong(
                "The compiled graph must contain exactly these nodes: __start__, "
                "generate_riddle, display_riddle, judge_guess, and __end__."
            )

        edges_output = edges_match.group("edges")
        edge_pairs = re.findall(
            r"\bEdge\s*\(\s*source\s*=\s*['\"]([^'\"]+)['\"]\s*,\s*"
            r"target\s*=\s*['\"]([^'\"]+)['\"]",
            edges_output,
        )
        if len(edge_pairs) != len(self.expected_edges) or set(edge_pairs) != self.expected_edges:
            return CheckResult.wrong(
                "The compiled graph must use the linear connections __start__ -> "
                "generate_riddle -> display_riddle -> judge_guess -> __end__."
            )

        conditional_values = re.findall(
            r"\bconditional\s*=\s*(True|False)", edges_output
        )
        if len(conditional_values) != len(self.expected_edges) or any(
            value != "False" for value in conditional_values
        ):
            return CheckResult.wrong(
                "All four graph connections must be unconditional (conditional=False)."
            )

        try:
            continuation_output = main.execute(self.wrong_guess)
        except Exception as error:
            return CheckResult.wrong(
                f"Could not resume the stage-two program with a guess: {error}"
            )

        history_start_match = re.search(
            r"^[ \t]*\[StateSnapshot\s*\(",
            continuation_output,
            re.MULTILINE,
        )
        if history_start_match is None:
            return CheckResult.wrong(self.history_guidance)

        history_start = continuation_output.find("[", history_start_match.start())
        history_output = self._extract_balanced(
            continuation_output, history_start, "[", "]"
        )
        if history_output is None:
            return CheckResult.wrong(self.history_guidance)

        snapshot_markers = list(
            re.finditer(r"\bStateSnapshot\s*\(", history_output)
        )
        if not snapshot_markers:
            return CheckResult.wrong(self.history_guidance)

        snapshots = []
        for marker in snapshot_markers:
            snapshot_start = history_output.find("(", marker.start())
            snapshot = self._extract_balanced(
                history_output, snapshot_start, "(", ")"
            )
            if snapshot is None:
                return CheckResult.wrong(self.history_guidance)
            snapshots.append(snapshot)

        snapshot_values = []
        snapshot_next = []
        snapshot_configs = []

        for snapshot in snapshots:
            values_header = re.match(r"\(\s*values\s*=\s*", snapshot)
            if values_header is None:
                return CheckResult.wrong(self.history_guidance)

            values_start = values_header.end()
            values_output = self._extract_balanced(
                snapshot, values_start, "{", "}"
            )
            if values_output is None:
                return CheckResult.wrong(self.history_guidance)

            try:
                values = ast.literal_eval(values_output)
            except (SyntaxError, ValueError):
                return CheckResult.wrong(self.history_guidance)
            if not isinstance(values, dict):
                return CheckResult.wrong(self.history_guidance)
            snapshot_values.append(values)

            values_end = values_start + len(values_output)
            after_values = snapshot[values_end:]
            next_match = re.match(
                r"\s*,\s*next\s*=\s*(?P<next>\([^)]*\)|\[[^]]*\])\s*,\s*"
                r"config\s*=\s*",
                after_values,
            )
            if next_match is None:
                return CheckResult.wrong(self.history_guidance)

            try:
                next_nodes = ast.literal_eval(next_match.group("next"))
            except (SyntaxError, ValueError):
                return CheckResult.wrong(self.history_guidance)
            snapshot_next.append(next_nodes)

            config_start = values_end + next_match.end()
            config_output = self._extract_balanced(
                snapshot, config_start, "{", "}"
            )
            if config_output is None:
                return CheckResult.wrong(self.history_guidance)

            try:
                config = ast.literal_eval(config_output)
            except (SyntaxError, ValueError):
                return CheckResult.wrong(self.history_guidance)
            snapshot_configs.append(config)

        records = []
        for text, values, next_nodes, config in zip(
            snapshots, snapshot_values, snapshot_next, snapshot_configs
        ):
            if isinstance(next_nodes, str):
                node_names = {next_nodes}
            else:
                try:
                    node_names = {str(node) for node in next_nodes}
                except TypeError:
                    node_names = {str(next_nodes)}
            records.append(
                {
                    "text": text,
                    "values": values,
                    "next": node_names,
                    "config": config,
                }
            )

        required_checkpoints = {
            "__start__",
            "generate_riddle",
            "display_riddle",
            "judge_guess",
        }
        recorded_next_nodes = set().union(
            *(record["next"] for record in records)
        )
        if not required_checkpoints.issubset(recorded_next_nodes):
            return CheckResult.wrong(
                "The graph history does not show the complete stage-two flow. "
                "Invoke the compiled graph through generate_riddle, display_riddle, "
                "and judge_guess before printing its state history."
            )

        display_records = [
            record for record in records if "display_riddle" in record["next"]
        ]
        if not any(
            re.search(r"\bInterrupt\s*\(", record["text"])
            for record in display_records
        ):
            return CheckResult.wrong(
                "The history does not show display_riddle pausing for the player. "
                "Call interrupt() inside display_riddle before continuing."
            )

        judge_records = [
            record for record in records if "judge_guess" in record["next"]
        ]
        if not any(
            record["values"].get("guess") == self.wrong_guess
            for record in judge_records
        ):
            return CheckResult.wrong(
                "The resumed guess is not saved before judge_guess runs. Resume the "
                "graph with Command(resume=...) and return that value as the guess."
            )

        terminal_records = [record for record in records if not record["next"]]
        if not any(
            record["values"].get("guess") == self.wrong_guess
            for record in terminal_records
        ):
            return CheckResult.wrong(
                "The history does not show judge_guess completing with the submitted "
                "guess preserved in graph state."
            )

        riddle = next(
            (
                record["values"].get("riddle")
                for record in display_records
                if record["values"].get("riddle") is not None
            ),
            None,
        )
        if not hasattr(riddle, "keys"):
            return CheckResult.wrong(
                "The history does not show generate_riddle saving a structured riddle "
                "before display_riddle runs."
            )

        required_riddle_fields = {"question", "answer", "hints"}
        if not required_riddle_fields.issubset(set(riddle)):
            return CheckResult.wrong(
                "The generated riddle in graph state must include a question, answer, "
                "and three hints."
            )

        if any(
            value is None or not str(value).strip()
            for value in (riddle["question"], riddle["answer"])
        ):
            return CheckResult.wrong(
                "The generated riddle must include a non-empty question and answer."
            )

        try:
            hints = list(riddle["hints"])
        except TypeError:
            hints = []
        normalized_hints = [
            "" if hint is None else str(hint).strip() for hint in hints
        ]
        if (
            len(normalized_hints) != 3
            or any(not hint for hint in normalized_hints)
            or len(set(normalized_hints)) != 3
        ):
            return CheckResult.wrong(
                "The generated riddle must include exactly three distinct, non-empty "
                "hints."
            )

        saved_riddles = [
            record["values"]["riddle"]
            for record in records
            if "riddle" in record["values"]
        ]
        if any(saved_riddle != riddle for saved_riddle in saved_riddles):
            return CheckResult.wrong(
                "The generated riddle changes while the graph is paused or resumed. "
                "Keep the same riddle in state through judge_guess."
            )

        thread_ids = []
        for record in records:
            config = record["config"]
            configurable = config.get("configurable") if hasattr(config, "get") else None
            thread_id = (
                configurable.get("thread_id")
                if hasattr(configurable, "get")
                else None
            )
            if re.fullmatch(
                r"quest-[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-"
                r"[89ab][0-9a-f]{3}-[0-9a-f]{12}",
                str(thread_id or ""),
                re.IGNORECASE,
            ) is None:
                return CheckResult.wrong(
                    "The state history must use a quest-<UUID> thread ID. Create the "
                    "checkpointer config with thread_id=f'quest-{uuid4()}'."
                )
            thread_ids.append(str(thread_id))

        if len(set(thread_ids)) != 1:
            return CheckResult.wrong(
                "The pause and resume checkpoints must stay in the same quest thread. "
                "Reuse the same thread_id when invoking Command(resume=...)."
            )

        return CheckResult.correct()