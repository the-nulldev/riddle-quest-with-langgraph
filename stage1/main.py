from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from typing import TypedDict
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
        description="Exactly 3 helpful hints, ordered from subtle to revealing."
    )

    category: SkipJsonSchema[str] = "general"
    difficulty: SkipJsonSchema[str] = "easy"

model = init_chat_model("gpt-5.4-mini").with_structured_output(Riddle)

class GraphState(TypedDict):
    riddle: dict[str, object]


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
            "difficulty": "easy",
        }
    )

    return {"riddle": generated_riddle.model_dump()}


def display_riddle_node(state: GraphState) -> GraphState:
    """Display the generated challenge question."""
    riddle = Riddle.model_validate(state["riddle"])
    print(riddle)
    print(f"Category: {riddle.category.title()}")
    print(f"Difficulty: {riddle.difficulty.title()}\n")
    print(riddle.question)

    return {}


builder = StateGraph(GraphState)
builder.add_node("generate_riddle", generate_riddle_node)
builder.add_node("display_riddle", display_riddle_node)

builder.add_edge(START, "generate_riddle")
builder.add_edge("generate_riddle", "display_riddle")
builder.add_edge("display_riddle", END)

graph = builder.compile()
print(graph.get_graph())


if __name__ == "__main__":
    result = graph.invoke({})
    print(result)


