import json

text = """```json
{
    "intent": "greeting",
    "category": null,
    "product_name": null,
    "quantity": null,
    "confidence": 0.95
}
```"""

cleaned_text = text.strip()
if cleaned_text.startswith("```json"):
    cleaned_text = cleaned_text[7:]
elif cleaned_text.startswith("```"):
    cleaned_text = cleaned_text[3:]
if cleaned_text.endswith("```"):
    cleaned_text = cleaned_text[:-3]

print(repr(cleaned_text.strip()))

try:
    data = json.loads(cleaned_text.strip())
    print("Parsed OK")
except Exception as e:
    print("Error:", e)
