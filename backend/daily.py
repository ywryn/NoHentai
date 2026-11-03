"""Attach the actual saved conditions to daily result groups, including legacy snapshots."""
import json
from app.daily_config import conditions


def result_groups(con):
    from . import db
    groups = [{key: value for key, value in group.items() if key != 'filters'}
              for group in db.snapshot(con, 'daily', [])]
    missing = [group for group in groups if not group.get('conditions')]
    if not missing:
        return groups
    # A current rule may have changed since publication. Recover from the matching
    # successful checkpoint first; never present today's rule as a historical fact.
    for row in con.execute("""SELECT j.config_json,s.result_json FROM jobs j
            JOIN job_steps s ON s.job_id=j.id AND s.name='daily'
            WHERE j.conclusion='success' AND s.result_json IS NOT NULL
            ORDER BY j.id DESC"""):
        config = json.loads(row['config_json'] or '{}')
        frozen = {rule['name']: rule for rule in config.get('daily', [])}
        for published in json.loads(row['result_json']):
            for group in missing[:]:
                if (group.get('generatedAt') and group.get('generatedAt') == published.get('generatedAt')
                        and group.get('name') == published.get('name') and published['name'] in frozen):
                    group['conditions'] = conditions(frozen[published['name']])
                    group['conditionsSource'] = 'snapshot'
                    missing.remove(group)
        if not missing:
            break
    rules = con.execute('SELECT id,data FROM daily_rules ORDER BY position').fetchall() if missing else []
    for group in missing:
        for row in rules:
            rule = json.loads(row['data'])
            if (group.get('groupId') == row['id'] if group.get('groupId') else group.get('name') == rule['name']):
                group['conditions'] = conditions(rule)
                group['conditionsSource'] = 'current'
                break
    return groups
