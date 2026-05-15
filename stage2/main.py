from uuid import uuid4

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing_extensions import TypedDict, NotRequired
from typing import Any
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command, interrupt
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

load_dotenv()

class Riddle(BaseModel):
    """A structured challenge presented to the player."""

    question: str = Field(description="The complete riddle question.")
    answer: str = Field(description="The concise answer to the riddle.")
    hints: list[str] = Field(
        min_length=3,
        max_length=3,
        description="Exactly three helpful hints, ordered from subtle to revealing."
    )

    category: SkipJsonSchema[str] = "general"
    difficulty: SkipJsonSchema[str] = "easy"

model = init_chat_model("gpt-5.4-mini").with_structured_output(Riddle)

class GraphState(TypedDict):
    riddle: dict[str, Any]
    guess: NotRequired[str]
    result: NotRequired[str]


def generate_riddle_node(_: GraphState) -> GraphState:

    print("Generating your challenge...\n")

    generated_riddle = model.invoke(
        """
          Create a riddle that meets the following requirements:
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
    """Display only the public portion of the generated challenge."""
    riddle = Riddle.model_validate(state["riddle"])

    print(f"Category: {riddle.category.title()}")
    print(f"Difficulty: {riddle.difficulty.title()}\n")
    print(riddle.question)

    print()

    guess = interrupt("Enter your guess: ")

    return {"guess": guess}

def normalize_answer(value: str) -> str:
    """Normalize capitalization, surrounding whitespace, and leading articles."""
    normalized = " ".join(value.casefold().split())

    for article in ("a ", "an ", "the "):
        if normalized.startswith(article):
            return normalized[len(article):]
    return normalized


def judge_guess_node(state: GraphState) -> GraphState:
    """Compare the player's guess with the riddle's answer"""

    riddle = Riddle.model_validate(state["riddle"])

    guess = state["guess"]

    if normalize_answer(guess) == normalize_answer(riddle.answer):
        print("Correct! You opened the vault.")
        return {"result": "Opened"}
    else:
        print(f"Answer: {riddle.answer}")

        return {"result": "Not opened"}


builder = StateGraph(GraphState)
builder.add_node("generate_riddle", generate_riddle_node)
builder.add_node("display_riddle", display_riddle_node)
builder.add_node("judge_guess", judge_guess_node)

builder.add_edge(START, "generate_riddle")
builder.add_edge("generate_riddle", "display_riddle")
builder.add_edge("display_riddle", "judge_guess")
builder.add_edge("judge_guess", END)


checkpointer = InMemorySaver()
graph = builder.compile(checkpointer=checkpointer)
print(graph.get_graph())

thread_id = f"quest-{uuid4()}"
print(f"Quest thread: {thread_id}\n")

config = {"configurable": {"thread_id": thread_id}}
graph.invoke({}, config=config)

player_guess = input("Enter your guess: \n> ")
graph.invoke(Command(resume=player_guess), config=config)

print(list(graph.get_state_history(config=config)))
