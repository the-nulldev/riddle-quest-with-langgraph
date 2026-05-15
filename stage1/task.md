## Stage One — Generate a challenge

### About

Generate a structured riddle for the player to solve.

### Description

The vault needs a challenge before a player can begin their quest. In this first stage, your task is to build a linear graph that generates a riddle, stores it in graph state, and displays the question. Use a Pydantic model and enforce structured output for this:

- `question`: the complete riddle shown to the player;
- `answer`: a concise answer used later to judge guesses;
- `hints`: exactly three distinct, non-empty hints ordered from subtle to revealing.

For this stage, the player cannot choose a category or difficulty. Keep both fields in your Pydantic `Riddle` model, set `category` to `general` and `difficulty` to `easy` by default, and let the application supply those values instead of asking the language model to generate them.

Annotate these fields with Pydantic's `SkipJsonSchema`:

```python
category: SkipJsonSchema[str] = "general"
difficulty: SkipJsonSchema[str] = "easy"
```

`SkipJsonSchema` omits these fields from `Riddle.model_json_schema()`; it does not remove them from the `Riddle` model itself. LangChain uses that reduced JSON Schema for structured output, so the language model generates only the riddle content. After validation, Pydantic applies the defaults defined in your code, and the resulting `Riddle` object still includes `category` and `difficulty`.

You can use the following prompt for the model:

```markdown
  Create a riddle that meets the following requirements:
  - The riddle must be a "general" category riddle.
  - The difficulty level must be "easy".
  - Include exactly three distinct hints.
  - The question must contain all text needed to present the riddle.
  - Do not put the category, difficulty, answer, or hints inside the question.
  - Opt for concise-answer riddles rather than lengthy narratives. 
```

In the graph’s state, we need to track the riddle, the category, and difficulty. Once a riddle is generated, display it and finish the program. The graph at this stage has a simple linear structure:

```python
START -> generate_riddle -> dsplay_riddle -> END
```

**Important:**

To validate your solution, ensure you print the following:

1. The compiled graph. You can display it as follows:

    ```python
    graph = builder.compile()
    print(graph.get_graph())
    
    # Expected output includes:
    Graph(nodes={'__start__': Node(id='__start__', name='__start__'...
    ```

2. The result after invoking the graph:

    ```python
    result = graph.invoke({})
    print(result)
    
    # Expected output includes:
    {'riddle': {'question': 'I can be opened, but...', 'category': 'general', 'difficulty': 'easy'}, ...}
    ```


### Objectives

Your objectives at this stage are to:

- Create a graph state object to hold the generated riddle. At this stage, it tracks the `riddle`, its `category`, and its `difficulty` level.
- Create a `generate_riddle` node to generate a structured riddle with the following fields:
    - `question`: `str`,
    - `answer`: `str`,
    - `hints`: `list[str]`, — exactly 3 hints,
    - `category`: `SkipJsonSchema[str]`, — defaults to `general`,
    - `difficulty`: `SkipJsonSchema[str]`, — defaults to `easy`.
- Ensure the model returns structured output matching your `Riddle` model. Use `.model_dump()` when returning the generated riddle so it is saved in the graph state as a dictionary.
- The `generate_riddle` node should also update the category hard-coded to `general` and difficulty set to `easy`.
- Create a `display_riddle` node to display the category, difficulty, and question after generation. Use `.model_validate()` when fetching the riddle for attribute access.
- Connect these nodes and build the graph.

Do not take user input yet. Also, do not display the answer or any hints yet. The player will use them in later stages.

### Examples

*Expected output:*

```python
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

Welcome to the vault. 
Generating your challenge...

Category: General
Difficulty: Easy

I have keys but no locks. I have space but no rooms. You can enter, but you cannot go outside. What am I?

{'riddle': {'question': 'I can be cracked, made, told, and played...', 'answer': 'A joke', 'hints': ['It is usually spoken or written...'], 'category': 'general', 'difficulty': 'easy'}, 'category': 'general', 'difficulty': 'easy'}
```