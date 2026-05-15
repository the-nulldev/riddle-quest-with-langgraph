## Stage Three — Ask for a hint

### About

Add more attempts and reveal hints when the player submits an incorrect answer.

### Description

One guess is not always enough to solve a riddle. Let’s allow the user up to 4 attempts. After each guess, use conditional edges to determine the next step:

- If the guess is correct, the player wins.
- If the guess is incorrect and attempts remain, reveal the next hint.
- After revealing a hint, pause and ask for another guess.
- If no attempts remain, reveal the answer.
- After a win or loss, ask the user if they’d like to start another quest. Run the graph all over again while true.

A hint must never be displayed more than once.

Here’s a visual representation of the graph at this stage:

!Group 51 (1).png.png)

### Objectives

In this stage, your program should:

- Allow the player up to four total guesses:
    - One initial guess;
    - One additional guess after each of the three hints.
- Store submitted guesses in a reducer-backed list (`guesses` in the graph’s state) and track the next unused hint.
- Route a correct guess to the `victory` node.
- Route to a `reveal_hint` node to reveal one hint after each of the first three incorrect guesses. This node should also increment to the next hint.
- End immediately when the player guesses correctly.
- Route to a `defeat` node after the fourth incorrect guess.
- Allow users to start another quest after victory or defeat.

Do not reveal a hint after a correct guess. Do not ask for another guess once the player has used all available attempts.

As before, make sure to print the graph via `.get_graph()` as well as the state history.

### Examples

*Example 1: The player answers after one hint:*

```python
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

...
I speak without a mouth and hear without ears. I have no body, but I come alive with wind.

Enter your guess:
> A bird
Incorrect.

Hint 1: I repeat what you say.

Enter your guess:
> An echo
Correct! You opened the vault.

Start another quest? (y/n) 
> yes

Quest thread: quest-76119ccd-d659-4aa9-8045-0faeaa176980

Generating your challenge...

[StateSnapshot(values={'riddle': {'question': 'I have ...
```

*Example 2: All hints are used up:*

```python
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

...
I have hands but cannot hold anything.
I have a face but cannot smile.

Enter your guess:
> A statue
Incorrect.

Hint 1: I help you organize your day.

Enter your guess:
> A calendar
Incorrect.

Hint 2: I usually contain the numbers from 1 to 12.

Enter your guess:
> A compass
Incorrect.

Hint 3: I tell you the time.

Enter your guess:
> A watch
Incorrect. You have no attempts remaining.
The answer was: a clock.

...

[StateSnapshot(values={'riddle': {'question': 'I have ...
```

*Example 3: No further hints are displayed after victory*

```python
... 

Enter your guess:
> A keyboard
Correct! You opened the vault.

Start another quest? (y/n) 
> no
[StateSnapshot(values={'riddle': {'question': 'I have ...
```