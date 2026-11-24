"""Read provider billing metrics separately from the lightweight health overview."""
import os
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

import httpx

from . import db, security

XAI_BASE = 'https://management-api.x.ai/v1/billing/teams'


def xai_usage():
    if urlsplit(security.credential('LLM_API_BASE')).hostname != 'api.x.ai':
        return {'state': 'unsupported'}

    team = os.getenv('XAI_TEAM_ID', '').strip()
    key = os.getenv('XAI_MANAGEMENT_KEY', '').strip()
    if not key or not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', team):
        return {'state': 'unconfigured'}

    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = {'state': 'unavailable', 'month': start.strftime('%Y-%m'), 'spendUsd': None, 'balanceUsd': None}
    if os.getenv('NOHENTAI_DISABLE_UPSTREAM') == '1':
        return result
    payload = {'analyticsRequest': {
        'timeRange': {'startTime': start.strftime('%Y-%m-%d %H:%M:%S'),
                      'endTime': now.strftime('%Y-%m-%d %H:%M:%S'), 'timezone': 'Etc/GMT'},
        'timeUnit': 'TIME_UNIT_DAY',
        'values': [{'name': 'usd', 'aggregation': 'AGGREGATION_SUM'}],
        'groupBy': [],
        'filters': [],
    }}
    errors = (httpx.HTTPError, ValueError, TypeError, KeyError, IndexError, AttributeError, InvalidOperation)
    with httpx.Client(timeout=4, follow_redirects=False, headers={'Authorization': f'Bearer {key}'}) as client:
        try:
            response = client.post(f'{XAI_BASE}/{team}/usage', json=payload).raise_for_status().json()
            if response.get('limitReached') is False:
                cost = sum(
                    (Decimal(str(point['values'][0])) for series in response['timeSeries']
                     for point in series['dataPoints']),
                    Decimal(0),
                )
                if cost.is_finite():
                    result['spendUsd'] = str(cost)
        except errors:
            pass
        try:
            payload = client.get(f'{XAI_BASE}/{team}/prepaid/balance').raise_for_status().json()
            # The provider ledger represents prepaid credits as negative USD cents.
            cents = int(payload['total']['val'])
            result['balanceUsd'] = str(max(0, -cents) / Decimal(100))
        except errors:
            pass
    if result['spendUsd'] is not None or result['balanceUsd'] is not None:
        result.update(state='available', checkedAt=db.now())
    return result
