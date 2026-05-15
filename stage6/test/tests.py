import ast
import re

from hstest import CheckResult, StageTest, TestedProgram, dynamic_test


class SemanticLangGraphTest(StageTest):
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
    first_user = "stage-six-player-7c1d9e"
    first_preferences = ("nature", "medium")
    first_guesses = (
        "stage-six-first-wrong-1-7c1d9e",
        "stage-six-first-wrong-2-7c1d9e",
        "stage-six-first-wrong-3-7c1d9e",
        "stage-six-first-wrong-4-7c1d9e",
    )
    second_guesses = (
        "stage-six-second-wrong-1-7c1d9e",
        "stage-six-second-wrong-2-7c1d9e",
        "stage-six-second-wrong-3-7c1d9e",
        "stage-six-second-wrong-4-7c1d9e",
    )
    history_guidance = (
        "Could not read a printed checkpoint history. Print "
        "list(graph.get_state_history(config=...)) so the grader can inspect "
        "the StateSnapshot values and checkpoint lineage."
    )
    graph_guidance = (
        "Could not read the compiled graph. Print the compiled graph, for example "
        "with print(graph.get_graph())."
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

    @staticmethod
    def _top_level_fields(group):
        if len(group) < 2 or group[0] != "(" or group[-1] != ")":
            return None

        pairs = {"(": ")", "[": "]", "{": "}"}
        closing = set(pairs.values())
        stack = []
        quote = None
        escaped = False
        start = 1
        parts = []

        for index in range(1, len(group) - 1):
            character = group[index]
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
            elif character in pairs:
                stack.append(pairs[character])
            elif character in closing:
                if not stack or stack.pop() != character:
                    return None
            elif character == "," and not stack:
                parts.append(group[start:index])
                start = index + 1

        if quote is not None or stack:
            return None
        parts.append(group[start:-1])

        fields = {}
        for part in parts:
            match = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(.*?)\s*$", part, re.DOTALL)
            if match is None or match.group(1) in fields:
                return None
            fields[match.group(1)] = match.group(2)
        return fields

    def _graph_error(self, output):
        parsed_nodes = []
        for marker in re.finditer(r"\bGraph\s*\(", output):
            start = output.find("(", marker.start())
            graph_output = self._extract_balanced(output, start, "(", ")")
            if graph_output is None:
                continue

            node_matches = re.findall(
                r"\bNode\s*\(\s*id\s*=\s*(['\"])(.*?)\1",
                graph_output,
                re.DOTALL,
            )
            if not node_matches:
                continue
            nodes = {node_id for _, node_id in node_matches}
            if nodes == self.expected_nodes:
                return None
            parsed_nodes.append(nodes)

        if not parsed_nodes:
            return self.graph_guidance

        nodes = parsed_nodes[0]
        missing = sorted(self.expected_nodes - nodes)
        extra = sorted(nodes - self.expected_nodes)
        return (
            "graph_shape: The compiled graph has the wrong node set. "
            f"Missing: {missing}; extra: {extra}."
        )

    @classmethod
    def _task_names(cls, tasks_output):
        names = []
        position = 0
        while True:
            marker = re.search(r"\bPregelTask\s*\(", tasks_output[position:])
            if marker is None:
                break
            marker_start = position + marker.start()
            task_start = tasks_output.find("(", marker_start)
            task = cls._extract_balanced(tasks_output, task_start, "(", ")")
            if task is None:
                break
            fields = cls._top_level_fields(task)
            if fields is not None and "name" in fields:
                try:
                    name = ast.literal_eval(fields["name"])
                except (SyntaxError, ValueError):
                    name = None
                if name is not None:
                    names.append(name)
            position = task_start + len(task)
        return names

    @classmethod
    def _parse_snapshot(cls, snapshot):
        fields = cls._top_level_fields(snapshot)
        if fields is None:
            return None

        required = {"values", "next", "config", "metadata", "parent_config"}
        if not required.issubset(fields):
            return None

        try:
            values = ast.literal_eval(fields["values"])
            next_nodes = ast.literal_eval(fields["next"])
            config = ast.literal_eval(fields["config"])
            metadata = ast.literal_eval(fields["metadata"])
            parent_config = ast.literal_eval(fields["parent_config"])
        except (SyntaxError, ValueError):
            return None

        if not isinstance(values, dict):
            return None
        if not isinstance(next_nodes, (list, tuple)):
            return None
        if not isinstance(config, dict) or not isinstance(metadata, dict):
            return None
        if parent_config is not None and not isinstance(parent_config, dict):
            return None

        tasks_output = fields.get("tasks", "")
        interrupts_output = fields.get("interrupts", "")
        return {
            "raw": snapshot,
            "values": values,
            "next": tuple(next_nodes),
            "config": config,
            "metadata": metadata,
            "parent_config": parent_config,
            "task_names": cls._task_names(tasks_output),
            "has_interrupt": re.search(
                r"\bInterrupt\s*\(",
                tasks_output + interrupts_output,
            ) is not None,
        }

    @classmethod
    def _parse_history(cls, history_output):
        records = []
        position = 0
        while True:
            marker = re.search(r"\bStateSnapshot\s*\(", history_output[position:])
            if marker is None:
                break
            marker_start = position + marker.start()
            snapshot_start = history_output.find("(", marker_start)
            snapshot = cls._extract_balanced(
                history_output,
                snapshot_start,
                "(",
                ")",
            )
            if snapshot is None:
                return None
            record = cls._parse_snapshot(snapshot)
            if record is None:
                return None
            records.append(record)
            position = snapshot_start + len(snapshot)
        return records or None

    @classmethod
    def _history_candidates(cls, output):
        candidates = []
        position = 0
        while True:
            marker = re.search(
                r"\[\s*StateSnapshot\s*\(",
                output[position:],
                re.DOTALL,
            )
            if marker is None:
                break
            history_start = position + marker.start()
            history_output = cls._extract_balanced(
                output,
                history_start,
                "[",
                "]",
            )
            if history_output is None:
                position = history_start + 1
                continue
            records = cls._parse_history(history_output)
            if records is not None:
                candidates.append(records)
            position = history_start + len(history_output)
        return candidates

    @staticmethod
    def _execute(main, value, context):
        try:
            return main.execute(value), None
        except BaseException as error:
            return None, f"Could not {context}: {error}"

    @staticmethod
    def _checkpoint_ref(config):
        if not isinstance(config, dict):
            return None
        configurable = config.get("configurable")
        if not isinstance(configurable, dict):
            return None
        if "thread_id" not in configurable or "checkpoint_id" not in configurable:
            return None
        thread_id = configurable["thread_id"]
        checkpoint_id = configurable["checkpoint_id"]
        if thread_id is None or checkpoint_id is None or checkpoint_id == "":
            return None
        return (
            thread_id,
            configurable.get("checkpoint_ns", ""),
            checkpoint_id,
        )

    @staticmethod
    def _ref_key(reference):
        if reference is None:
            return None
        return tuple(repr(part) for part in reference)

    @classmethod
    def _record_index(cls, records):
        index = {}
        thread_id = None
        for record in records:
            reference = cls._checkpoint_ref(record["config"])
            if reference is None:
                return None, None, (
                    "Every StateSnapshot config must include "
                    "thread_id and checkpoint_id."
                )
            if thread_id is None:
                thread_id = reference[0]
            elif reference[0] != thread_id:
                return None, None, (
                    "Every checkpoint in a quest must use the same thread."
                )

            key = cls._ref_key(reference)
            if key in index:
                return None, None, (
                    "Checkpoint IDs must uniquely identify snapshots."
                )
            index[key] = record
        return index, thread_id, None

    @classmethod
    def _parent_record(cls, record, index):
        parent_reference = cls._checkpoint_ref(record["parent_config"])
        return index.get(cls._ref_key(parent_reference))

    @staticmethod
    def _as_sequence(value):
        if isinstance(value, (list, tuple)):
            return list(value)
        return None

    @staticmethod
    def _same_vault(first, second):
        if first == second:
            return True
        return str(first).strip().casefold() == str(second).strip().casefold()

    @classmethod
    def _riddles_by_number(cls, values):
        riddles = cls._as_sequence(values.get("riddles"))
        if riddles is None or len(riddles) != 2:
            return None

        by_number = {}
        for riddle in riddles:
            if not isinstance(riddle, dict) or "vault_number" not in riddle:
                return None
            number = riddle["vault_number"]
            normalized = str(number).strip().casefold()
            if not normalized or normalized in by_number:
                return None
            by_number[normalized] = riddle

        if not all(
                any(cls._same_vault(riddle["vault_number"], expected) for riddle in riddles)
                for expected in (1, 2)
        ):
            return None
        return by_number

    @classmethod
    def _is_clean_snapshot(cls, record):
        values = record["values"]
        guesses = cls._as_sequence(values.get("guesses"))
        return (
            record["next"] == ("display_riddle",)
            and cls._riddles_by_number(values) is not None
            and "selected_vault" in values
            and guesses == []
            and values.get("next_hint") == 0
            and "result" not in values
        )

    @classmethod
    def _selected_matches(cls, values, selected_vault):
        return (
            "selected_vault" in values
            and cls._same_vault(values["selected_vault"], selected_vault)
        )

    @classmethod
    def _progress_matches(
            cls,
            record,
            selected_vault,
            riddles,
            guesses,
            next_hint,
            next_node,
    ):
        values = record["values"]
        return (
            cls._selected_matches(values, selected_vault)
            and values.get("riddles") == riddles
            and cls._as_sequence(values.get("guesses")) == list(guesses)
            and values.get("next_hint") == next_hint
            and record["next"] == (next_node,)
            and "result" not in values
        )

    @classmethod
    def _children(cls, records, parent):
        parent_reference = cls._checkpoint_ref(parent["config"])
        return [
            record
            for record in records
            if cls._checkpoint_ref(record["parent_config"]) == parent_reference
        ]

    @classmethod
    def _branch_path(
            cls,
            records,
            start,
            selected_vault,
            riddles,
            guesses,
            branch_name,
    ):
        if not start["has_interrupt"]:
            return None, (
                f"gameplay_loop: The {branch_name} branch clean display_riddle "
                "checkpoint must contain an interrupt."
            )

        path = [start]
        current = start
        for attempt in range(1, 5):
            prefix = guesses[:attempt]
            next_hint = min(attempt - 1, 3)
            next_node = "reveal_hint" if attempt < 4 else "defeat"
            matches = [
                child
                for child in cls._children(records, current)
                if cls._progress_matches(
                    child,
                    selected_vault,
                    riddles,
                    prefix,
                    next_hint,
                    next_node,
                )
            ]
            if len(matches) != 1:
                return None, (
                    f"gameplay_loop: The {branch_name} branch must accumulate guess "
                    f"{attempt} on the latest checkpoint and advance hints in order."
                )
            current = matches[0]
            path.append(current)
            if attempt < 4 and not current["has_interrupt"]:
                return None, (
                    f"gameplay_loop: Guess checkpoint {attempt + 1} on the "
                    f"{branch_name} branch must contain an interrupt."
                )

        terminal_matches = []
        for child in cls._children(records, current):
            values = child["values"]
            if (
                    cls._selected_matches(values, selected_vault)
                    and values.get("riddles") == riddles
                    and cls._as_sequence(values.get("guesses")) == list(guesses)
                    and values.get("next_hint") == 3
                    and child["next"] == ()
                    and "result" in values
            ):
                terminal_matches.append(child)
        if len(terminal_matches) != 1:
            return None, (
                f"gameplay_loop: The {branch_name} branch must reach defeat after "
                "exactly four accumulated wrong guesses."
            )
        path.append(terminal_matches[0])
        return path, None

    @classmethod
    def _generation_error(cls, records, clean, index):
        choice = cls._parent_record(clean, index)
        if (
                choice is None
                or choice["next"] != ("choose_vault",)
                or not choice["has_interrupt"]
                or choice["values"].get("riddles") != clean["values"].get("riddles")
        ):
            return (
                "generation_selection: Two generated vaults must join at an "
                "interrupting choose_vault checkpoint before selection."
            )

        fanout = cls._parent_record(choice, index)
        if fanout is None:
            return "generation_selection: Could not trace vault selection to the fan-out."
        if (
                fanout["next"].count("generate_vault") != 2
                or len(fanout["next"]) != 2
                or fanout["task_names"].count("generate_vault") != 2
        ):
            return (
                "generation_selection: user_preferences must fan out to exactly two "
                "generate_vault tasks."
            )

        preferences = cls._parent_record(fanout, index)
        start = cls._parent_record(preferences, index) if preferences is not None else None
        if (
                preferences is None
                or preferences["next"] != ("user_preferences",)
                or start is None
                or start["next"] != ("__start__",)
        ):
            return (
                "graph_shape: Checkpoint lineage must run from __start__ through "
                "user_preferences into the two-vault fan-out."
            )

        generated_tasks = sum(
            record["task_names"].count("generate_vault")
            for record in records
        )
        if generated_tasks != 2:
            return (
                "no_regeneration: The quest history must contain only the two "
                "original generate_vault tasks."
            )
        return None

    @classmethod
    def _first_history_context(cls, records):
        index, thread_id, error = cls._record_index(records)
        if error is not None:
            return None, error

        clean_candidates = [
            record
            for record in records
            if cls._is_clean_snapshot(record)
            and cls._same_vault(record["values"]["selected_vault"], 1)
        ]
        if not clean_candidates:
            return None, (
                "history_lookup: Find the clean pre-game snapshot by next="
                "display_riddle, two riddles, empty guesses, next_hint 0, and no result."
            )

        branch_errors = []
        for clean in clean_candidates:
            riddles = clean["values"]["riddles"]
            generation_error = cls._generation_error(records, clean, index)
            if generation_error is not None:
                branch_errors.append(generation_error)
                continue
            branch, branch_error = cls._branch_path(
                records,
                clean,
                clean["values"]["selected_vault"],
                riddles,
                cls.first_guesses,
                "original vault",
            )
            if branch_error is not None:
                branch_errors.append(branch_error)
                continue
            return {
                "records": records,
                "index": index,
                "thread_id": thread_id,
                "clean": clean,
                "riddles": riddles,
                "selected_vault": clean["values"]["selected_vault"],
                "branch": branch,
            }, None

        return None, branch_errors[0]

    @classmethod
    def _preservation_error(cls, first_context, final_records, final_index):
        for original in first_context["records"]:
            reference = cls._checkpoint_ref(original["config"])
            preserved = final_index.get(cls._ref_key(reference))
            if preserved is None:
                return (
                    "path_preservation: The final history must retain every checkpoint "
                    "from the completed original branch."
                )
            if (
                    preserved["values"] != original["values"]
                    or preserved["next"] != original["next"]
                    or cls._checkpoint_ref(preserved["parent_config"])
                    != cls._checkpoint_ref(original["parent_config"])
                    or preserved["task_names"] != original["task_names"]
                    or preserved["has_interrupt"] != original["has_interrupt"]
            ):
                return (
                    "Original checkpoints must remain unchanged "
                    "after the fork."
                )
        return None

    @classmethod
    def _other_vault(cls, riddles, selected_vault):
        candidates = [
            riddle["vault_number"]
            for riddle in riddles
            if not cls._same_vault(riddle.get("vault_number"), selected_vault)
        ]
        return candidates[0] if len(candidates) == 1 else None

    @classmethod
    def _valid_update(cls, record, clean, other_vault, riddles):
        if str(record["metadata"].get("source", "")).casefold() != "update":
            return False
        if cls._checkpoint_ref(record["parent_config"]) != cls._checkpoint_ref(clean["config"]):
            return False
        if not cls._is_clean_snapshot(record):
            return False
        if not cls._same_vault(record["values"]["selected_vault"], other_vault):
            return False
        if record["values"].get("riddles") != riddles:
            return False

        original_values = dict(clean["values"])
        updated_values = dict(record["values"])
        original_values.pop("selected_vault", None)
        updated_values.pop("selected_vault", None)
        return original_values == updated_values

    @classmethod
    def _final_history_error(cls, records, first_context):
        index, thread_id, error = cls._record_index(records)
        if error is not None:
            return error
        if thread_id != first_context["thread_id"]:
            return "Attempting the other vault must reuse the quest thread."

        error = cls._preservation_error(first_context, records, index)
        if error is not None:
            return error

        generated_tasks = sum(
            record["task_names"].count("generate_vault")
            for record in records
        )
        if generated_tasks != 2:
            return (
                "Forking must reuse the two original riddles without "
                "running generate_vault again."
            )

        clean_reference = cls._checkpoint_ref(first_context["clean"]["config"])
        clean = index.get(cls._ref_key(clean_reference))
        riddles = first_context["riddles"]
        other_vault = cls._other_vault(riddles, first_context["selected_vault"])
        if clean is None or other_vault is None:
            return "The two stored vault records must identify the other vault."

        updates = [
            record
            for record in records
            if cls._valid_update(record, clean, other_vault, riddles)
        ]
        if not updates:
            return (
                "update_state must change only selected_vault and its "
                "parent checkpoint must be the original clean pre-game snapshot."
            )

        original_branch, error = cls._branch_path(
            records,
            clean,
            first_context["selected_vault"],
            riddles,
            cls.first_guesses,
            "preserved original vault",
        )
        if error is not None:
            return "path_preservation: " + error.split(": ", 1)[-1]

        branch_errors = []
        for update in updates:
            update_reference = cls._checkpoint_ref(update["config"])
            if (
                    update_reference[0] != clean_reference[0]
                    or update_reference[1] != clean_reference[1]
            ):
                branch_errors.append(
                    "The fork update must keep the clean checkpoint's "
                    "thread and checkpoint namespace."
                )
                continue
            branch, branch_error = cls._branch_path(
                records,
                update,
                other_vault,
                riddles,
                cls.second_guesses,
                "other vault",
            )
            if branch_error is None:
                for record in records:
                    values = record["values"]
                    if (
                            "selected_vault" in values
                            and values.get("riddles") != riddles
                    ):
                        return (
                            "The generated riddles must remain unchanged "
                            "through both branches."
                        )
                return None
            branch_errors.append(
                "Fork guesses and next_hint must progress on a single "
                "parent-linked branch; resume later guesses without checkpoint_id."
            )

        return branch_errors[0]

    @classmethod
    def _select_first_history(cls, output):
        candidates = cls._history_candidates(output)
        if not candidates:
            return None, cls.history_guidance
        errors = []
        for records in candidates:
            context, error = cls._first_history_context(records)
            if error is None:
                return context, None
            errors.append(error)
        return None, errors[0]

    @classmethod
    def _select_final_history(cls, output, first_context):
        candidates = cls._history_candidates(output)
        if not candidates:
            return cls.history_guidance
        errors = []
        for records in candidates:
            error = cls._final_history_error(records, first_context)
            if error is None:
                return None
            errors.append(error)
        return errors[0]

    @dynamic_test(time_limit=0)
    def test_stage_six_output(self):
        main = TestedProgram()
        try:
            startup_output = main.start()
        except Exception as error:
            return CheckResult.wrong(f"Could not start stage six: {error}")

        error = self._graph_error(startup_output)
        if error is not None:
            return CheckResult.wrong(error)

        category, difficulty = self.first_preferences
        scripted_inputs = (
            (self.first_user, "submit the player ID"),
            (category, "submit the category"),
            (difficulty, "submit the difficulty"),
            ("1", "select vault 1"),
            *((guess, f"submit original-vault guess {index}")
              for index, guess in enumerate(self.first_guesses, start=1)),
        )
        for value, context in scripted_inputs:
            _, error = self._execute(main, value, context)
            if error is not None:
                return CheckResult.wrong(error)

        fork_output, error = self._execute(main, "2", "choose the other vault")
        if error is not None:
            return CheckResult.wrong(error)
        first_context, error = self._select_first_history(fork_output)
        if error is not None:
            return CheckResult.wrong(error)

        for index, guess in enumerate(self.second_guesses, start=1):
            _, error = self._execute(
                main,
                guess,
                f"submit other-vault guess {index}",
            )
            if error is not None:
                return CheckResult.wrong(error)

        final_output, error = self._execute(main, "n", "finish the quest")
        if error is not None:
            return CheckResult.wrong(error)
        error = self._select_final_history(final_output, first_context)
        if error is not None:
            return CheckResult.wrong(error)
        return CheckResult.correct()


LangGraphTest = SemanticLangGraphTest
