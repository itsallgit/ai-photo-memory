import json
import uuid

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

def start_slideshow(args):
    confirmation = str(uuid.uuid4())
    message = f"Slideshow started (id: {confirmation})"
    return {"message": message, "code": 0}

def get_tags(args):
    tags = [{"tag":"beach","count":120}, {"tag":"family","count":45}, {"tag":"sunset","count":78}]
    return {"tags": tags}

def handler(event, context):
    args, name = _parse_event(event)
    if not name:
        name = event.get('tool') or event.get('toolName')
    if name and name.endswith('start_slideshow'):
        return start_slideshow(args)
    elif name and name.endswith('get_tags'):
        return get_tags(args)
    else:
        action = args.get('action') if isinstance(args, dict) else None
        if action == 'start_slideshow':
            return start_slideshow(args)
        elif action == 'get_tags':
            return get_tags(args)
        return {"error":"unknown_tool","message":"Tool name not provided or unrecognized."}
