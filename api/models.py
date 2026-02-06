from django.contrib.auth.models import User
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _

# api/models.py (добавьте в конец файла)
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
import json

class AuditLog(models.Model):
    """Модель для аудита действий пользователей"""
    
    class ActionType(models.TextChoices):
        CREATE = 'CREATE', 'Создание'
        UPDATE = 'UPDATE', 'Обновление'
        DELETE = 'DELETE', 'Удаление (физическое)'
        SOFT_DELETE = 'SOFT_DELETE', 'Удаление (логическое)'
        RESTORE = 'RESTORE', 'Восстановление'
        VIEW = 'VIEW', 'Просмотр'
        EXPORT = 'EXPORT', 'Экспорт'
        IMPORT = 'IMPORT', 'Импорт'
        LOGIN = 'LOGIN', 'Вход в систему'
        LOGOUT = 'LOGOUT', 'Выход из системы'
        SYSTEM = 'SYSTEM', 'Системное действие'
    
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
        verbose_name="Пользователь"
    )
    action = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        verbose_name="Тип действия"
    )
    model_name = models.CharField(max_length=100, verbose_name="Модель")
    object_id = models.CharField(max_length=100, null=True, blank=True, verbose_name="ID объекта")
    
    # Для отслеживания изменений
    old_values = models.JSONField(null=True, blank=True, verbose_name="Старые значения")
    new_values = models.JSONField(null=True, blank=True, verbose_name="Новые значения")
    
    # Контекст
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP адрес")
    user_agent = models.TextField(null=True, blank=True, verbose_name="User Agent")
    request_path = models.CharField(max_length=500, null=True, blank=True, verbose_name="Путь запроса")
    request_method = models.CharField(max_length=10, null=True, blank=True, verbose_name="Метод запроса")
    
    # Технические поля
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Время действия")
    is_system_action = models.BooleanField(default=False, verbose_name="Системное действие")
    
    class Meta:
        verbose_name = "Запись аудита"
        verbose_name_plural = "Записи аудита"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['model_name', 'action']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        user_name = self.user.username if self.user else 'Аноним'
        return f"{user_name} - {self.get_action_display()} - {self.model_name} - {self.timestamp}"
    
    def get_changes_summary(self):
        """Возвращает текстовое описание изменений"""
        if self.action == self.ActionType.CREATE:
            return f"Создан объект {self.model_name}"
        elif self.action == self.ActionType.DELETE:
            return f"Удален объект {self.model_name}"
        elif self.action == self.ActionType.UPDATE and self.old_values and self.new_values:
            changes = []
            for field in self.old_values:
                if field in self.new_values and self.old_values[field] != self.new_values[field]:
                    changes.append(f"{field}: {self.old_values[field]} → {self.new_values[field]}")
            if changes:
                return "Изменены поля: " + ", ".join(changes)
        return self.get_action_display()


class Subject(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Название предмета")
    description = models.TextField(blank=True, verbose_name="Описание")
    
    class Meta:
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class StudentGroup(models.Model):
    name = models.CharField(max_length=50, verbose_name="Название класса")
    year = models.IntegerField(verbose_name="Год обучения")
    curator = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='curated_groups',
        verbose_name="Классный руководитель"
    )
    
    class Meta:
        verbose_name = "Учебный класс"
        verbose_name_plural = "Учебные классы"
        ordering = ['year', 'name']
        unique_together = ['name', 'year']
    
    def __str__(self):
        return f"{self.name} ({self.year} год)"


class StudentProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='student_profile',
        verbose_name="Пользователь"
    )
    patronymic = models.CharField(max_length=50, verbose_name="Отчество")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    profile_image = models.ImageField(
        upload_to='student_profile_images/',
        blank=True,
        null=True,
        verbose_name="Фотография"
    )
    address = models.TextField(blank=True, verbose_name="Адрес")
    course = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        verbose_name="Курс"
    )
    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name="Учебный класс"
    )
    
    class Meta:
        verbose_name = "Профиль ученика"
        verbose_name_plural = "Профили учеников"
    
    def get_full_name(self):
        return f"{self.user.last_name} {self.user.first_name} {self.patronymic}"
    
    def __str__(self):
        return self.get_full_name()


class TeacherProfile(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name='teacher_profile',
        verbose_name="Пользователь"
    )
    patronymic = models.CharField(max_length=50, verbose_name="Отчество")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Телефон")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Дата рождения")
    profile_image = models.ImageField(
        upload_to='teacher_profile_images/',
        blank=True,
        null=True,
        verbose_name="Фотография"
    )
    qualification = models.CharField(max_length=100, verbose_name="Квалификация")
    
    class Meta:
        verbose_name = "Профиль учителя"
        verbose_name_plural = "Профили учителей"
    
    def get_full_name(self):
        return f"{self.user.last_name} {self.user.first_name} {self.patronymic}"
    
    def __str__(self):
        return self.get_full_name()


class TeacherSubject(models.Model):
    teacher = models.ForeignKey(
        TeacherProfile,
        on_delete=models.CASCADE,
        related_name='teacher_subjects',
        verbose_name="Учитель"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='subject_teachers',
        verbose_name="Предмет"
    )
    
    class Meta:
        verbose_name = "Предмет учителя"
        verbose_name_plural = "Предметы учителей"
        unique_together = ['teacher', 'subject']
    
    def __str__(self):
        return f"{self.teacher.get_full_name()} - {self.subject.name}"


