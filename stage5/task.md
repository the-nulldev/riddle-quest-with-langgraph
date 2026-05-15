## Stage Five — Choose your vault

### About

One vault is no longer enough. Generate multiple vaults concurrently and let the player decide which challenge to enter.

### Description

The vault now remembers each player’s preferred category and difficulty, but every quest still presents only one riddle. Give the player a choice by preparing two vaults:

1. Vault 1 uses the player's preferred category and difficulty.
2. Vault 2 uses the general category and the same preferred difficulty.

Use LangGraph’s `Send` API to fan out the work so that each vault can be generated independently. `Send` takes the name of a node and the state to pass to that invocation. For example:

```python
from langgraph.types import Send

def create_tasks(state):
    worker_states = [
        {
            "item": state["preferred_item"],
            "slot_number": 1,
        },
        {
            "item": "general",
            "slot_number": 2,
        },
    ]

    return [Send("worker", worker_state) for worker_state in worker_states]
```

The main graph state should carry everything needed across the full quest. Keep the existing fields for the player’s `category` and `difficulty`, submitted `guesses`, the next hint index, and the final result. Add:

- `riddles`: a list containing all generated riddles, annotated with an append reducer.
- `riddle`: the riddle selected by the player and used by the rest of the game;
- `selected_vault`: the number of the selected vault.

Define a separate worker state containing only `category`, `difficulty`, and `vault_number`. We’ll also need a title for each vault; therefore, add `title` to the `Riddle` model and instruct the LLM to generate it:

```bash
# ... previous requirements
- Give the vault a short, atmospheric title.
```

Once a worker receives its structured result, dump it to a dictionary and attach the riddle’s metadata: `category`, `difficulty`, and `vault_number`. You can do it as follows:

```bash
  # riddle = model.invoke...
  
riddle_data = riddle.model_dump()
riddle_data.update(
    {
        "category": category,
        "difficulty": difficulty,
        "vault_number": state["vault_number"],
    }
)
  
 return {"riddles": [riddle_data]}
```

Parallel completion order is not guaranteed, so sort or look up records by `vault_number` rather than relying on list position.

Once both vaults are ready, show the available choices and ask the player which vault they want to enter. Display enough information to distinguish them without revealing their answers. After a valid selection, run the full pipeline as before to solve the riddle.

### Objectives

For this stage, you should:

- Use `Send` to generate two vaults simultaneously.
- Generate one vault using the player’s preferred category and one using the `general` category.
- Use the player’s selected difficulty for both vaults.
- Each generated riddle should have a short `title` and a `vault_number` (1 or 2).
- Collect all generated riddles in the graph state. Use a reducer so results returned by separate workers are combined safely. Ensure you attach a riddle’s metadata (`category`, `difficulty`, and `vault_number`) after generation.
- Show the number, title, category, difficulty, and a short preview for each vault for the user to choose.
- `interrupt()` the graph to collect the player’s selection. You can also use `input()`.
- Accept only an available vault number. If the selection is invalid, ask again.
- Store the selected riddle in the state and continue with the guess, hint, victory, and defeat flows from the previous stages.
- Saved user preferences should keep working across separate graph threads.

Do not reveal the answer or hints while presenting the vault choices.

Remember to print the compiled graph via `.get_graph()` as well as the full state history at the very end of execution.

### Examples

The greater-than symbol followed by a space (`>` ) represents user input. It is not part of the input.

*Example 1: Choosing between generated vaults*

```bash
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

...
Please enter your ID:
> mr-robot

Saved preferences:
Category: Nature
Difficulty: Medium

Would you like to change these preferences? (y/N)
> no

Preparing two vaults...

Choose a vault:

1. The Whispering Canopy — Nature, Medium
   I drink sunlight and turn it into sweets...

2. The Silent Chamber — General, Medium
   I follow you all day but disappear at night...

Select a vault:
> 1

Entering The Whispering Canopy...

Category: Object
Difficulty: Easy

I have keys but open no locks....

...
[StateSnapshot(values={'riddles': [{'title': 'Vault of Silent Keys', 'question': 'I have keys but...
```

*Example 2: Invalid vault selection*

```bash
Select a vault:
> 3

Please choose one of the available vaults.

Select a vault:
> two

Please choose one of the available vaults.

Select a vault:
> 2

Entering The Silent Chamber...
```