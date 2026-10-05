"""관리자 알림 메일 — 회원가입 시 승인 요청을 보낸다.

SMTP 설정(SMTP_USER/SMTP_PASSWORD)이나 수신자(ADMIN_NOTIFY_EMAILS)가 비어 있으면
조용히 건너뛴다. 가입 응답을 보낸 뒤 BackgroundTasks로 실행되므로, 메일 서버가
느리거나 실패해도 가입 자체에는 영향이 없다 (실패는 로그로만 남긴다).
"""

import html
import logging
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from common.config import get_settings

# uvicorn 로거에 붙여야 docker logs에 INFO까지 보인다.
logger = logging.getLogger("uvicorn.error")

# 한국은 서머타임이 없어서 고정 오프셋으로 충분하다 (slim 이미지엔 tzdata가 없다).
KST = timezone(timedelta(hours=9), "KST")

ACCENT = "#10b981"
INK = "#0f1115"


def format_kst(dt: datetime) -> str:
    """2026-10-05T05:03:22Z -> '2026년 10월 5일 14시 03분 22초'"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    k = dt.astimezone(KST)
    return f"{k.year}년 {k.month}월 {k.day}일 {k.hour:02d}시 {k.minute:02d}분 {k.second:02d}초"


def _signup_html(email: str, signed_up_at: str, admin_url: str) -> str:
    e, t, url = html.escape(email), html.escape(signed_up_at), html.escape(admin_url, quote=True)
    # 메일 클라이언트(특히 Gmail/Outlook)는 <style>과 flex를 제대로 지원하지 않아서
    # 테이블 + 인라인 스타일로만 짠다.
    return f"""\
<!DOCTYPE html>
<html lang="ko">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;">
  <div style="display:none;max-height:0;overflow:hidden;opacity:0;">{e} 님이 가입했습니다. 승인을 기다리고 있어요.</div>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f4f6;padding:32px 16px;">
    <tr><td align="center">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
             style="max-width:520px;background:#ffffff;border-radius:16px;overflow:hidden;
                    font-family:-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',sans-serif;">
        <tr><td style="background:{INK};padding:22px 28px;">
          <span style="color:#6ee7b7;font-size:18px;font-weight:700;letter-spacing:.3px;">AI Voice Cover</span>
          <span style="color:#9ca3af;font-size:13px;margin-left:8px;">관리자 알림</span>
        </td></tr>

        <tr><td style="padding:32px 28px 8px;">
          <div style="display:inline-block;background:#ecfdf5;color:#047857;font-size:12px;font-weight:600;
                      padding:4px 10px;border-radius:999px;">승인 대기</div>
          <h1 style="margin:14px 0 8px;font-size:22px;line-height:1.4;color:#111827;">새 회원이 가입했어요</h1>
          <p style="margin:0;font-size:15px;line-height:1.6;color:#4b5563;">
            아래 회원이 가입을 신청했습니다. 승인해야 로그인할 수 있어요.
          </p>
        </td></tr>

        <tr><td style="padding:20px 28px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0"
                 style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:12px;">
            <tr><td style="padding:16px 18px;border-bottom:1px solid #e5e7eb;">
              <div style="font-size:12px;color:#6b7280;margin-bottom:4px;">아이디</div>
              <div style="font-size:16px;font-weight:600;color:#111827;word-break:break-all;">{e}</div>
            </td></tr>
            <tr><td style="padding:16px 18px;">
              <div style="font-size:12px;color:#6b7280;margin-bottom:4px;">가입 일시 (한국 시간)</div>
              <div style="font-size:16px;font-weight:600;color:#111827;">{t}</div>
            </td></tr>
          </table>
        </td></tr>

        <tr><td align="center" style="padding:8px 28px 32px;">
          <a href="{url}" target="_blank"
             style="display:inline-block;background:{ACCENT};color:#ffffff;text-decoration:none;font-size:15px;
                    font-weight:700;padding:14px 28px;border-radius:10px;">관리자 페이지에서 승인하기</a>
          <p style="margin:14px 0 0;font-size:12px;color:#9ca3af;word-break:break-all;">
            버튼이 안 눌리면 이 주소로 들어가세요: <a href="{url}" style="color:#6b7280;">{url}</a>
          </p>
        </td></tr>

        <tr><td style="background:#f9fafb;padding:16px 28px;border-top:1px solid #e5e7eb;">
          <p style="margin:0;font-size:12px;line-height:1.6;color:#9ca3af;">
            이 메일은 AI Voice Cover 회원가입 시 자동으로 발송됩니다.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _signup_text(email: str, signed_up_at: str, admin_url: str) -> str:
    return (
        "[AI Voice Cover] 새 회원가입 승인 요청\n\n"
        f"아이디: {email}\n"
        f"가입 일시: {signed_up_at} (한국 시간)\n\n"
        "승인해야 로그인할 수 있어요. 아래 관리자 페이지에서 승인해 주세요.\n"
        f"{admin_url}\n"
    )


def build_signup_message(email: str, created_at: datetime) -> EmailMessage | None:
    settings = get_settings()
    recipients = settings.admin_notify_email_list
    if not recipients:
        return None

    signed_up_at = format_kst(created_at)
    admin_url = settings.public_web_url.rstrip("/") + "/admin"

    msg = EmailMessage()
    msg["Subject"] = f"[AI Voice Cover] {email} 님이 가입했어요 — 승인해 주세요"
    msg["From"] = formataddr(("AI Voice Cover 알림", settings.smtp_from or settings.smtp_user))
    msg["To"] = ", ".join(recipients)
    msg["Message-ID"] = make_msgid(domain="ai-voice-cover.local")
    msg.set_content(_signup_text(email, signed_up_at, admin_url))
    msg.add_alternative(_signup_html(email, signed_up_at, admin_url), subtype="html")
    return msg


def send_signup_notification(email: str, created_at: datetime) -> None:
    settings = get_settings()
    if not (settings.smtp_user and settings.smtp_password):
        logger.warning("SMTP 설정이 없어 가입 알림 메일을 건너뜁니다 (%s)", email)
        return
    msg = build_signup_message(email, created_at)
    if msg is None:
        return

    try:
        context = ssl.create_default_context()
        if settings.smtp_port == 465:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20) as smtp:
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
                smtp.starttls(context=context)
                smtp.login(settings.smtp_user, settings.smtp_password)
                smtp.send_message(msg)
        logger.info("가입 알림 메일 발송: %s -> %s", email, msg["To"])
    except Exception:
        logger.exception("가입 알림 메일 발송 실패 (%s)", email)
