from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Daily Opportunity Intel"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_timezone: str = ""
    timezone: str = "Asia/Shanghai"

    database_url: str = "sqlite:///./daily_intelligence.db"
    sources_config_path: str = "./config/sources.json"

    daily_run_hour: int = 7
    daily_run_minute: int = 0
    min_final_score: float = 4.8
    max_items_per_report: int = 8

    ai_provider: str = "openai_compatible"
    ai_base_url: str = "https://api.deepseek.com"
    ai_api_key: str = ""
    ai_model: str = "deepseek-v4-flash"
    ai_timeout_seconds: int = 90
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"
    qwen_api_key: str = ""
    qwen_model: str = "qwen-plus"
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"

    feishu_webhook: str = ""
    feishu_webhook_url: str = ""
    feishu_secret: str = ""
    feishu_max_message_chars: int = 3500
    push_dry_run: bool = False

    email_host: str = ""
    email_port: int = 0
    email_user: str = ""
    email_password: str = ""
    email_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_to: str = ""
    smtp_use_tls: bool = True

    proxy_url: str = ""
    log_file: str = Field(default="./logs/app.log")

    def model_post_init(self, __context) -> None:
        if self.app_timezone:
            self.timezone = self.app_timezone

        if self.deepseek_api_key and not self.ai_api_key:
            self.ai_api_key = self.deepseek_api_key
            self.ai_base_url = "https://api.deepseek.com"
            self.ai_model = self.deepseek_model
        elif self.qwen_api_key and not self.ai_api_key:
            self.ai_api_key = self.qwen_api_key
            self.ai_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
            self.ai_model = self.qwen_model
        elif self.openai_api_key and not self.ai_api_key:
            self.ai_api_key = self.openai_api_key
            self.ai_base_url = "https://api.openai.com/v1"
            self.ai_model = self.openai_model or self.ai_model

        if self.feishu_webhook and not self.feishu_webhook_url:
            self.feishu_webhook_url = self.feishu_webhook

        if self.email_host and not self.smtp_host:
            self.smtp_host = self.email_host
        if self.email_port and self.smtp_port == 587:
            self.smtp_port = self.email_port
        if self.email_user and not self.smtp_username:
            self.smtp_username = self.email_user
        if self.email_password and not self.smtp_password:
            self.smtp_password = self.email_password
        if self.email_user and not self.smtp_from:
            self.smtp_from = self.email_user
        if self.email_to and not self.smtp_to:
            self.smtp_to = self.email_to

    @property
    def sources_path(self) -> Path:
        return Path(self.sources_config_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()
