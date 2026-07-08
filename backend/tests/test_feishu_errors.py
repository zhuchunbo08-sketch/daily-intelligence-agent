import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.notifications.feishu import FeishuNotifier


def test_invalid_feishu_token_error_points_to_primary_config():
    notifier = FeishuNotifier()
    notifier.settings.feishu_webhook_source = "FEISHU_WEBHOOK"

    with pytest.raises(RuntimeError) as exc:
        notifier._raise_for_feishu_error(
            {"code": 19001, "msg": "param invalid: incoming webhook access token invalid"}
        )

    message = str(exc.value)
    assert "incoming webhook access token invalid" in message
    assert "FEISHU_WEBHOOK" in message
    assert "open-apis/bot/v2/hook" not in message
