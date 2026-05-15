from uuid import uuid4

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict, NotRequired
from typing import Annotated
import operator
from langgraph.checkpoint.memory import InMemorySaver
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

class GraphState(TypedDict):
    riddle: NotRequired[dict[str, object]]
    guesses: Annotated[list[str], operator.add]
    next_hint: int


def generate_riddle_node(_: GraphState) -> GraphState:

    print("Generating your challenge...\n")

    generated_riddle = model.invoke(
        """
        Create a riddle. Requirements:
        - The riddle must be a "general" category riddle.
        - The difficulty level must be "easy".
        - Include exactly three distinct hints.
        - The question must contain all text needed to present the riddle.
        - Do not put the category, difficulty, answer, or hints inside the question.
        - Opt for concise-answer riddles rather than lengthy narratives. 
        """
    )

    riddle = generated_riddle.model_copy(
        update={
            "category": "general",
            "difficulty": "easy"
        }
    )

    return {"riddle": riddle.model_dump()}


def display_riddle_node(state: GraphState) -> GraphState:
    """Display the riddle and pause for the initial guess."""
    riddle = Riddle.model_validate(state["riddle"])

    print(f"Category: {riddle.category.title()} ")
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

    if normalize_answer(guess) == normalize_answer(riddle.answer):
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


def victory_node(_: GraphState) -> GraphState:
    """Announce that the latest guess was correct."""
    print("Correct! You opened the vault.")
    return {}


def defeat_node(state: GraphState) -> GraphState:
    """Reveal the answer after all four guesses are incorrect."""
    riddle = Riddle.model_validate(state["riddle"])

    print("Incorrect. You have no attempts left")
    print(f"The correct answer is: {riddle.answer}.")
    return {}


builder = StateGraph(GraphState)
builder.add_node("generate_riddle", generate_riddle_node)
builder.add_node("display_riddle", display_riddle_node)
builder.add_node("reveal_hint", reveal_hint_node)
builder.add_node("victory", victory_node)
builder.add_node("defeat", defeat_node)

builder.add_edge(START, "generate_riddle")
builder.add_edge("generate_riddle", "display_riddle")
builder.add_conditional_edges(
    "display_riddle",
    route_guess,
    {
        "victory": "victory",
        "reveal_hint": "reveal_hint",
        "defeat": "defeat",
    },
)

builder.add_conditional_edges(
    "reveal_hint",
    route_guess,
    {
        "victory": "victory",
        "reveal_hint": "reveal_hint",
        "defeat": "defeat"
    }
)
builder.add_edge("victory", END)
builder.add_edge("defeat", END)

checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
print(graph.get_graph())


if __name__ == "__main__":

    while True:
        thread_id = f"quest-{uuid4()}"
        config = {"configurable": {"thread_id": thread_id}}

        print(f"Quest thread: {thread_id}")
        result = graph.invoke(
            {"guesses": [], "next_hint": 0},
            config=config,
        )

        while result.get("__interrupt__"):
            guess = input("Enter your guess:\n> ")
            result = graph.invoke(Command(resume=guess), config=config)

        again = input("\n Start another quest? (y/n) ").strip().lower()

        if again not in {"y", "yes"}:
            break

        print()

    print(list(graph.get_state_history(config=config)))

