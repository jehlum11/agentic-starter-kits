from typing import Literal
from pydantic import BaseModel, create_model
import json
from os import getenv
import pandas as pd

from dotenv import load_dotenv

load_dotenv()


def dataframe_to_json_schema(
    df: pd.DataFrame,
    class_name: str = "GeneratedModel",
    exclude_columns: list[str] | None = None,
    max_enum_size: int = 50,
    required_columns: list[str] | None = None,
) -> dict:
    """
    Retrieve a JSON Schema (dict) from a pandas DataFrame.

    - Numeric columns → "integer" (if all ints) or "number"
    - Object/category columns → "string" with "enum" of unique values (if count <= max_enum_size)
    """
    exclude_columns = exclude_columns or []
    properties: dict = {}
    required: list[str] = required_columns or []
    for col in df.columns:
        if col in exclude_columns:
            continue

        if required_columns is None:
            required.append(col)
        dtype = df[col].dtype
        series = df[col].dropna()

        if pd.api.types.is_numeric_dtype(dtype):
            if (
                pd.api.types.is_integer_dtype(dtype)
                and (series == series.astype(int)).all()
            ):
                properties[col] = {"type": "integer", "title": col}
            else:
                properties[col] = {"type": "number", "title": col}
        else:
            uniques = series.astype(str).unique().tolist()
            if len(uniques) <= max_enum_size:
                properties[col] = {
                    "type": "string",
                    "enum": sorted(uniques),
                    "title": col,
                }
            else:
                properties[col] = {"type": "string", "title": col}

    return {
        "type": "object",
        "title": class_name,
        "properties": properties,
        "required": required,
    }


def dataframe_to_pydantic_model(
    df: pd.DataFrame,
    class_name: str = "GeneratedModel",
    exclude_columns: list[str] | None = None,
) -> type[BaseModel]:
    """
    Retrieve schema from a pandas DataFrame and create a Pydantic model from it.

    1. Builds a JSON Schema from column names and dtypes (enums from unique values).
    2. Creates and returns a Pydantic model class matching that schema.
    """
    schema = dataframe_to_json_schema(
        df, class_name=class_name, exclude_columns=exclude_columns
    )
    return json_schema_to_pydantic_model(schema, class_name=class_name)


def json_schema_to_pydantic_model(
    schema: dict | str,
    class_name: str | None = None,
) -> type[BaseModel]:
    """
    Create a Pydantic model from a JSON Schema (dict or path to .json file).

    Supports: type (string, integer, number), enum → Literal, required.
    """
    if isinstance(schema, str):
        with open(schema, encoding="utf-8") as f:
            schema = json.load(f)

    props = schema.get("properties", schema)
    required = set(schema.get("required", []))
    class_name = class_name or schema.get("title", "GeneratedModel")
    field_definitions = {}

    for name, prop in props.items():
        if not isinstance(prop, dict):
            continue
        typ = prop.get("type", "string")
        enum_vals = prop.get("enum")

        if enum_vals is not None:
            py_type = Literal.__getitem__(tuple(enum_vals))
        elif typ == "integer":
            py_type = int
        elif typ == "number":
            py_type = float
        else:
            py_type = str

        field_definitions[name] = (
            (py_type, ...) if name in required else (py_type | None, None)
        )

    return create_model(class_name, **field_definitions)


def get_chat_openai():
    """Ollama local (fallback when BASE_URL/MODEL_ID not set)."""
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model="llama3.2",
        base_url="http://localhost:11434/v1",
        api_key="ollama",
    )


def get_chat_from_env():
    """
    Chat client from env: BASE_URL, MODEL_ID, API_KEY (same as autogen agent).
    Uses OpenAI-compatible API (e.g. Llama Stack). Falls back to Ollama if not set.
    """
    from langchain_openai import ChatOpenAI

    base_url = getenv("BASE_URL")
    model_id = getenv("MODEL_ID")
    api_key = getenv("API_KEY")
    if base_url and model_id:
        url = base_url.rstrip("/")
        if not url.endswith("/v1"):
            url = url + "/v1"
        return ChatOpenAI(
            base_url=url,
            model=model_id,
            api_key=api_key or "not-needed",
            temperature=0.1,
        )
    return get_chat_openai()


def get_chat_llama_stack():
    from langchain_llama_stack import ChatLlamaStack

    llama_base_url = getenv("LLAMA_STACK_CLIENT_BASE_URL")
    llama_api_key = getenv("LLAMA_STACK_CLIENT_API_KEY")
    model_id = getenv("MODEL_ID")

    return ChatLlamaStack(
        base_url=f"{llama_base_url}/v1",
        api_key=llama_api_key,
        model=model_id,
        temperature=0.1,
    )
