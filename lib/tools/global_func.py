import json

def get_type(item):
    if isinstance(item, list):
        return "list"
    elif isinstance(item, str):
            try:
                parsed = json.loads(item)
                if isinstance(parsed, dict):
                    return "json_data"
                else:
                    return "str"
            except (json.JSONDecodeError, TypeError):
                return "str"
    return "unknown"