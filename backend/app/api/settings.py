from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("")
def get_public_settings():
    settings = get_settings()
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "timezone": settings.timezone,
        "daily_run_hour": settings.daily_run_hour,
        "daily_run_minute": settings.daily_run_minute,
        "database_url": settings.database_url,
        "sources_config_path": settings.sources_config_path,
        "min_final_score": settings.min_final_score,
        "max_items_per_report": settings.max_items_per_report,
        "ai_provider": settings.ai_provider,
        "ai_base_url": settings.ai_base_url,
        "ai_model": settings.ai_model,
        "ai_configured": bool(settings.ai_api_key),
        "feishu_configured": bool(settings.feishu_webhook_url),
        "feishu_secret_configured": bool(settings.feishu_secret),
        "email_configured": bool(settings.smtp_host and settings.smtp_to),
        "push_dry_run": settings.push_dry_run,
        "proxy_configured": bool(settings.proxy_url),
    }
