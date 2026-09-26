"""Current-profile quality evidence, separate from historical readiness reports."""
import json
from pathlib import Path

from app.shared.cloud import canonical_bytes, digest

REPORT_PATH = Path(__file__).resolve().parents[1] / 'data' / 'hybrid-readiness.json'


def read_report(profile, path=None):
    if not profile or profile.get('observation_contract') != 'hybrid-photo-signals-v1':
        return {'status': 'blocked', 'code': 'hybrid_profile_not_bound'}
    try:
        report = json.loads((path or REPORT_PATH).read_text())
    except FileNotFoundError:
        return {'status': 'blocked', 'code': 'missing_current_report'}
    except (OSError, ValueError):
        return {'status': 'blocked', 'code': 'current_report_invalid'}
    if (not isinstance(report, dict) or report.get('profile_sha256') != digest(canonical_bytes(profile))
            or report.get('detector_manifest_sha256') != profile['detector_manifest_sha256']):
        return {'status': 'blocked', 'code': 'current_report_stale'}
    # Current evaluation artifacts do not yet provide a qualified reviewed-case inventory.
    # Boolean assertions cannot substitute for bounded measurements and source evidence.
    return {**report, 'status': 'blocked',
            **({'code': 'reviewed_evidence_incomplete'} if report.get('status') == 'pass' else {})}
