import ast
import re

from hstest import CheckResult, StageTest, TestedProgram, dynamic_test


class LangGraphTest(StageTest):
    expected_nodes = {"__start__", "generate_riddle", "display_riddle", "__end__"}
    expected_edges = [
        ("__start__", "generate_riddle"),
        ("generate_riddle", "display_riddle"),
        ("display_riddle", "__end__"),
    ]

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

    def _find_result(self, output):
        result = None
        for start, character in enumerate(output):
            if character != "{":
                continue
            candidate = self._extract_balanced(output, start, "{", "}")
            if candidate is None:
                continue
            try:
                value = ast.literal_eval(candidate)
            except (SyntaxError, ValueError):
                continue
            if isinstance(value, dict) and "riddle" in value:
                result = value
        return result

    @dynamic_test(time_limit=0)
    def test_stage_one_output(self):
        try:
            output = TestedProgram().start()
        except Exception as error:
            return CheckResult.wrong(
                f"Could not start the stage-one program: {error}"
            )

        graph_match = re.search(
            r"^\s*Graph\s*\(\s*nodes\s*=.*$", output, re.MULTILINE
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
            r"\bedges\s*=\s*\[(?P<edges>.*)\]\s*\)\s*$", graph_output
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
                "The compiled graph must contain exactly these nodes: "
                "__start__, generate_riddle, display_riddle, and __end__."
            )

        edges_output = edges_match.group("edges")
        edge_pairs = re.findall(
            r"\bEdge\s*\(\s*source\s*=\s*['\"]([^'\"]+)['\"]\s*,\s*"
            r"target\s*=\s*['\"]([^'\"]+)['\"]",
            edges_output,
        )
        conditional_values = re.findall(
            r"\bconditional\s*=\s*(True|False)", edges_output
        )

        if edge_pairs != self.expected_edges:
            return CheckResult.wrong(
                "The compiled graph must use the linear connections "
                "__start__ -> generate_riddle -> display_riddle -> __end__."
            )

        if len(conditional_values) != len(self.expected_edges) or any(
            value != "False" for value in conditional_values
        ):
            return CheckResult.wrong(
                "All three graph connections must be unconditional (conditional=False)."
            )

        result = self._find_result(output)
        if result is None:
            return CheckResult.wrong(
                "Could not find the final graph state. Ensure you print the result "
                "returned by graph.invoke({})."
            )

        riddle = result["riddle"]
        if not hasattr(riddle, "keys"):
            return CheckResult.wrong(
                "The final graph state does not contain the generated riddle fields. "
                "Return the generated riddle from generate_riddle using model_dump()."
            )

        expected_fields = {
            "question",
            "answer",
            "hints",
            "category",
            "difficulty",
        }
        missing_fields = expected_fields - set(riddle)
        if missing_fields:
            return CheckResult.wrong(
                "The generated riddle must include question, answer, three hints, "
                "category, and difficulty."
            )

        for field in ("question", "answer"):
            value = riddle[field]
            if value is None or not str(value).strip():
                return CheckResult.wrong(
                    f"The generated riddle must include a non-empty {field}."
                )

        hints = riddle["hints"]
        try:
            hint_values = list(hints)
        except TypeError:
            hint_values = []
        if len(hint_values) != 3:
            return CheckResult.wrong(
                "Generate exactly three distinct, non-empty hints for the riddle."
            )
        normalized_hints = [
            "" if hint is None else str(hint).strip() for hint in hint_values
        ]
        if any(not hint for hint in normalized_hints):
            return CheckResult.wrong(
                "Generate exactly three distinct, non-empty hints for the riddle."
            )
        if len(set(normalized_hints)) != 3:
            return CheckResult.wrong(
                "Generate exactly three distinct, non-empty hints for the riddle."
            )

        if str(riddle["category"]).strip().lower() != "general":
            return CheckResult.wrong(
                "Set the stage-one riddle category to the default value 'general'."
            )
        if str(riddle["difficulty"]).strip().lower() != "easy":
            return CheckResult.wrong(
                "Set the stage-one riddle difficulty to the default value 'easy'."
            )

        return CheckResult.correct()