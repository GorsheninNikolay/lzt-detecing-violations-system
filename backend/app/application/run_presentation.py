"""Small operational snapshots for the product interface; full audit stays separate."""


def summary_snapshot(snapshot: dict) -> dict:
    return {**snapshot, 'ai_evidence': [
        {**call, 'result': None} for call in snapshot.get('ai_evidence', [])
    ]}
