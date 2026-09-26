"""Conservative, revision-bound comparisons for one declared zone."""
from datetime import datetime


def compare_equipment(entries: list[dict], frame_times: list[str], observations: list[dict],
                      usable_ids: list[str], supported: set[str], *, frames=None) -> list[dict]:
    if not entries or not frame_times:
        return []
    legacy = frames is None
    if frames is None:
        ordered = list(dict.fromkeys(o['input_id'] for o in observations))
        if len(ordered) != len(frame_times):
            return []
        frames = [{'input_id': key, 'captured_at': time, 'sha256': key} for key, time in zip(ordered, frame_times)]
    timed = []
    for frame in frames:
        try:
            time = datetime.fromisoformat(frame['captured_at'])
        except (TypeError, ValueError):
            continue
        if time.utcoffset() is not None:
            active = [e for e in entries if e['state'] == 'active' and e['starts_at'] <= time <= e['ends_at']]
            timed.append((frame, active))

    def independent(candidates):
        distinct = {}
        for frame in candidates:
            if frame['input_id'] in usable_ids and frame.get('frame_usability', {'usable': True})['usable']:
                distinct.setdefault(frame['sha256'], frame)
        return list(distinct.values())

    reason = 'At least three assessable frames of the active zone are required.'
    if legacy and any(active for _, active in timed) and len(independent([f for f, _ in timed])) < 3:
        return [{'kind': 'insufficient_observations', 'entry_id': None, 'reason': reason}]
    states = {(o['input_id'], o['class_name']): o['state'] for o in observations}
    signals = []
    for entry in entries:
        applicable = [f for f, active in timed if entry in active]
        if not applicable:
            continue
        usable = independent(applicable)
        if len(usable) < 3:
            signals.append({'kind': 'insufficient_observations', 'entry_id': entry['id'], 'reason': reason,
                            'supporting_input_ids': [f['input_id'] for f in applicable]})
            continue
        for name in entry['expected_equipment']:
            if (name not in supported or name == 'concrete_mixer_truck' and entry.get('stage_key') != 'concreting'
                    or name == 'road_roller' and entry.get('stage_key') != 'roadwork'):
                continue
            if any(states.get((f['input_id'], name)) == 'detected' for f in applicable):
                continue
            assessable = independent([f for f in applicable
                if f.get('class_assessability', {}).get(name, 'assessable') == 'assessable'
                and states.get((f['input_id'], name)) == 'not_detected_in_frame'])
            ids = [f['input_id'] for f in assessable]
            if len(ids) < 3:
                if not legacy:
                    signals.append({'kind': 'insufficient_observations', 'entry_id': entry['id'],
                                    'class_name': name, 'reason': reason, 'supporting_input_ids': [f['input_id'] for f in applicable]})
                continue
            signals.append({'kind': 'expected_equipment_missing', 'entry_id': entry['id'], 'class_name': name,
                            'reason': 'Expected equipment was not detected in the assessable series.',
                            'supporting_input_ids': ids})
        excluded = {}
        for frame, concurrent in timed:
            if entry not in concurrent or frame not in usable:
                continue
            allowed = set().union(*(set(e['expected_equipment']) | set(e['allowed_equipment']) for e in concurrent))
            forbidden = set.intersection(*(set(e['excluded_equipment']) for e in concurrent)) - allowed
            for name in forbidden & supported:
                if states.get((frame['input_id'], name)) == 'detected':
                    excluded.setdefault(name, []).append(frame['input_id'])
        for name, ids in excluded.items():
            signals.append({'kind': 'equipment_not_planned', 'entry_id': entry['id'], 'class_name': name,
                            'reason': 'All concurrent active operations explicitly exclude this equipment.',
                            'supporting_input_ids': ids})
    return [{k: v for k, v in signal.items() if k != 'supporting_input_ids'} for signal in signals] if legacy else signals
