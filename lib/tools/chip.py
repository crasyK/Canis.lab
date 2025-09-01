import json
from typing import Callable, Any

from lib.tools.code import execute_code_tool, save_code_tool_results
from lib.tools.llm import generate_llm_tool_batch_file, get_available_llm_tools, get_tool_template

available_chips = {
    "Classification":{
        "data_markers":{
            "in": {"classification_description":{"str":"single"}, "classification_list":{"list":"single"}, "data":{"json":"data"}},
            "out": [] # Empty because the amount of final data outputs is dependent on the classification list
        }
    },
    "Dialogue Parsing": {
        "data_markers": {
            "in": {"data":{"json":"data"}},
            "out": {"parsed_data":{"json":"data"}}
        }
    }
}

def get_available_chips():
    return available_chips

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
    unwind_data = execute_code_tool("bind", {"structured_content": batch_data, "key_name": "dialogue"})
    return {"parsed_data": unwind_data}

REGISTRY: dict[str, Callable[..., Any]] = {
    "Classification": {"start":start_classification_chip,"finish":finish_classification_chip},
    "Dialogue Parsing": {"start":start_dialogue_parsing_chip,"finish":finish_dialogue_parsing_chip}
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
