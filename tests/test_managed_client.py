from unittest.mock import Mock

import pytest

from b17_parser.http import AccessError, BudgetReached, FetchError, ManagedClient
from b17_parser.pacing import AccessGate


class Clock:
    def __init__(self):
        self.now = 10000
    def time(self):
        return self.now
    def sleep(self, seconds):
        self.now += seconds


def gate(path, clock):
    return AccessGate(path, delay=15, jitter=0, clock=clock.time, sleep=clock.sleep)


def test_block_prevents_next_client_from_touching_network(tmp_path):
    clock = Clock()
    denied = Mock(last_url='https://www.b17.ru/test/')
    denied.get.side_effect = AccessError('HTTP 503')
    client = ManagedClient(denied, gate(tmp_path / 'access.json', clock))
    with pytest.raises(AccessError):
        client.get('https://www.b17.ru/test/')
    another = Mock()
    with pytest.raises(FetchError, match='cooldown'):
        ManagedClient(another, gate(tmp_path / 'access.json', clock)).get('https://www.b17.ru/other/')
    another.get.assert_not_called()


def test_login_expiry_does_not_impose_ip_cooldown(tmp_path):
    clock = Clock()
    denied = Mock()
    denied.get.side_effect = AccessError('B17 login is absent or expired; authenticated collection stopped')
    client = ManagedClient(denied, gate(tmp_path / 'access.json', clock))
    with pytest.raises(AccessError):
        client.get('https://www.b17.ru/test/')
    assert client.gate._read()['cooldown_until'] == 0


def test_budget_stops_before_new_request(tmp_path):
    clock = Clock()
    transport = Mock(last_url='https://www.b17.ru/test/')
    transport.get.return_value = 'HTML'
    client = ManagedClient(transport, gate(tmp_path / 'access.json', clock), max_requests=1)
    assert client.get('https://www.b17.ru/test/') == 'HTML'
    with pytest.raises(BudgetReached):
        client.get('https://www.b17.ru/test/')
    assert transport.get.call_count == 1


def test_captcha_takes_precedence_over_expired_login_and_records_cooldown(tmp_path):
    from b17_parser.http import validate_page
    clock = Clock()
    transport = Mock()
    transport.get.side_effect = lambda url: validate_page('<input name=captcha>', url, require_login=True)
    client = ManagedClient(transport, gate(tmp_path / 'access.json', clock))
    with pytest.raises(AccessError, match='CAPTCHA'):
        client.get('https://www.b17.ru/test/')
    assert client.gate._read()['cooldown_until'] > clock.time()
