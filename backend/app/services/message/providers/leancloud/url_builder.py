"""LeanCloud webhook URL builder."""

WEBHOOK_PATH = "/api/v1/leancloud/webhook"


def build_leancloud_webhook_url(api_base_url: str, webhook_token: str) -> str:
    """Build the LeanCloud webhook URL for console configuration."""
    base_url = api_base_url.rstrip("/")
    return f"{base_url}{WEBHOOK_PATH}/{webhook_token}"
