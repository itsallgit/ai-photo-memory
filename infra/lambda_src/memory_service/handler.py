import json
import uuid
import random
from datetime import datetime

def _parse_event(payload):
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except:
            return {}, None
    if isinstance(payload, dict):
        name = payload.get('name') or payload.get('tool') or payload.get('toolName')
        args = payload.get('arguments') or payload.get('input') or payload.get('body')
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except:
                args = {}
        return args or {}, name
    return {}, None

def remember_text(args):
    text = args.get('text', '')
    memory_id = str(uuid.uuid4())
    who = ["Alice", "Bob"] if random.random() > 0.5 else ["Carol"]
    what = text[:140] or "A remembered event"
    when = datetime.utcnow().date().isoformat()
    where = "123 Example St, Sydney, Australia"
    return {"memory_id": memory_id, "who": who, "what": what, "when": when, "where": where}

def add_memory(args):
    memory_id = str(uuid.uuid4())
    return {"memory_id": memory_id, "who": args.get("who", []), "what": args.get("what", ""), "when": args.get("when", datetime.utcnow().date().isoformat()), "where": args.get("where", "")}

def handler(event, context):
    args, name = _parse_event(event)
    if not name:
        name = event.get('tool') or event.get('toolName')
    if name and name.endswith('remember'):
        return remember_text(args)
    elif name and name.endswith('add_memory'):
        return add_memory(args)
    else:
        action = args.get('action') if isinstance(args, dict) else None
        if action == 'remember':
            return remember_text(args)
        elif action == 'add_memory':
            return add_memory(args)
        return {"error":"unknown_tool","message":"Tool name not provided or unrecognized."}
