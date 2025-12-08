"""Notification integrations."""

from ci_guardian.notifications.slack import send_failure_notification, send_pr_notification

__all__ = ["send_failure_notification", "send_pr_notification"]
