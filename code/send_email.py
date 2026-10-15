# -*- coding: utf-8 -*-
"""
通过 QQ 邮箱的 SMTP 把周报发出去。

安全说明（很重要）：
  QQ 邮箱不允许用登录密码发信，必须用"授权码"。
  授权码只放在 GitHub 仓库的 Secret 里（名字叫 QQMAIL），
  绝对不要写进这个文件、也不要发在聊天里。
"""

from __future__ import annotations

import os
import smtplib
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr


def send_html_email(subject: str, html_body: str, sender: str, receiver: str, dry_run: bool = False) -> None:
    password = os.getenv("QQMAIL", "").strip()
    host = os.getenv("QQ_SMTP_HOST", "smtp.qq.com").strip()
    port = int(os.getenv("QQ_SMTP_PORT", "465"))

    if dry_run:
        print(f"[邮件] 演练模式：本该发送给 {receiver}，主题《{subject}》，正文 {len(html_body)} 字符")
        return

    if not password:
        raise RuntimeError(
            "没有读到 QQMAIL。请到仓库 Settings → Secrets and variables → Actions "
            "里添加名为 QQMAIL 的 Secret（内容是 QQ 邮箱授权码）。"
        )

    message = MIMEMultipart("alternative")
    message["From"] = formataddr((str(Header("AI 科研周报", "utf-8")), sender))
    message["To"] = receiver
    message["Subject"] = Header(subject, "utf-8")
    message.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP_SSL(host, port, timeout=60) as server:
        server.login(sender, password)
        server.sendmail(sender, [receiver], message.as_string())
    print(f"[邮件] 已发送到 {receiver}")
