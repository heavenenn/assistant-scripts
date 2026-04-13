"""
tools/mail.py
郵件工具：寄信、收信同步
"""

import os
import imaplib
import email as email_lib
import re
import smtplib
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.mime.image import MIMEImage
from email.header import decode_header
from email import encoders
from datetime import datetime

SENDER_EMAIL = "weiweiclaw@gmail.com"
CRED_FILE    = r"C:\Users\heave\.openclaw\weiweiclaw_credentials.txt"
MAIL_DIR     = r"C:\Users\heave\OneDrive\文件\薇薇\mail"
UID_RECORD   = os.path.join(MAIL_DIR, ".synced_uids")


# ── 憑證 ─────────────────────────────────────────────────────────────────────

def _read_app_password() -> str:
    try:
        with open(CRED_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "email-password" in line:
                    line = line.replace("：", ":")
                    pwd = line.split(":")[-1].strip()
                    if pwd:
                        return pwd
    except OSError as e:
        raise RuntimeError(f"無法讀取憑證檔：{e}") from e
    raise RuntimeError("憑證檔中找不到 email-password")


# ── 郵件建構輔助 ─────────────────────────────────────────────────────────────

def _build_attachment(path: str) -> MIMEBase:
    mime_type, _ = mimetypes.guess_type(path)
    main_type, sub_type = (mime_type.split("/", 1) if mime_type
                           else ("application", "octet-stream"))
    part = MIMEBase(main_type, sub_type)
    with open(path, "rb") as f:
        part.set_payload(f.read())
    encoders.encode_base64(part)
    part.add_header("Content-Disposition", "attachment",
                    filename=os.path.basename(path))
    return part


def _build_inline_image(path: str, cid: str) -> MIMEImage:
    mime_type, _ = mimetypes.guess_type(path)
    if mime_type and "/" in mime_type:
        sub_type = mime_type.split("/")[1]
    else:
        ext = os.path.splitext(path)[1].lower()
        sub_type = "png" if ext == ".png" else "jpeg"

    with open(path, "rb") as f:
        img_data = f.read()

    img_part = MIMEImage(img_data, _subtype=sub_type)
    img_part.add_header("Content-ID", f"<{cid}>")
    img_part.add_header("Content-Disposition", "inline")
    return img_part


# ── 寄信 ─────────────────────────────────────────────────────────────────────

def send_mail(
    to_email: str,
    subject: str,
    content: str,
    attachment_path: str | None = None,
    is_html: bool = False,
    inline_image_paths: list[str] | None = None,
) -> dict:
    """
    寄送郵件。
    回傳統一格式 dict：{"status": "success"/"error", ...}
    """
    inline_image_paths = inline_image_paths or []

    # 驗證附件路徑
    if attachment_path and not os.path.exists(attachment_path):
        raise FileNotFoundError(f"附件不存在：{attachment_path}")

    for p in inline_image_paths:
        if not os.path.exists(p):
            raise FileNotFoundError(f"內嵌圖片不存在：{p}")

    app_password = _read_app_password()
    normalized_content = content.replace("\\n", "\n")

    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"]    = SENDER_EMAIL
    msg["To"]      = to_email

    related = MIMEMultipart("related")
    mime_type = "html" if is_html else "plain"
    related.attach(MIMEText(normalized_content, mime_type, "utf-8"))

    for idx, img_path in enumerate(inline_image_paths):
        related.attach(_build_inline_image(img_path, f"img{idx}"))

    msg.attach(related)

    if attachment_path and str(attachment_path).lower() not in ("", "none"):
        msg.attach(_build_attachment(attachment_path))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER_EMAIL, app_password)
        server.send_message(msg)

    parts = []
    if attachment_path:
        parts.append("attachment")
    if inline_image_paths:
        parts.append(f"{len(inline_image_paths)} inline image(s)")

    return {
        "message": "Mail sent" + (f" with {', '.join(parts)}" if parts else ""),
        "to": to_email,
        "subject": subject,
    }


# ── 收信同步 ─────────────────────────────────────────────────────────────────

