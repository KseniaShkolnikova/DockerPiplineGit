# MPTed_base/utils/email_sender.py
import logging
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string
from django.conf import settings
import smtplib
import ssl
from datetime import datetime


logger = logging.getLogger(__name__)

def send_student_credentials_email(student_email, username, password, student_name, login_url):
    """
    Отправляет HTML письмо с учетными данными ученику
    """
    try:
        logger.info(f"🔄 Попытка отправки email ученику {student_name} ({student_email})")
        
        subject = f'Ваши учетные данные для входа в образовательную систему'
        
        # Сначала попробуем найти HTML шаблон
        try:
            html_content = render_to_string('emails/student_welcome.html', {
                'student_name': student_name,
                'username': username,
                'password': password,
                'login_url': login_url,
            })
            logger.debug("✅ HTML шаблон успешно загружен")
        except Exception as template_error:
            logger.warning(f"⚠️ Не удалось загрузить HTML шаблон: {template_error}")
            # Если шаблон не найден, создаем простое HTML
            html_content = f"""
            <html>
            <body>
                <h2>Здравствуйте, {student_name}!</h2>
                <p>Ваша учетная запись в образовательной системе была успешно создана.</p>
                <p><strong>Ваши данные для входа:</strong></p>
                <ul>
                    <li><strong>Логин:</strong> {username}</li>
                    <li><strong>Пароль:</strong> {password}</li>
                </ul>
                <p><a href="{login_url}">Войти в систему</a></p>
                <p>После первого входа рекомендуется сменить пароль.</p>
            </body>
            </html>
            """
        
        # Текстовая версия
        text_content = f"""
        Здравствуйте, {student_name}!
        
        Ваша учетная запись в образовательной системе была успешно создана.
        
        Ваши данные для входа:
        • Логин: {username}
        • Пароль: {password}
        • Ссылка для входа: {login_url}
        
        После первого входа рекомендуется сменить пароль.
        Никому не сообщайте свои учетные данные.
        
        С уважением,
        Администрация образовательной системы
        """
        
        # Создаем email сообщение
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[student_email],
        )
        
        # Прикрепляем HTML версию
        email.attach_alternative(html_content, "text/html")
        
        # Пытаемся отправить с детальным логированием
        try:
            # Проверяем настройки перед отправкой
            logger.debug(f"📧 Параметры отправки:")
            logger.debug(f"  From: {settings.DEFAULT_FROM_EMAIL}")
            logger.debug(f"  To: {student_email}")
            logger.debug(f"  Subject: {subject}")
            logger.debug(f"  Backend: {settings.EMAIL_BACKEND}")
            
            # Отправляем (fail_silently=False, чтобы видеть ошибки)
            result = email.send(fail_silently=False)
            
            if result == 1:
                logger.info(f"✅ Email успешно отправлен ученику {student_name} ({student_email})")
                return True
            else:
                logger.warning(f"⚠️ Email не отправлен ученику {student_email}. Результат: {result}")
                return False
                
        except smtplib.SMTPAuthenticationError as auth_error:
            logger.error(f"❌ Ошибка аутентификации SMTP: {auth_error}")
            logger.error("Проверьте логин и пароль в настройках Gmail")
            return False
            
        except smtplib.SMTPException as smtp_error:
            logger.error(f"❌ Ошибка SMTP: {smtp_error}")
            return False
            
        except ssl.SSLError as ssl_error:
            logger.error(f"❌ Ошибка SSL: {ssl_error}")
            logger.error("Попробуйте изменить порт на 465 и использовать EMAIL_USE_SSL = True")
            return False
            
        except Exception as send_error:
            logger.error(f"❌ Ошибка при отправке email: {send_error}")
            logger.exception("Детали ошибки:")
            return False
        
    except Exception as e:
        logger.error(f"❌ Общая ошибка отправки email ученику {student_email}: {str(e)}")
        logger.exception("Трассировка ошибки:")
        return False


