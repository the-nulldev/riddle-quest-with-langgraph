import operator
import uuid
from typing import Annotated, NotRequired, TypedDict

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.store.memory import InMemoryStore
from langgraph.types import Command, Send, interrupt
from pydantic import BaseModel, Field
from pydantic.json_schema import SkipJsonSchema

load_dotenv()


class Riddle(BaseModel):
    """A structured challenge presented to the player."""

    title: str = Field(description="A short, atmospheric vault title.")
    question: str = Field(description="The riddle question.")
    answer: str = Field(description="The answer to the riddle.")
    hints: list[str] = Field(
        min_length=3,
        max_length=3,
        description="Exactly three helpful hints, ordered from subtle to revealing.",
    )

    category: SkipJsonSchema[str] = ""
    difficulty: SkipJsonSchema[str] = ""
    vault_number: SkipJsonSchema[int] = 0

model = init_chat_model("gpt-5.4-mini").with_structured_output(Riddle)


class GraphState(TypedDict):
    riddles: Annotated[list[dict[str, object]], operator.add]
    riddle: NotRequired[dict[str, object]]
    guesses: Annotated[list[str], operator.add]
    preferred_category: NotRequired[str]
    preferred_difficulty: NotRequired[str]
    selected_vault: NotRequired[int]
    next_hint: int
    result: NotRequired[str]


class VaultWorkerState(TypedDict):
    category: str
    difficulty: str
    vault_number: int


CATEGORIES = ("nature", "geography", "logic", "object")
DIFFICULTIES = ("easy", "medium", "hard")


def user_preferences_node(_: GraphState, runtime: Runtime) -> GraphState:
    user_id = input("Please enter your ID: ")
    preferences_namespace = (user_id, 'hyper-user')
    preferences_key = "user_preferences"

    stored_preferences = runtime.store.get(preferences_namespace, preferences_key)

    if stored_preferences is None:
        print("No saved/valid preferences were found. \n")
        while True:
            category = input("Please choose a category: ['nature', 'geography', 'object', 'logic'] ").strip().casefold()
            difficulty = input("Please choose a difficulty: ['easy', 'medium', 'hard'] ").strip().casefold()

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

    decision = input(f"Would you like to change these preferences? (y/N) ")

    if decision.lower() in {"y", "yes"}:
        category_upd = input("Please choose a category: ['nature', 'geography', 'object', 'logic'] ")
        difficulty_upd = input("Please choose a difficulty: ['easy', 'medium', 'hard'] ")

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


def send_vault_workers(state: GraphState) -> list[Send]:
    """Create three distinct vault-generation tasks."""
    category = state["preferred_category"]
    difficulty = state["preferred_difficulty"]

    settings = [
        {
            "vault_number": 1,
            "category": category,
            "difficulty": difficulty,
        },
        {
            "vault_number": 2,
            "category": "general",
            "difficulty": difficulty,
        },
    ]

    print(f"Preparing two vaults: [general] and [{category}] categories...\n")
    return [Send("generate_vault", setting) for setting in settings]


