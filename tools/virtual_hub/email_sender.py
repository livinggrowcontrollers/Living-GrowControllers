import os
import json
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage


class EmailSender:
    """
    Handles background notification email dispatch via SMTP for Cloudflare Tunnel URLs.
    Guarantees no unhandled exceptions fail the host application.
    """

    def __init__(self, config_path="email_config.json", log_callback=None):
        self.log_callback = log_callback
        
        # Determine robust absolute path to email_config.json relative to this file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(config_path):
            self.config_path = os.path.join(base_dir, config_path)
        else:
            self.config_path = config_path

    def _log(self, message):
        if self.log_callback:
            self.log_callback(f"[E-Mail] {message}")
        else:
            print(f"[E-Mail] {message}")

    def _load_config(self):
        if not os.path.exists(self.config_path):
            self._log(f"Konfigurationsdatei '{os.path.basename(self.config_path)}' fehlt. Mail-Versand übersprungen.")
            return None

        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                config = json.load(f)
                
            required_keys = ["smtp_server", "smtp_port", "sender_email", "sender_password", "recipient_email"]
            for key in required_keys:
                if key not in config:
                    self._log(f"Fehlerhafte Konfiguration: Schlüssel '{key}' fehlt in {os.path.basename(self.config_path)}.")
                    return None
            return config
        except json.JSONDecodeError as e:
            self._log(f"JSON-Syntaxfehler in '{os.path.basename(self.config_path)}': {str(e)}")
            return None
        except Exception as e:
            self._log(f"Fehler beim Lesen von '{os.path.basename(self.config_path)}': {str(e)}")
            return None

    def send_tunnel_notification(self, tunnel_url, device_id="unknown"):
        """
        Sends an email containing the updated Cloudflare tunnel address.
        Catches all SMTP & SSL errors safely.
        """
        config = self._load_config()
        if not config:
            return False

        if not config.get("sender_password"):
            self._log("Passwort in 'email_config.json' ist leer. Mailversand nicht möglich.")
            return False

        smtp_server = config.get("smtp_server", "smtp.gmail.com")
        smtp_port = int(config.get("smtp_port", 587))
        sender_email = config.get("sender_email")
        sender_password = config.get("sender_password")
        recipient_email = config.get("recipient_email", "thefreak1980@gmail.com")

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        device_str = device_id if device_id else "unknown"

        msg = EmailMessage()
        msg["Subject"] = "🌱 GrowMaster Tunnel aktualisiert"
        msg["From"] = sender_email
        msg["To"] = recipient_email

        email_content = (
            f"GrowMaster Tunnel\n\n"
            f"Gerät:\n{device_str}\n\n"
            f"Tunnel-Adresse:\n\n"
            f"{tunnel_url}\n\n"
            f"Zeit:\n"
            f"{now_str}\n"
        )
        msg.set_content(email_content)

        try:
            context = ssl.create_default_context()
            self._log(f"Verbinde mit SMTP-Server {smtp_server}:{smtp_port}...")
            
            with smtplib.SMTP(smtp_server, smtp_port, timeout=10.0) as server:
                server.ehlo()
                server.starttls(context=context)
                server.ehlo()
                
                try:
                    server.login(sender_email, sender_password)
                except smtplib.SMTPAuthenticationError as e:
                    self._log(f"Login fehlgeschlagen (Authentifizierungsfehler): {str(e)}")
                    return False
                except Exception as e:
                    self._log(f"Login fehlgeschlagen: {str(e)}")
                    return False

                server.send_message(msg)
                self._log(f"E-Mail mit Tunnel-Adresse erfolgreich an {recipient_email} gesendet.")
                return True

        except smtplib.SMTPConnectError as e:
            self._log(f"SMTP-Verbindung fehlgeschlagen: {str(e)}")
        except smtplib.SMTPException as e:
            self._log(f"SMTP-Fehler beim Mailversand: {str(e)}")
        except Exception as e:
            self._log(f"Unerwarteter Fehler beim Mailversand: {str(e)}")

        return False