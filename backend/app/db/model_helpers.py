import json

from app.db.models import IntelligenceItem


def analysis_dict(item: IntelligenceItem) -> dict:
    if not item.analysis_json:
        return {}
    try:
        return json.loads(item.analysis_json)
    except json.JSONDecodeError:
        return {}


IntelligenceItem.analysis = property(analysis_dict)
