import json

data = json.load(open("scroll_result.json", encoding="utf-8"))
for point in data["result"]["points"]:
    payload = point["payload"]
    page = payload.get("page")
    content = payload.get("content", "")
    print(f"page={page} content={content[:150]}")
    print("---")
