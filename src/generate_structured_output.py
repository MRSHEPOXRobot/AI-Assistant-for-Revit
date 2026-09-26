"""
Baseline 1 (v2): جيب structured output (JSON) من Qwen2.5-Coder-14B-Instruct
باستخدام grammar-constrained decoding + few-shot prompting.

الاستخدام:
    python generate_structured_output.py "Create a wall from (0,0,0) to (5000,0,0) on Level 1"

راجع README.md في جذر المشروع لتفاصيل كل القرارات والإصلاحات اللي وصلنا بيها للنسخة دي.
"""

import json
import sys
from pathlib import Path

from llama_cpp import Llama, LlamaGrammar
from jsonschema import validate, ValidationError

MODEL_PATH = "models/qwen2.5-coder-14b-instruct-q5_k_m.gguf"  # عدّل المسار حسب مكان تحميلك
SCHEMA_PATH = Path(__file__).parent.parent / "schema" / "revit_command_schema.json"

SYSTEM_PROMPT = (
    "You are a converter that turns natural-language Revit instructions "
    "into a single structured JSON command. Only output valid JSON matching "
    "the given schema. If the instruction is ambiguous, make a reasonable "
    "assumption and explain it in \"notes\". If the instruction does not "
    "correspond to any supported action, use action = \"unknown\".\n\n"
    "Field usage rules:\n"
    "- For create_door / create_window: put the host wall's id in "
    "target.host_element_id, NOT target.element_id (element_id is only for "
    "modify/move/delete/query actions that target an existing element directly).\n"
    "- For create_level: use parameters.elevation for the level's vertical "
    "position. NEVER use parameters.height for this - height is only for the "
    "height dimension of an object like a wall or door.\n"
    "- For modify_parameter: ALWAYS use parameters.parameter_name and "
    "parameters.parameter_value together to describe the change, even if the "
    "parameter being changed has a typed field elsewhere in the schema (like "
    "height or width). Leave those typed fields null in this case - do not "
    "fill both the typed field and parameter_name/parameter_value."
)

FEWSHOT_SYSTEM_PROMPT = SYSTEM_PROMPT + """

Examples:

Instruction: "Create a wall from (0,0,0) to (3000,0,0) on Level 1 with height 2800mm"
Output: {"action": "create_wall", "target": {"element_id": null, "category": null, "filter": null, "host_element_id": null}, "parameters": {"start_point": [0,0,0], "end_point": [3000,0,0], "level": "Level 1", "height": 2800, "width": null, "family_type": null, "parameter_name": null, "parameter_value": null, "offset": null, "elevation": null}, "confidence": "high", "notes": null}

Instruction: "Add a door type 'Single-Flush: 900x2100mm' on the wall with id 45021"
Output: {"action": "create_door", "target": {"element_id": null, "category": null, "filter": null, "host_element_id": 45021}, "parameters": {"start_point": null, "end_point": null, "level": null, "height": null, "width": null, "family_type": "Single-Flush: 900x2100mm", "parameter_name": null, "parameter_value": null, "offset": null, "elevation": null}, "confidence": "high", "notes": null}

Instruction: "Create a new level called 'Level 4' at elevation 12000mm"
Output: {"action": "create_level", "target": {"element_id": null, "category": null, "filter": null, "host_element_id": null}, "parameters": {"start_point": null, "end_point": null, "level": "Level 4", "height": null, "width": null, "family_type": null, "parameter_name": null, "parameter_value": null, "offset": null, "elevation": 12000}, "confidence": "high", "notes": null}

Instruction: "Change the height parameter of wall id 45010 to 4000mm"
Output: {"action": "modify_parameter", "target": {"element_id": 45010, "category": null, "filter": null, "host_element_id": null}, "parameters": {"start_point": null, "end_point": null, "level": null, "height": null, "width": null, "family_type": null, "parameter_name": "Height", "parameter_value": "4000", "offset": null, "elevation": null}, "confidence": "high", "notes": null}

Instruction: "Show me all doors on Level 2"
Output: {"action": "query_elements", "target": {"element_id": null, "category": "Doors", "filter": "level = Level 2", "host_element_id": null}, "parameters": {"start_point": null, "end_point": null, "level": null, "height": null, "width": null, "family_type": null, "parameter_name": null, "parameter_value": null, "offset": null, "elevation": null}, "confidence": "high", "notes": null}
"""


def load_schema() -> dict:
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_llm(n_ctx: int = 4096, n_gpu_layers: int = -1) -> Llama:
    """
    n_gpu_layers = -1 بيحاول يحمّل كل الطبقات على الـ GPU لو متاح.
    لو مفيش GPU حط 0 (هيشتغل على CPU بس هيكون أبطأ بكتير مع موديل 14B).
    """
    return Llama(
        model_path=MODEL_PATH,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False,
    )


def generate(llm: Llama, grammar: LlamaGrammar, instruction: str,
             system_prompt: str = FEWSHOT_SYSTEM_PROMPT) -> dict:
    out = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": instruction},
        ],
        grammar=grammar,
        max_tokens=512,
        temperature=0.7,
        top_p=0.8,
        top_k=20,
        repeat_penalty=1.1,
    )
    text = out["choices"][0]["message"]["content"].strip()
    # strict=False: يسمح بـ control characters خام (زي newline) جوه الـ strings
    # بدل ما يفشل بـ "Invalid control character"
    return json.loads(text, strict=False)


def main():
    if len(sys.argv) < 2:
        print("الاستخدام: python generate_structured_output.py \"<التعليمة باللغة الطبيعية>\"")
        sys.exit(1)

    instruction = sys.argv[1]
    schema = load_schema()
    grammar = LlamaGrammar.from_json_schema(json.dumps(schema))

    llm = build_llm()
    result = generate(llm, grammar, instruction)

    try:
        validate(instance=result, schema=schema)
        print("✅ Output صالح ومطابق للـ schema:\n")
    except ValidationError as e:
        print(f"❌ فشل الـ validation: {e.message}\n")

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