def send_account_changes_email(student_email, username, password, student_name, login_url, changes):
    """
    Отправляет письмо об изменениях в учетной записи
    """
    try:
        logger.info(f"🔄 Попытка отправки email об изменениях ученику {student_name} ({student_email})")
        
        subject = f'Изменения в вашей учетной записи'
        
        # Подготовка HTML контента
        html_content = f"""
        <html>
        <body>
            <h2>Здравствуйте, {student_name}!</h2>
            <p>В вашей учетной записи произошли следующие изменения:</p>
            <ul>
        """
        
        for change in changes:
            html_content += f"<li>{change}</li>"
        
        html_content += f"""
            </ul>
            <p><strong>Текущие данные для входа:</strong></p>
            <ul>
                <li><strong>Логин:</strong> {username}</li>
        """
        
        if password:
            html_content += f"<li><strong>Новый пароль:</strong> {password}</li>"
        
        html_content += f"""
            </ul>
            <p><a href="{login_url}">Войти в систему</a></p>
        </body>
        </html>
        """
        
        # Текстовая версия
        text_content = f"В вашей учетной записи произошли изменения: {', '.join(changes)}"
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[student_email],
        )
        email.attach_alternative(html_content, "text/html")
        
        try:
            result = email.send(fail_silently=False)
            
            if result == 1:
                logger.info(f"✅ Email об изменениях отправлен ученику {student_name}")
                return True
            else:
                logger.warning(f"⚠️ Email об изменениях не отправлен ученику {student_email}")
                return False
                
        except Exception as send_error:
            logger.error(f"❌ Ошибка отправки email об изменениях: {send_error}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Общая ошибка отправки email об изменениях: {str(e)}")
        return False


# Дополнительная функция для тестирования email соединения
def test_email_connection():
    """Тестирует соединение с SMTP сервером"""
    try:
        logger.info("🔧 Тестирование соединения с SMTP сервером...")
        
        connection = get_connection()
        
        logger.debug(f"Backend: {connection.__class__.__name__}")
        logger.debug(f"Host: {connection.host}")
        logger.debug(f"Port: {connection.port}")
        logger.debug(f"Username: {connection.username}")
        
        # Пробуем открыть соединение
        connection.open()
        logger.info("✅ Соединение с SMTP сервером установлено успешно!")
        
        # Проверяем авторизацию
        if hasattr(connection, 'login'):
            connection.login()
            logger.info("✅ Авторизация прошла успешно!")
        
        connection.close()
        logger.info("✅ Соединение закрыто")
        return True
        
    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"❌ Ошибка аутентификации: {e}")
        logger.error("Проверьте логин и пароль в настройках Gmail")
        return False
        
    except Exception as e:
        logger.error(f"❌ Ошибка соединения: {e}")
        return False
    

def send_teacher_credentials_email(teacher_email, username, password, teacher_name, login_url):
    """
    Отправляет HTML письмо с учетными данными учителю
    """
    try:
        logger.info(f"Отправка email учителю {teacher_name} ({teacher_email})")
        
        subject = 'Учетные данные для входа в систему МПТед'
        
        try:
            html_content = render_to_string('emails/teacher_welcome.html', {
                'teacher_name': teacher_name,
                'username': username,
                'password': password,
                'login_url': login_url,
            })
        except:
            html_content = f"""
            <html>
            <body>
                <h2>Уважаемый(ая) {teacher_name},</h2>
                <p>Ваша учетная запись учителя в системе МПТед создана.</p>
                <p><strong>Логин:</strong> {username}</p>
                <p><strong>Пароль:</strong> {password}</p>
                <p><a href="{login_url}">Войти в систему</a></p>
                <p>Сохраните эти данные и смените пароль после первого входа.</p>
            </body>
            </html>
            """
        
        text_content = f"""
        Уважаемый(ая) {teacher_name},
        
        Ваша учетная запись учителя в системе МПТед создана.
        
        Логин: {username}
        Пароль: {password}
        Ссылка: {login_url}
        
        Сохраните эти данные.
        Смените пароль после первого входа.
        """
        
        email = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[teacher_email],
        )
        
        email.attach_alternative(html_content, "text/html")
        
        try:
            result = email.send(fail_silently=False)
            if result == 1:
                logger.info(f"Email отправлен учителю {teacher_name}")
                return True
            else:
                logger.warning(f"Email не отправлен учителю {teacher_email}")
                return False
                
        except Exception as send_error:
            logger.error(f"Ошибка отправки email учителю: {send_error}")
            return False
        
    except Exception as e:
        logger.error(f"Ошибка отправки email учителю: {str(e)}")
        return False