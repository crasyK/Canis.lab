import json
from typing import Callable, Any

from lib.tools.code import execute_code_tool, save_code_tool_results
from lib.tools.llm import generate_llm_tool_batch_file, get_available_llm_tools, get_tool_template
from lib.tools.seed import generate_seed_batch_file
from lib.tools.batch import convert_batch_in_to_json_data

available_chips = {
    "Seed Data Generation": {
        "data_markers": {
            "in": {"seed_file_location":{"file":"single"}},
            "out": {"generated_data":{"json":"data"}, "queries":{"json":"data"}}
        }
    },
    "Classification":{
        "data_markers":{
            "in": {"classification_description":{"str":"single"}, "classification_list":{"list":"single"}, "data":{"json":"data"}},
            "out": [] # Empty because the amount of final data outputs is dependent on the classification list
        }
    },
    "Dialogue Parsing": {
        "data_markers": {
            "in": {"data":{"str":"data"}},
            "out": {"parsed_data":{"json":"data"}}
        }
    },
    "5-Stage Conversation Analysis": {
        "data_markers": {
            "in": {"data":{"json":"data"}},
            "out": {"EXCELLENT":{"json":"data"}, "GOOD":{"json":"data"}, "FAIR":{"json":"data"}, "POOR":{"json":"data"}, "REJECT":{"json":"data"}}
        }
    }
}

def get_available_chips():
    return available_chips


def start_seed_data_generation_chip(seed_file_location: str, batch_file_location: str):
    generated_seed_data = generate_seed_batch_file(seed_file_location, batch_file_location)
    return get_available_chips()["Seed Data Generation"]["data_markers"]["out"]

def finish_seed_data_generation_chip(seed_file_location: dict, batch_data: dict):
    generated_seed_data = generate_seed_batch_file(seed_file_location, None)
    queries, sys_prompts = convert_batch_in_to_json_data(generated_seed_data, None, None)
    return {"generated_data": batch_data, "queries":queries}


def start_classification_chip(classification_description: str, classification_list: list, data: dict, batch_file_location: str):
    expanded_descriptions = save_code_tool_results("expand",execute_code_tool("expand", {"single": classification_description, "data_to_adapt_to": data}),None)
    expanded_classification_list = save_code_tool_results("expand",execute_code_tool("expand", {"single": classification_list, "data_to_adapt_to": data}),None)
    generate_llm_tool_batch_file("clean", {"__criteria_verbose__": expanded_descriptions, "__lables__": expanded_classification_list, "__dirty_data__": data}, batch_file_location)

    output_markers = {}

    for classification in classification_list:
        output_markers.update({classification: {"json":"data"}})

    return output_markers

def finish_classification_chip(classification_description: str, classification_list: list, data: dict, batch_data: dict):
    print("Finishing classification chip...")
    segregated_data = execute_code_tool("segregate", {"data": data, "classification": batch_data, "labels": classification_list})
    return segregated_data

def start_dialogue_parsing_chip(data: dict, batch_file_location: str):
    generate_llm_tool_batch_file("parse_conversation", {"__conversation__": data}, batch_file_location)

    return get_available_chips()["Dialogue Parsing"]["data_markers"]["out"]

def finish_dialogue_parsing_chip(data: dict, batch_data: dict):
    unwind_data = save_code_tool_results("unwind",execute_code_tool("bind", {"structured_content": batch_data, "key_name": "dialogue"}), None)
    return {"parsed_data": unwind_data}

def start_5_stage_conversation_analysis_chip(data: dict, batch_file_location: str):
    classification_description = """DIALOGUE QUALITY ASSESSMENT CRITERIA:\n\n1. COHERENCE & RELEVANCE (40% weight):\n   - Responses are logically connected to previous messages\n   - Each turn addresses the topic or question appropriately\n   - No contradictory or nonsensical responses\n   - Maintains conversational flow and context\n\n2. COMPLETENESS & STRUCTURE (25% weight):\n   - Dialogue has clear beginning and natural progression\n   - Conversations feel complete, not abruptly cut off\n   - Proper turn-taking between participants\n   - No missing or truncated responses\n\n3. LANGUAGE QUALITY (20% weight):\n   - Proper grammar, spelling, and punctuation\n   - Natural, human-like language (not robotic or template-heavy)\n   - Appropriate vocabulary and tone for the context\n   - Clear and understandable communication\n\n4. ROLE CONSISTENCY (10% weight):\n   - Speakers maintain consistent roles throughout\n   - No role confusion or switching mid-conversation\n   - Appropriate expertise level for assigned roles\n\n5. EDUCATIONAL/PRACTICAL VALUE (5% weight):\n   - Content is informative, helpful, or educational\n   - Provides value to potential training use cases\n   - Demonstrates good conversation patterns\n\nCLASSIFICATION GUIDELINES:\n- EXCELLENT: Meets all criteria excellently, exemplary dialogue\n- GOOD: Meets most criteria well, minor issues only\n- FAIR: Meets basic criteria but has notable quality issues\n- POOR: Significant problems in multiple criteria areas\n- REJECT: Unusable due to major coherence, completion, or quality issues"""
    classification_list = ["EXCELLENT", "GOOD", "FAIR", "POOR", "REJECT"]
    expanded_descriptions = save_code_tool_results("expand",execute_code_tool("expand", {"single": classification_description, "data_to_adapt_to": data}),None)
    expanded_classification_list = save_code_tool_results("expand",execute_code_tool("expand", {"single": classification_list, "data_to_adapt_to": data}),None)
    generate_llm_tool_batch_file("clean", {"__criteria_verbose__": expanded_descriptions, "__lables__": expanded_classification_list, "__dirty_data__": data}, batch_file_location)

    output_markers = {}

    for classification in classification_list:
        output_markers.update({classification: {"json":"data"}})

    return output_markers

def finish_5_stage_conversation_analysis_chip(data: dict, batch_data: dict):
    print("Finishing 5-stage conversation analysis chip...")
    segregated_data = execute_code_tool("segregate", {"data": data, "classification": batch_data, "labels": ["EXCELLENT", "GOOD", "FAIR", "POOR", "REJECT"]})
    return segregated_data

REGISTRY: dict[str, Callable[..., Any]] = {
    "Seed Data Generation": {"start":start_seed_data_generation_chip,"finish":finish_seed_data_generation_chip},
    "Classification": {"start":start_classification_chip,"finish":finish_classification_chip},
    "Dialogue Parsing": {"start":start_dialogue_parsing_chip,"finish":finish_dialogue_parsing_chip},
    "5-Stage Conversation Analysis": {"start":start_5_stage_conversation_analysis_chip,"finish":finish_5_stage_conversation_analysis_chip}
}

def prepare_chip_use(chip_name):
    available_chips = get_available_chips()
    if chip_name not in available_chips:
        raise ValueError(f"Unknown chip '{chip_name}'")
    return available_chips[chip_name].get("data_markers", {})

def start_chip_tool(chip_name, data, batch_file_location):
    fn = REGISTRY.get(chip_name)
    if not fn:
        raise ValueError(f"Unknown chip '{chip_name}'")
    return fn["start"](**data, batch_file_location=batch_file_location)

def finish_chip_tool(chip_name, data, batch_data):
    fn = REGISTRY.get(chip_name)
    if not fn:
        raise ValueError(f"Unknown chip '{chip_name}'")
    return fn["finish"](**data, batch_data=batch_data)

def save_chip_results(chip_name, results, filenames):
    for key, data in results.items():
        dataset = {}
        for i, item in data.items():
            dataset[i] = item
        with open(filenames[key], 'w') as f:
            json.dump(dataset, f)
