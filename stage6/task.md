## Stage Six — Replay a previous vault

### About

Use checkpoint history to attempt the unchosen vault without generating the riddles again.

### Description

In the previous topic, you used time travel to continue a graph from an earlier checkpoint. This stage applies the same idea to the two generated vaults. The first playthrough remains in history, while a fork starts from the moment just before its gameplay began.

After the first playthrough ends in victory or defeat, the player should see:

```text
1. Finish this quest
2. Attempt the other vault
```

Keep asking until the player enters a valid option. The other vault may be attempted only once during a quest.

If the player chooses the other vault, call `get_state_history()` and find the snapshot taken after vault selection but before gameplay. Identify it from its state and next node rather than a fixed history index. It should:

- have `("display_riddle",)` as its next node;
- contain both records in `riddles` and the original `selected_vault`;
- have no guesses, have `next_hint` set to `0`, and have no result.

The record with a different `vault_number` is the unplayed vault. Update only `selected_vault`; `update_state()` creates a checkpoint for the new branch and leaves the completed path intact:

```python
other_vault = next(
    riddle for riddle in snapshot.values["riddles"]
    if riddle["vault_number"] != snapshot.values["selected_vault"]
)

fork_config = graph.update_state(
    snapshot.config,
    values={"selected_vault": other_vault["vault_number"]},
)
fork_checkpoint_id = fork_config["configurable"]["checkpoint_id"]

result = graph.invoke(None, config=fork_config)
```

Here, `thread_id` groups the quest's checkpoints, `checkpoint_ns` identifies the graph's checkpointing scope within that thread, and `checkpoint_id` selects one exact checkpoint. The top-level graph normally uses an empty checkpoint namespace. This is separate from an `InMemoryStore` namespace, which organizes long-term memories.

Because `fork_config` includes `fork_checkpoint_id`, use it only for the first invocation. That invocation advances the branch to a newer checkpoint. For later guesses, omit `checkpoint_id` so LangGraph resumes from the latest checkpoint in the same thread and scope:

```python
runtime_config = {
    "configurable": {
        "thread_id": fork_config["configurable"]["thread_id"],
        "checkpoint_ns": fork_config["configurable"].get(
            "checkpoint_ns", ""
        ),
    }
}
```

Use `runtime_config` for every later `Command(resume=...)`. Reusing the pinned `fork_config` can restart the branch and repeat the riddle or Hint 1.

Gameplay nodes should resolve the active record from `riddles` and `selected_vault`; a separate active-riddle copy can become stale after the fork. Reuse the generated riddles, and give only an entirely new quest a new `thread_id`. Stored preferences remain available through the shared store.

### Objectives

In this stage, you should:

- Preserve the preference, generation, selection, and four-attempt flows.
- Offer a validated, one-time choice to attempt the other vault.
- Retrieve history only on replay and find the clean pre-gameplay snapshot from its state and next node.
- Select the other record by `vault_number` and update only `selected_vault`.
- Start with the pinned `fork_config`, then resume guesses with its unpinned thread and namespace.
- Resolve gameplay from `riddles` and `selected_vault` without calling the model again.
- Preserve the original path, and use a new `thread_id` only for a new quest.

### Examples

The greater-than symbol followed by a space (`> `) represents user input. It is not part of the entered value. Generated vault titles and riddles may differ.

*Example 1: Attempting the other vault*

```bash
Correct! You opened the vault.

1. Finish this quest
2. Attempt the other vault

Choose an option:
> 2

Entering The Moonlit Archive...

Category: General
Difficulty: Hard

The more you remove from me, the larger I become. What am I?

Enter your guess:
> a hole

Correct! You opened the vault.
```

*Example 2: Advancing hints in the fork*

```bash
Enter your guess:
> a map

Incorrect.
Hint 1: You may find me attached to an envelope.

Enter your guess:
> a label

Incorrect.
Hint 2: I usually show that postage has been paid.
```

The second guess must continue from the latest fork checkpoint. It must not display the riddle again or repeat Hint 1.