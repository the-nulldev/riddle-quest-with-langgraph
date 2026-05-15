## Stage Two — Guess the answer

### About

Pause the graph, resume it, and judge the player’s guess.

### Description

The vault has presented its challenge, but the player cannot answer it yet. In this stage, add a new `judge_guess` node to check the user’s guess. After displaying the riddle in the `display_riddle` node, call `interrupt()` to pause graph execution. This saves the current graph state in a checkpoint and returns control to the application. Read the player’s answer and resume the graph with `Command(resume=...)`. The graph should judge the guess and display whether they passed or failed.

Use the `uuid` library to generate a unique checkpoint ID for your checkpointer as follows:

```markdown
from uuid import uuid4

thread_id = f"quest-{uuid4()}"
```

Ignore articles (a, an, the), capitalization, and leading or trailing whitespace in an answer. For example, `A clock`, `Clock`,  `clock`, `the clock`, and `clock`   should be treated as the same guess.

Here’s a visual representation of the graph at this stage:

**Important**

To validate your solution, ensure you print the following:

1. The compiled graph. You can display it as follows:

    ```python
    graph = builder.compile()
    print(graph.get_graph())
    
    # Expected output includes:
    Graph(nodes={'__start__': Node(id='__start__', name='__start__'...
    ```

2. The entire graph history:

    ```python
    config = {"configurable": ...
    
    print(list(graph.get_state_history(config=config)))
    
    # Expected output includes:
    [StateSnapshot(values={'riddle': {'question': 'I have ...
    ```


### Objectives

In this stage, your program should:

- Add a new `guess` field in your graph state to track the player’s guess.
- Pause the graph with `interrupt()` at the `display_riddle` node and ask for a guess. You’ll resume the graph `Command(resume=...)` passing the user’s input. This node should return the player’s guess to update the graph state.
- Compare the guess with the riddle’s answer in the `judge_guess` node.
- End with a victory message for a correct guess.
- End with an incorrect message and the answer for an incorrect guess.

### Examples

*Example 1: The answer is correct*

```python
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

Welcome to the vault. 
Quest thread: quest-7eba59d7-e117-435b-a485-e1a6ecc347be

Generating your challenge...

Category: Object
Difficulty: Easy

I have hands but cannot hold anything. I have a face but cannot smile. What am I?

Enter your guess:
> A clock
Correct! You opened the vault.

[StateSnapshot(values={'riddle': {'question': 'I have ...
```

*Example 2: The answer is incorrect*

```python
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

Welcome to the vault. 
Quest thread: quest-7eba59d7-e117-435b-a485-e1a6ecc347be

Generating your challenge...

Category: Object
Difficulty: Easy

I have hands but cannot hold anything. I have a face but cannot smile. What am I?

Enter your guess:
> A mirror
Incorrect. The answer was: a clock.

[StateSnapshot(values={'riddle': {'question': 'I have ...
```

*Example 3: Capitalization and whitespace are ignored*

```python
...
Enter your guess:
>   CLOCK
Correct! You opened the vault.

[StateSnapshot(values={'riddle': {'question': 'I have ...
```