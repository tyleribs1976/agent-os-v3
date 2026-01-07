from src.json_fixer import fix_json_newlines
import json
test_json = "{\"content\": \"line1" + chr(10) + "line2\"}"
print("Original repr:", repr(test_json))
try:
    json.loads(test_json)
except json.JSONDecodeError as e:
    print("Original error:", e)
fixed = fix_json_newlines(test_json)
print("Fixed repr:", repr(fixed))
try:
    result = json.loads(fixed)
    print("Fixed parsed:", result)
except json.JSONDecodeError as e:
    print("Fixed error:", e)