class DailySchedule(models.Model):
    class WeekDay(models.TextChoices):
        MONDAY = 'MON', _('Понедельник')
        TUESDAY = 'TUE', _('Вторник')
        WEDNESDAY = 'WED', _('Среда')
        THURSDAY = 'THU', _('Четверг')
        FRIDAY = 'FRI', _('Пятница')
        SATURDAY = 'SAT', _('Суббота')
        SUNDAY = 'SUN', _('Воскресенье')  # Добавил воскресенье для полноты
    
    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name='daily_schedules',
        verbose_name="Учебный класс"
    )
    week_day = models.CharField(
        max_length=3,
        choices=WeekDay.choices,
        verbose_name="День недели"
    )
    is_active = models.BooleanField(default=True, verbose_name="Активно")
    is_weekend = models.BooleanField(default=False, verbose_name="Выходной")  # Добавил поле
    
    class Meta:
        verbose_name = "Расписание на день"
        verbose_name_plural = "Расписания на дни"
        unique_together = ['student_group', 'week_day']
        ordering = ['week_day']
    
    def __str__(self):
        status = " (выходной)" if self.is_weekend else ""
        return f"{self.get_week_day_display()} - {self.student_group.name}{status}"

class ScheduleLesson(models.Model):
    daily_schedule = models.ForeignKey(
        DailySchedule,
        on_delete=models.CASCADE,
        related_name='lessons',
        verbose_name="Расписание дня"
    )
    lesson_number = models.IntegerField(verbose_name="Номер урока")
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='schedule_lessons',
        verbose_name="Предмет"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='schedule_lessons',
        verbose_name="Учитель"
    )
    
    class Meta:
        verbose_name = "Урок в расписании"
        verbose_name_plural = "Уроки в расписании"
        ordering = ['daily_schedule', 'lesson_number']
        unique_together = ['daily_schedule', 'lesson_number']
    
    def __str__(self):
        return f"{self.lesson_number} урок: {self.subject.name}"


class Homework(models.Model):
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    description = models.TextField(verbose_name="Описание")
    schedule_lesson = models.ForeignKey(
        ScheduleLesson,
        on_delete=models.CASCADE,
        related_name='homeworks',
        verbose_name="Урок"
    )
    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name='homeworks',
        verbose_name="Учебный класс"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    due_date = models.DateTimeField(verbose_name="Срок сдачи")
    attachment = models.FileField(
        upload_to='homework_attachments/',
        blank=True,
        null=True,
        verbose_name="Прикрепленный файл"
    )
    
    class Meta:
        verbose_name = "Домашнее задание"
        verbose_name_plural = "Домашние задания"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title


class HomeworkSubmission(models.Model):
    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name='submissions',
        verbose_name="Домашнее задание"
    )
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='homework_submissions',
        verbose_name="Ученик"
    )
    submission_file = models.FileField(
        upload_to='homework_submissions/',
        verbose_name="Файл с работой"
    )
    submission_text = models.TextField(blank=True, verbose_name="Текст работы")
    submitted_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отправки")
    
    class Meta:
        verbose_name = "Сданная работа"
        verbose_name_plural = "Сданные работы"
        unique_together = ['homework', 'student']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.homework.title}"


class Grade(models.Model):
    class GradeType(models.TextChoices):
        HOMEWORK = 'HW', _('Домашняя работа')
        TEST = 'TEST', _('Контрольная работа')
        CLASSWORK = 'CW', _('Классная работа')
        EXAM = 'EXAM', _('Экзамен')
        PROJECT = 'PROJ', _('Проект')
        ORAL = 'ORAL', _('Устный ответ')
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='grades',
        verbose_name="Ученик"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='grades',
        verbose_name="Предмет"
    )
    schedule_lesson = models.ForeignKey(
        ScheduleLesson,
        on_delete=models.CASCADE,
        related_name='grades',
        verbose_name="Урок"
    )
    teacher = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='given_grades',
        verbose_name="Учитель"
    )
    value = models.DecimalField(
        max_digits=3,
        decimal_places=1,
        verbose_name="Оценка"
    )
    grade_type = models.CharField(
        max_length=10,
        choices=GradeType.choices,
        verbose_name="Тип оценки"
    )
    date = models.DateField(verbose_name="Дата выставления")
    comment = models.TextField(blank=True, verbose_name="Комментарий")
    
    class Meta:
        verbose_name = "Оценка"
        verbose_name_plural = "Оценки"
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.student.get_full_name()}: {self.value} по {self.subject.name}"


class Comment(models.Model):
    homework = models.ForeignKey(
        Homework,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="Домашнее задание"
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name="Автор"
    )
    text = models.TextField(verbose_name="Текст комментария")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Комментарий от {self.author.get_full_name()}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'P', _('Присутствовал')
        ABSENT = 'A', _('Отсутствовал')
        LATE = 'L', _('Опоздал')
    
    student = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Ученик"
    )
    schedule_lesson = models.ForeignKey(
        ScheduleLesson,
        on_delete=models.CASCADE,
        related_name='attendances',
        verbose_name="Урок"
    )
    date = models.DateField(verbose_name="Дата")
    status = models.CharField(
        max_length=1,
        choices=Status.choices,
        verbose_name="Статус"
    )
    
    class Meta:
        verbose_name = "Посещаемость"
        verbose_name_plural = "Посещаемость"
        unique_together = ['student', 'schedule_lesson', 'date']
    
    def __str__(self):
        return f"{self.student.get_full_name()} - {self.date} - {self.get_status_display()}"


class Announcement(models.Model):
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    content = models.TextField(verbose_name="Содержание")
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='announcements',
        verbose_name="Автор"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='announcements',
        verbose_name="Для класса"
    )
    is_for_all = models.BooleanField(default=False, verbose_name="Для всех классов")
    
    class Meta:
        verbose_name = "Объявление"
        verbose_name_plural = "Объявления"
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title