def generate_vault_node(state: VaultWorkerState) -> GraphState:
    """Generate one riddle and return it as a one-element reducer list."""
    category = state["category"]
    difficulty = state["difficulty"]

    generated_riddle = model.invoke(
        f"""
          Create a riddle that meets the following requirements:
          - Give the vault a short, atmospheric title.
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
            "difficulty": difficulty,
            "vault_number": state["vault_number"]
        })

    return {"riddles": [riddle.model_dump()]}



def preview(question: str, limit: int = 50) -> str:
    """Create a short single-line question preview."""
    value = " ".join(question.split())
    if len(value) <= limit:
        return value
    return f"{value[:limit - 3].rstrip()}..."


def choose_vault_node(state: GraphState) -> GraphState:
    """Display all generated vaults and pause for a valid selection."""
    riddles = sorted(
        (Riddle.model_validate(value) for value in state["riddles"]),
        key=lambda value: value.vault_number,
    )

    print("Choose a vault:\n")
    for riddle in riddles:
        print(
            f"{riddle.vault_number}. {riddle.title} — "
            f"{riddle.category.title()}, {riddle.difficulty.title()}"
        )
        print(f"   {preview(riddle.question)}\n")

    selection = interrupt("Select a vault:")

    try:
        selected_number = int(str(selection).strip())
    except ValueError:
        selected_number = 0

    if selected_number not in {1, 2}:
        print("Choose vault 1 or 2.")
        return Command(goto="choose_vault")

    selected = next(
        riddle for riddle in riddles
        if riddle.vault_number == selected_number
    )

    print(f"\nEntering {selected.title}...\n")
    return {
        "selected_vault": selected_number,
        "riddle": selected.model_dump(),
        "guesses": [],
        "next_hint": 0,
    }

def get_selected_riddle(state: GraphState) -> Riddle:
    """Return the riddle belonging to the selected vault."""
    selected_vault = state["selected_vault"]

    return next(
        Riddle.model_validate(value)
        for value in state["riddles"]
        if value["vault_number"] == selected_vault
    )

def display_riddle_node(state: GraphState) -> GraphState:
    """Display the riddle and pause for the initial guess."""
    riddle = get_selected_riddle(state)

    print(f"Category: {riddle.category.title()}")
    print(f"Difficulty: {riddle.difficulty.title()}\n")
    print(riddle.question)
    print()

    guess = interrupt("Enter your guess: ")

    return {"guesses": [guess]}


def normalize_answer(value: str) -> str:
    """Normalize capitalization, whitespace, and leading articles."""
    normalized = " ".join(value.casefold().split())

    for article in ("a ", "an ", "the "):
        if normalized.startswith(article):
            return normalized[len(article):]

    return normalized


def route_guess(state: GraphState) -> str:
    """Route the latest guess to victory, a hint, or defeat."""
    riddle = get_selected_riddle(state)
    latest_guess = state["guesses"][-1]

    if normalize_answer(latest_guess) == normalize_answer(riddle.answer):
        return "victory"

    if len(state["guesses"]) < 4:
        return "reveal_hint"

    return "defeat"


def reveal_hint_node(state: GraphState) -> GraphState:
    """Reveal the next unused hint and pause for another guess."""
    riddle = get_selected_riddle(state)
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
    print("Correct!")
    return {}

def defeat_node(state: GraphState) -> GraphState:
    """Reveal the answer after all attempts are exhausted."""
    riddle = get_selected_riddle(state)

    print("Incorrect. You're done.")
    print(f"The answer was: {riddle.answer}.")

    return {"result": "Not opened"}


builder = StateGraph(GraphState)
builder.add_node("user_preferences", user_preferences_node)
builder.add_node("generate_vault", generate_vault_node)
builder.add_node("choose_vault", choose_vault_node)
builder.add_node("display_riddle", display_riddle_node)
builder.add_node("reveal_hint", reveal_hint_node)
builder.add_node("victory", victory_node)
builder.add_node("defeat", defeat_node)

builder.add_edge(START, "user_preferences")
builder.add_conditional_edges("user_preferences", send_vault_workers)
builder.add_edge("generate_vault", "choose_vault")
builder.add_edge("choose_vault", "display_riddle")
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
            {
                "riddles": [],
                "guesses": [],
                "next_hint": 0,
            },
            config=config,
        )

        while result.get("__interrupt__"):
            interruption = result["__interrupt__"][0]
            prompt = str(interruption.value)
            answer = input(f"{prompt} ")
            result = graph.invoke(Command(resume=answer), config=config)

        print(result)

        print("\n1. Finish this quest. \n")
        print("2. Attempt the second riddle.")

        user_choice = input("\nChoose an option:\n> ").strip()

        if user_choice == "1":
            again = input("\nStart another quest? (y/n) ").strip().casefold()
            if again not in {"y", "yes"}:
                exit(1)

        if user_choice == "2":
            final_state = list(graph.get_state_history(config))
            current_state = graph.get_state(config)


            print(final_state)

            fork_snapshot = next(snapshot for snapshot in final_state if snapshot.next == ('display_riddle',))
            current_vault = int(current_state.values["selected_vault"])

            if current_vault == 2:
                new_vault = 1
            elif current_vault == 1:
                new_vault = 2
            else:
                raise ValueError("Go to hell!")

            fork_config = graph.update_state(
                fork_snapshot.config,
                values={
                    "selected_vault": new_vault,
                }
            )

            fork_runtime_config = {
                "configurable": {
                    "thread_id": fork_config["configurable"]["thread_id"],
                    "checkpoint_ns": fork_config["configurable"].get("checkpoint_ns", ""),
                }

            }

            fork_result = graph.invoke(None, config=fork_runtime_config)

            while fork_result.get("__interrupt__"):
                interruption = fork_result["__interrupt__"][0]
                prompt = str(interruption.value)
                answer = input(f"{prompt} ")
                fork_result = graph.invoke(Command(resume=answer), config=fork_runtime_config)

            again = input("\nStart another quest? (y/n) ").strip().casefold()
            if again not in {"y", "yes"}:
                forked_state = list(graph.get_state_history(fork_runtime_config))
                print(forked_state)
                exit(1)