def _load_synced_uids() -> set[str]:
    if not os.path.exists(UID_RECORD):
        return set()
    with open(UID_RECORD, "r", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _save_synced_uid(uid: str) -> None:
    with open(UID_RECORD, "a", encoding="utf-8") as f:
        f.write(uid + "\n")


def _decode_mime_header(value: str | None) -> str:
    if not value:
        return "(no subject)"
    parts = []
    for fragment, charset in decode_header(value):
        if isinstance(fragment, bytes):
            parts.append(fragment.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(fragment)
    return "".join(parts)


def _safe_name(name: str, max_len: int = 50) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|]', "_", name).strip().strip(".")
    return cleaned[:max_len] or "unnamed"


def _extract_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if (part.get_content_type() == "text/plain"
                    and part.get_content_disposition() != "attachment"):
                payload = part.get_payload(decode=True)
                charset = part.get_content_charset() or "utf-8"
                return payload.decode(charset, errors="replace") if payload else ""
    else:
        payload = msg.get_payload(decode=True)
        charset = msg.get_content_charset() or "utf-8"
        return payload.decode(charset, errors="replace") if payload else ""
    return ""


def _save_attachments(msg, dest_dir: str) -> list[str]:
    saved = []
    for part in msg.walk():
        disposition = part.get_content_disposition() or ""
        filename = part.get_filename()
        if filename:
            filename = _decode_mime_header(filename)
        is_attachment = (disposition == "attachment") or (
            filename and part.get_content_type()
            not in ("text/plain", "text/html")
        )
        if not is_attachment or not filename:
            continue
        payload = part.get_payload(decode=True)
        if not payload:
            continue
        safe = _safe_name(filename, max_len=100)
        base, ext = os.path.splitext(safe)
        candidate, counter = safe, 1
        while os.path.exists(os.path.join(dest_dir, candidate)):
            candidate = f"{base}_{counter}{ext}"
            counter += 1
        with open(os.path.join(dest_dir, candidate), "wb") as f:
            f.write(payload)
        saved.append(candidate)
    return saved


def sync_mail(reset: bool = False) -> dict:
    """
    同步 Gmail 收件匣到本地。
    reset=True 會清除 UID 記錄，重新下載所有信件。
    """
    os.makedirs(MAIL_DIR, exist_ok=True)

    if reset and os.path.exists(UID_RECORD):
        os.remove(UID_RECORD)

    passwd = _read_app_password()
    synced_ids = _load_synced_uids()

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    try:
        mail.login(SENDER_EMAIL, passwd)
        mail.select("inbox")

        status, messages = mail.uid("search", None, "ALL")
        if status != "OK":
            raise RuntimeError("搜尋郵件失敗")

        all_uids = messages[0].split()
        new_uids = [u for u in all_uids if u.decode() not in synced_ids]
        saved_count = 0

        for uid_bytes in new_uids:
            uid = uid_bytes.decode()
            status, msg_data = mail.uid("fetch", uid_bytes, "(RFC822)")
            if status != "OK":
                continue

            for response in msg_data:
                if not isinstance(response, tuple):
                    continue
                msg     = email_lib.message_from_bytes(response[1])
                subject = _decode_mime_header(msg["Subject"])
                from_   = _decode_mime_header(msg["From"])
                date    = msg["Date"] or ""
                body    = _extract_body(msg)

                ts          = datetime.now().strftime("%Y%m%d_%H%M%S")
                folder_name = f"{ts}_{_safe_name(subject)}"
                mail_subdir = os.path.join(MAIL_DIR, folder_name)
                os.makedirs(mail_subdir, exist_ok=True)

                with open(os.path.join(mail_subdir, "mail.txt"), "w",
                          encoding="utf-8") as f:
                    f.write(f"From: {from_}\nSubject: {subject}\n"
                            f"Date: {date}\n\n{body}")

                attachments = _save_attachments(msg, mail_subdir)
                _save_synced_uid(uid)
                saved_count += 1

    finally:
        try:
            mail.close()
        except Exception:
            pass
        mail.logout()

    return {
        "synced": saved_count,
        "total_on_server": len(all_uids),
        "mail_dir": MAIL_DIR,
    }
