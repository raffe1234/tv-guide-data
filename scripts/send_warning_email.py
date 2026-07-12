from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path


def _missing_environment_variables(names: tuple[str, ...]) -> list[str]:
    return [name for name in names if not os.environ.get(name)]


def _send_message(message: EmailMessage) -> None:
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT") or "587")
    username = os.environ["SMTP_USERNAME"]
    password = os.environ["SMTP_PASSWORD"]
    security = (os.environ.get("SMTP_SECURITY") or "starttls").lower()
    context = ssl.create_default_context()

    if security == "ssl":
        with smtplib.SMTP_SSL(host, port, context=context, timeout=30) as server:
            server.login(username, password)
            server.send_message(message)
        return

    if security != "starttls":
        raise ValueError("SMTP_SECURITY must be either 'starttls' or 'ssl'")

    with smtplib.SMTP(host, port, timeout=30) as server:
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(username, password)
        server.send_message(message)


def main() -> int:
    required = (
        "SMTP_HOST",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "GUIDE_ALERT_TO",
        "WARNING_FILE",
    )
    missing = _missing_environment_variables(required)
    if missing:
        print(
            "::warning title=TV guide email skipped::Missing repository secrets or "
            f"environment variables: {', '.join(missing)}"
        )
        return 0

    warning_path = Path(os.environ["WARNING_FILE"])
    if not warning_path.is_file():
        print(
            f"::warning title=TV guide email skipped::Warning file does not exist: {warning_path}"
        )
        return 0

    warnings = warning_path.read_text(encoding="utf-8").strip()
    if not warnings:
        return 0

    repository = os.environ.get("GITHUB_REPOSITORY", "tv-guide-data")
    run_url = os.environ.get("RUN_URL", "")
    sender = os.environ.get("SMTP_FROM") or os.environ["SMTP_USERNAME"]

    message = EmailMessage()
    message["Subject"] = f"TV guide coverage warning: {repository}"
    message["From"] = sender
    message["To"] = os.environ["GUIDE_ALERT_TO"]
    message.set_content(
        "The TV guide was published, but one or more coverage checks produced warnings.\n\n"
        f"{warnings}\n\n"
        f"Workflow run: {run_url}\n"
    )

    try:
        _send_message(message)
    except (OSError, smtplib.SMTPException, ValueError) as error:
        print(f"::warning title=TV guide email failed::{error}")
        return 0

    print("Coverage warning email sent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
