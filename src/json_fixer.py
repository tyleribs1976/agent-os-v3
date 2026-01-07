"""Fix JSON parsing issues with unescaped newlines."""

def fix_json_newlines(json_str: str) -> str:
    """
    Fix unescaped newlines inside JSON string values.
    """
    result = []
    in_string = False
    escape_next = False
    newline_count = 0
    fixed_count = 0
    
    for i, char in enumerate(json_str):
        if escape_next:
            result.append(char)
            escape_next = False
        elif char == "\\":
            result.append(char)
            escape_next = True
        elif char == "\"":
            result.append(char)
            in_string = not in_string
        elif char == "\n":
            newline_count += 1
            if in_string:
                result.append("\\n")
                fixed_count += 1
                print(f"DEBUG: Fixed newline at position {i}, in_string={in_string}")
            else:
                result.append(char)
        elif char == "\r" and in_string:
            result.append("\\r")
        elif char == "\t" and in_string:
            result.append("\\t")
        else:
            result.append(char)
    
    print(f"DEBUG fix_json_newlines: total {len(json_str)} chars, {newline_count} newlines, {fixed_count} fixed")
    return "".join(result)
