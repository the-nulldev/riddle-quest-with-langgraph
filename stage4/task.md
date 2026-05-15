## Stage Four — Store user preferences

### About

Collect user preferences and use them to generate a riddle.

### Description

The vault can now run a complete riddle game, but every challenge still uses the same default settings. Some players prefer logic puzzles, while others enjoy nature and geography. Some want a relaxed game; others want a difficult challenge.

Collect player preferences and store them in an `InMemoryStore` (or any other store you prefer). This happens in a new `user_preferences` node. The application should remember the player’s preferred category and difficulty across separate graph threads. When the game starts, prompt the player for their ID and ask them to choose:

- A category;
- A difficulty;

Save both choices in the store under the player’s ID. Generate the riddle using the selected preferences and update the active graph state. When the same player starts another quest, load the saved preferences from the store. Let the player use these saved preferences or replace them with new values.

If you use an `InMemoryStore`, saved preferences remain available only while the application is running.

Here’s a visual representation of the graph at this point:

!Group 59.png

### Objectives

In this stage, you should:

- Compile the graph with an `InMemoryStore` to store user preferences. You can also use a database-backed store, but this is not required.
- Each player should be identified with a player ID. `interrupt()` the `user_preferences` node to collect the player ID.
- If no preferences are stored under this player ID, collect them with `input()` or `interrupt()` if preferred.
- Use the player ID to create a namespace for preferences and store them there. For the key, use `user_preferences`.
- Accept only `nature`, `geography`, `object`, and `logic` categories.
- Support these difficulty levels: `easy`, `medium`, and `hard`.
- Ensure that the submitted preferences are valid before saving them.
- When the same player ID is entered in a new quest, load existing preferences.
- Allows the player to keep or change their stored preferences.
- If the user chooses to change preferences, replace the stored values and use the active ones for riddle generation.
- The graph execution should work as before.

Do not save preferences until both values are valid.

As before, print the compiled graph and the state history to validate your solution.

### Examples

The greater-than symbol followed by a space (`>` ) represents user input. It is not part of the input.

*Example 1: A new player*

```bash
Graph(nodes={'__start__': Node(id='__start__', name='__start__'...

Welcome to the vault. 
Quest thread: quest-17baab5b-35fe-4cd2-90cf-b3758fd21b83

Please enter your ID: 
> mr-robot

No saved/valid preferences were found. 

Please choose a category: ['nature', 'geography', 'object', 'logic'] 
> nature
Please choose a difficulty: ['easy', 'medium', 'hard'] 
> medium

Generating a [medium] level [nature] challenge...

Category: Nature
Difficulty: Medium

I drink sunlight and turn it into sweets...

...
[StateSnapshot(values={'riddle': {'question': 'I have ...
```

*Example 2: Invalid values*

```python
...
Please choose a category: ['nature', 'geography', 'object', 'logic'] 
> history

Please choose a difficulty: ['easy', 'medium', 'hard'] 
> impossible

Invalid category or difficulty. Please try again.  

Please choose a category: ['nature', 'geography', 'object', 'logic']  
> geography

Please choose a difficulty: ['easy', 'medium', 'hard'] 
> hard

Your preferences have been saved. 

Generating a [hard] level [geography] challenge...

...
[StateSnapshot(values={'riddle': {'question': 'I have ...
```

*Example 3: Using saved preferences in another thread — while the checkpoint (thread) is different, the stored preferences persist.*

```python
...
Welcome to the vault. 
Quest thread: quest-8d183ac6-34f5-421e-8c4d-bb229b31b221
Please enter your ID: 
> mr-robot
...

Correct! You opened the vault.
Start another quest? (y/n) 
> yes

Quest thread: quest-127530e4-5c2f-487b-8b1d-7afb2e0cafe5 # a new checkpoint ID
Please enter your ID: 
> mr-robot

Saved preferences: 

Category: Geography
Difficulty: Hard

Would you like to change these preferences? (y/N) 
> no

Using saved preferences...

Generating a [hard] level [geography] challenge...
```

*Example 4: Changing preferences*

```python
...
Start another quest? (y/n) 
> yes

Quest thread: quest-f50e0b5c-3381-48ec-9265-3bb5e937ef79
Please enter your ID: 
> mr-robot

Saved preferences: 

Category: Geography
Difficulty: Hard

Would you like to change these preferences? (y/N) 
> yes

Please choose a category: general, wordplay, object, or logic. 
> logic

Please choose a difficulty: easy, medium, or hard. 
> easy

Your preferences have been updated. 

Generating an [easy] level [logic] challenge...
```