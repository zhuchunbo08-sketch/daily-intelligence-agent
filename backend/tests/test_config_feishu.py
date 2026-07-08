import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import Settings


def test_feishu_webhook_accepts_token_only_value():
    settings = Settings(_env_file=None, feishu_webhook_url="abc123")

    assert settings.feishu_webhook_url == "https://open.feishu.cn/open-apis/bot/v2/hook/abc123"
    assert settings.feishu_webhook_source == "FEISHU_WEBHOOK_URL"


def test_feishu_webhook_accepts_host_path_without_scheme():
    settings = Settings(_env_file=None, feishu_webhook_url="open.feishu.cn/open-apis/bot/v2/hook/abc123")

    assert settings.feishu_webhook_url == "https://open.feishu.cn/open-apis/bot/v2/hook/abc123"


def test_feishu_webhook_takes_priority_over_legacy_url():
    settings = Settings(
        _env_file=None,
        feishu_webhook="https://open.feishu.cn/open-apis/bot/v2/hook/valid-webhook",
        feishu_webhook_url="wrong-token",
    )

    assert settings.feishu_webhook_url == "https://open.feishu.cn/open-apis/bot/v2/hook/valid-webhook"
    assert settings.feishu_webhook_source == "FEISHU_WEBHOOK"
