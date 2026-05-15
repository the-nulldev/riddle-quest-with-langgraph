import uuid

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import TypedDict, NotRequired
from typing import Annotated
import operator
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

load_dotenv()

class Riddle(BaseModel):
    """A structured challenge presented to the player."""

    question: str = Field(description="The riddle question.")
    answer: str = Field(description="The answer to the riddle.")
    hints: list[str] = Field(
        min_length=3,
        max_length=3,
        description="Exactly three helpful hints, ordered from subtle to revealing."
    )

    category: SkipJsonSchema[str] = ""
    difficulty: SkipJsonSchema[str] = ""


model = init_chat_model("gpt-5.4-mini").with_structured_output(Riddle)

CATEGORIES = ("nature", "geography", "logic", "object")
DIFFICULTIES =  ("easy", "medium", "hard")

class GraphState(TypedDict):
    riddle: NotRequired[dict[str, object]]
    guesses: Annotated[list[str], operator.add]
    preferred_category: NotRequired[str]
    preferred_difficulty: NotRequired[str]
    next_hint: int


def user_preferences_node(state: GraphState, runtime: Runtime) -> GraphState:
    user_id = interrupt("Please enter your ID: ")
    preferences_namespace = (user_id, 'hyper-user')
    preferences_key = "user_preferences"

    stored_preferences = runtime.store.get(preferences_namespace, preferences_key)

    if stored_preferences is None:
        print("No saved/valid preferences were found. \n")
        while True:
            category = interrupt("Please choose a category: ['nature', 'geography', 'object', 'logic'] \n>").strip().casefold()
            difficulty = interrupt("Please choose a difficulty: ['easy', 'medium', 'hard'] \n>").strip().casefold()

            if category in CATEGORIES and difficulty in DIFFICULTIES:
                break
            else:
                print("Invalid category or difficulty. Please try again. \n")
                Command(goto="user_preferences")

        runtime.store.put(
            namespace=preferences_namespace,
            key=preferences_key,
            value={
                "preferred_category": category,
                "preferred_difficulty": difficulty
            }
        )

        print("\nYour preferences have been saved. \n")

        return {
            "preferred_category": category,
            "preferred_difficulty": difficulty
        }

    saved_category = str(stored_preferences.value.get("preferred_category", "")).casefold()
    saved_difficulty = str(stored_preferences.value["preferred_difficulty"].casefold())

    print(
        "Saved preferences: \n"
        f"Category: {saved_category.title()}\n"
        f"Difficulty: {saved_difficulty.title()}\n\n"
    )

    decision = interrupt(f"Would you like to change these preferences? (y/N) ")

    if decision.lower() in {"y", "yes"}:
        category_upd = interrupt("Please choose a category: ['nature', 'geography', 'object', 'logic'] ")
        difficulty_upd = interrupt("Please choose a difficulty: ['easy', 'medium', 'hard'] ")

        runtime.store.put(
            namespace=preferences_namespace,
            key=preferences_key,
            value={
                "preferred_category": category_upd,
                "preferred_difficulty": difficulty_upd
            }
        )

        print("\nYour preferences have been updated. \n")

        return {
            "preferred_category": category_upd,
            "preferred_difficulty": difficulty_upd
        }


    return {
        "preferred_category": saved_category,
        "preferred_difficulty": saved_difficulty
    }


def generate_riddle_node(state: GraphState) -> GraphState:
    """Generate a riddle."""

    category = state["preferred_category"]
    difficulty = state["preferred_difficulty"]

    print(f"Generating a [{difficulty}] level [{category}] challenge...\n")

    generated_riddle = model.invoke(
        f"""
          Create a riddle that meets the following requirements:
          - The riddle must be a {category} category riddle.
          - The difficulty level must be {difficulty}.
          - Include exactly three distinct hints.
          - The question must contain all text needed to present the riddle.
          - Do not put the category, difficulty, answer, or hints inside the question.
          - Opt for concise-answer riddles rather than lengthy narratives. 

        """
    )

    riddle = generated_riddle.model_copy(
        update={
            "category": category,
            "difficulty": difficulty
        }
    )

    return {"riddle": riddle.model_dump()}


def display_riddle_node(state: GraphState) -> GraphState:
    """Display the riddle and pause for the initial guess."""
    riddle = Riddle.model_validate(state["riddle"])

    print(f"Category: {riddle.category.title()}")
    print(f"Difficulty: {riddle.difficulty.title()}\n")
    print(riddle.question)
    print()

    guess = interrupt("Enter your guess: ")

    return {"guesses": [guess]}


def normalize_answer(value: str) -> str:
    """Normalize capitalization, surrounding whitespace, and leading articles."""
    normalized = " ".join(value.casefold().split())

    for article in ("a ", "an ", "the "):
        if normalized.startswith(article):
            return normalized[len(article):]
    return normalized


def route_guess(state: GraphState) -> str:
    """Route the latest guess to victory, a hint, or defeat."""
    riddle = Riddle.model_validate(state["riddle"])
    latest_guess = state["guesses"][-1]

    if normalize_answer(latest_guess) == normalize_answer(riddle.answer):
        return "victory"

    if len(state["guesses"]) < 4:
        return "reveal_hint"

    return "defeat"


def reveal_hint_node(state: GraphState) -> GraphState:
    """Reveal the next unused hint and pause for another guess."""
    riddle = Riddle.model_validate(state["riddle"])
    hint_index = state["next_hint"]

    print("Incorrect.")
    print()
    print(f"Hint {hint_index + 1}: {riddle.hints[hint_index]}")
    print()

    guess = interrupt("Enter your guess: ")

    return {
        "guesses": [guess],
        "next_hint": hint_index + 1,
    }


def victory_node(state: GraphState) -> GraphState:
    """Announce that the latest guess was correct."""
    print("Correct! You opened the vault.")

    return {}


def defeat_node(state: GraphState) -> GraphState:
    """Reveal the answer after all four guesses are incorrect."""
    riddle = Riddle.model_validate(state["riddle"])

    print("Incorrect. You have no attempts remaining.")
    print(f"The answer was: {riddle.answer}.")

    return {}



builder = StateGraph(GraphState)
builder.add_node("user_preferences", user_preferences_node)
builder.add_node("generate_riddle", generate_riddle_node)
builder.add_node("display_riddle", display_riddle_node)
builder.add_node("reveal_hint", reveal_hint_node)
builder.add_node("victory", victory_node)
builder.add_node("defeat", defeat_node)

builder.add_edge(START, "user_preferences")
builder.add_edge("user_preferences", "generate_riddle")
builder.add_edge("generate_riddle", "display_riddle")
builder.add_conditional_edges("display_riddle", route_guess)
builder.add_conditional_edges("reveal_hint", route_guess)
builder.add_edge("victory", END)
builder.add_edge("defeat", END)

checkpointer = InMemorySaver()
store = InMemoryStore()
graph = builder.compile(checkpointer=checkpointer, store=store)
print(graph.get_graph())


if __name__ == "__main__":

    while True:
        thread_id = f"quest-{uuid.uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}

        print(f"\nQuest thread: {thread_id}")
        result = graph.invoke(
            {"guesses": [], "next_hint": 0},
            config=config,
        )

        while result.get("__interrupt__"):
            guess = input("Enter your guess:\n> ")
            result = graph.invoke(Command(resume=guess), config=config)

        again = input("\n Another quest? (y/n) ").strip().lower()

        if again not in {"y", "yes"}:
            break

    print(list(graph.get_state_history(config)))


