"""
Servicio para envío de emails
Compatible con el backend .NET
"""
import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List
from pathlib import Path

from config import get_settings
from core.logging import logger


class EmailService:
    """Servicio para envío de emails vía SMTP"""

    def __init__(self):
        self.settings = get_settings()

    async def send_obr_success_email(
        self,
        to_email: str,
        vendor_name: str,
        csv_file_path: str
    ) -> bool:
        """
        Envía email de éxito con archivo CSV adjunto
        """
        subject = f"OBR Vendor {vendor_name} generated"
        body = self._get_success_template()

        return await self._send_email_with_attachment(
            to_email=to_email,
            subject=subject,
            body=body,
            attachment_path=csv_file_path,
            attachment_name=Path(csv_file_path).name
        )

    async def send_obr_failure_email(
        self,
        to_email: str,
        vendor_name: str,
        error_message: Optional[str] = None
    ) -> bool:
        """
        Envía email de fallo en procesamiento
        """
        subject = f"OBR Vendor {vendor_name} Failed"
        body = self._get_failure_template(error_message)

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            body=body
        )

    async def send_obr_error_email(
        self,
        to_email: str,
        vendor_name: str,
        error_details: str
    ) -> bool:
        """
        Envía email de error técnico
        """
        subject = f"OBR Vendor {vendor_name} Error generating CSV"
        body = self._get_error_template(error_details)

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            body=body
        )

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str
    ) -> bool:
        """Envía email simple sin adjuntos"""
        try:
            message = MIMEMultipart()
            message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            message["To"] = to_email
            message["Subject"] = subject

            message.attach(MIMEText(body, "html"))

            await aiosmtplib.send(
                message,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.settings.smtp_password,
                start_tls=True
            )

            logger.info(f"Email enviado exitosamente a {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email a {to_email}: {e}")
            return False

    async def _send_email_with_attachment(
        self,
        to_email: str,
        subject: str,
        body: str,
        attachment_path: str,
        attachment_name: str
    ) -> bool:
        """Envía email con archivo adjunto"""
        try:
            message = MIMEMultipart()
            message["From"] = f"{self.settings.smtp_from_name} <{self.settings.smtp_from_email}>"
            message["To"] = to_email
            message["Subject"] = subject

            message.attach(MIMEText(body, "html"))

            # Adjuntar archivo
            with open(attachment_path, "rb") as file:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(file.read())
                encoders.encode_base64(part)
                part.add_header(
                    "Content-Disposition",
                    f"attachment; filename= {attachment_name}"
                )
                message.attach(part)

            await aiosmtplib.send(
                message,
                hostname=self.settings.smtp_host,
                port=self.settings.smtp_port,
                username=self.settings.smtp_username,
                password=self.settings.smtp_password,
                start_tls=True
            )

            logger.info(f"Email con adjunto enviado exitosamente a {to_email}")
            return True

        except Exception as e:
            logger.error(f"Error enviando email con adjunto a {to_email}: {e}")
            return False

    @staticmethod
    def _get_success_template() -> str:
        """Template HTML para email de éxito - Compatible con backend .NET"""
        return EmailService._load_template("You can download the OBR Vendor File.")

    @staticmethod
    def _get_failure_template(error_message: Optional[str] = None) -> str:
        """Template HTML para email de fallo - Compatible con backend .NET"""
        message = "Please try again, check the master file and vendor file"
        if error_message:
            message = f"{message}<br><br><strong>Error:</strong> {error_message}"
        return EmailService._load_template(message)

    @staticmethod
    def _get_error_template(error_details: str) -> str:
        """Template HTML para email de error técnico - Compatible con backend .NET"""
        message = f"Exception Message: {error_details}"
        return EmailService._load_template(message)

    @staticmethod
    def _load_template(message: str) -> str:
        """
        Carga el template HTML y reemplaza [message] con el contenido
        Compatible con Templates.GetMessageTemplate() del backend .NET
        """
        try:
            template_path = Path(__file__).parent.parent / "templates" / "email_template.html"
            with open(template_path, "r", encoding="utf-8") as file:
                template = file.read()
                return template.replace("[message]", message)
        except Exception as e:
            logger.warning(f"No se pudo cargar template HTML: {e}. Usando mensaje simple.")
            # Fallback si no existe el template
            return f"""
            <html>
            <body>
                <p>{message}</p>
                <p>Thank you,<br>Apollo OBR System</p>
            </body>
            </html>
            """
