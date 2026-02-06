# teacher_portal/views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta, date
from django.db.models import Q, Count, Avg, Sum, Case, When, Value, IntegerField, Max
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
import json

from api.models import *
from .decorators import teacher_required

# teacher_portal/views.py
def get_teacher_info(user):
    """Получает информацию о учителе и его группах"""
    try:
        profile = TeacherProfile.objects.get(user=user)
    except TeacherProfile.DoesNotExist:
        profile = None
    
    # Группы, где учитель - классный руководитель
    curator_groups = StudentGroup.objects.filter(curator=user)
    
    # Группы, которые учитель ведет
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user
    ).distinct()
    
    # Все группы учителя (классный руководитель + преподает)
    # Используем union вместо оператора |
    all_groups_qs = StudentGroup.objects.filter(
        id__in=curator_groups.values_list('id', flat=True)
    ).union(
        StudentGroup.objects.filter(
            id__in=teaching_groups.values_list('id', flat=True)
        )
    )
    
    # Конвертируем union QuerySet в список для удобства
    all_groups = list(all_groups_qs)
    
    # Предметы, которые ведет учитель
    subjects = Subject.objects.filter(
        subject_teachers__teacher__user=user
    ).distinct()
    
    return {
        'profile': profile,
        'curator_groups': curator_groups,
        'teaching_groups': teaching_groups,
        'all_groups': all_groups,
        'subjects': subjects,
    }



@teacher_required
def dashboard(request):
    """Главная страница учителя"""
    teacher_info = get_teacher_info(request.user)
    today = timezone.now().date()
    
    # Статистика
    total_students = StudentProfile.objects.filter(
        student_group__in=teacher_info['all_groups']
    ).count()
    
    # Оценки за сегодня
    today_grades = Grade.objects.filter(
        teacher=request.user,
        date=today
    ).count()
    
    # Посещаемость за сегодня
    today_attendance = Attendance.objects.filter(
        schedule_lesson__teacher=request.user,
        date=today
    ).count()
    
    # Активные ДЗ
    active_homework = Homework.objects.filter(
        schedule_lesson__teacher=request.user,
        due_date__gte=today
    ).count()
    
    # Ожидающие проверки работы
    recent_submissions = HomeworkSubmission.objects.filter(
        homework__schedule_lesson__teacher=request.user,
        homework__due_date__gte=today - timedelta(days=7)
    )

    # Получаем все домашние задания, по которым есть отправки
    submitted_homework_ids = recent_submissions.values_list('homework_id', flat=True)

    # Получаем работы, по которым еще нет оценок типа 'HW'
    pending_submissions = recent_submissions.filter(
        ~Q(id__in=Grade.objects.filter(
            grade_type='HW',
            subject__in=Subject.objects.filter(
                schedule_lessons__homeworks__id__in=submitted_homework_ids
            ),
            student__in=recent_submissions.values_list('student_id', flat=True)
        ).values_list('student_id', flat=True))
    ).count()
    
    # Расписание на сегодня
    today_schedule = []
    if teacher_info['all_groups']:
        week_day = today.strftime('%a').upper()[:3]
        today_schedule = ScheduleLesson.objects.filter(
            daily_schedule__student_group__in=teacher_info['all_groups'],
            daily_schedule__week_day=week_day,
            daily_schedule__is_active=True,
            daily_schedule__is_weekend=False,
            teacher=request.user
        ).select_related('subject', 'daily_schedule__student_group').order_by('lesson_number')
    
    # Ближайшие события (ДЗ на проверку, оценки к выставлению)
    upcoming_homework = Homework.objects.filter(
        schedule_lesson__teacher=request.user,
        due_date__gte=today
    ).select_related('schedule_lesson__subject', 'student_group').order_by('due_date')[:5]
    
    # Последние объявления
    recent_announcements = Announcement.objects.filter(
        author=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'teacher_info': teacher_info,
        'today': today,
        'stats': {
            'total_students': total_students,
            'today_grades': today_grades,
            'today_attendance': today_attendance,
            'active_homework': active_homework,
            'pending_submissions': pending_submissions,
        },
        'today_schedule': today_schedule,
        'upcoming_homework': upcoming_homework,
        'recent_announcements': recent_announcements,
    }
    
    return render(request, 'teacher_portal/dashboard.html', context)


@teacher_required
def manage_grades(request):
    """Управление оценками"""
    teacher_info = get_teacher_info(request.user)
    
    # Фильтры
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    student_id = request.GET.get('student', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Базовый запрос оценок
    grades_qs = Grade.objects.filter(
        teacher=request.user
    ).select_related('student', 'subject', 'schedule_lesson')
    
    # Применяем фильтры
    if group_id:
        grades_qs = grades_qs.filter(
            schedule_lesson__daily_schedule__student_group_id=group_id
        )
    
    if subject_id:
        grades_qs = grades_qs.filter(subject_id=subject_id)
    
    if student_id:
        grades_qs = grades_qs.filter(student_id=student_id)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            grades_qs = grades_qs.filter(date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            grades_qs = grades_qs.filter(date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Сортируем по дате
    grades_qs = grades_qs.order_by('-date', '-id')
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(grades_qs, 25)
    page_obj = paginator.get_page(page_number)
    
    # Статистика
    grade_stats = grades_qs.aggregate(
        total=Count('id'),
        average=Avg('value'),
        excellent=Count(Case(When(value__gte=4.5, then=1))),
        good=Count(Case(When(value__gte=3.5, value__lt=4.5, then=1))),
        satisfactory=Count(Case(When(value__gte=2.5, value__lt=3.5, then=1))),
        poor=Count(Case(When(value__lt=2.5, then=1))),
    )
    
    # Данные для фильтров
    groups = teacher_info['all_groups']
    subjects = teacher_info['subjects']
    students = User.objects.filter(
        student_profile__student_group__in=teacher_info['all_groups']
    ).distinct().order_by('last_name', 'first_name')
    
    context = {
        'teacher_info': teacher_info,
        'page_obj': page_obj,
        'grade_stats': grade_stats,
        'groups': groups,
        'subjects': subjects,
        'students': students,
        'filters': {
            'group_id': group_id,
            'subject_id': subject_id,
            'student_id': student_id,
            'date_from': date_from,
            'date_to': date_to,
        },
    }
    
    return render(request, 'teacher_portal/grades.html', context)

@teacher_required
def add_grade(request):
    """Добавление новой оценки"""
    teacher_info = get_teacher_info(request.user)
    
    if request.method == 'POST':
        student_id = request.POST.get('student')
        subject_id = request.POST.get('subject')
        value = request.POST.get('value')
        grade_type = request.POST.get('grade_type')
        comment = request.POST.get('comment', '')
        lesson_id = request.POST.get('lesson', '')
        grade_date = request.POST.get('date', timezone.now().date().isoformat())
        
        # Валидация
        errors = []
        
        if not student_id:
            errors.append('Выберите ученика')
        if not subject_id:
            errors.append('Выберите предмет')
        if not value:
            errors.append('Введите оценку')
        else:
            try:
                value = float(value)
                if value < 1 or value > 5:
                    errors.append('Оценка должна быть от 1 до 5')
            except ValueError:
                errors.append('Оценка должна быть числом')
        
        if not grade_type:
            errors.append('Выберите тип оценки')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                student = User.objects.get(id=student_id)
                subject = Subject.objects.get(id=subject_id)
                
                # Получаем урок (если указан)
                schedule_lesson = None
                if lesson_id:
                    schedule_lesson = ScheduleLesson.objects.get(id=lesson_id)
                
                # Создаем оценку
                grade = Grade.objects.create(
                    student=student,
                    subject=subject,
                    schedule_lesson=schedule_lesson,
                    teacher=request.user,
                    value=value,
                    grade_type=grade_type,
                    date=grade_date,
                    comment=comment
                )
                
                messages.success(request, f'Оценка {value} успешно выставлена для {student.get_full_name()}')
                return redirect('teacher_portal:grades')  # Исправлено!
                
            except Exception as e:
                messages.error(request, f'Ошибка при сохранении оценки: {str(e)}')
    
    # Данные для формы
    students = User.objects.filter(
        student_profile__student_group__in=teacher_info['all_groups']
    ).distinct().order_by('last_name', 'first_name')
    
    subjects = teacher_info['subjects']
    
    # Исправленная строка - убираем фильтрацию по дате
    recent_lessons = ScheduleLesson.objects.filter(
        teacher=request.user
    ).select_related('subject', 'daily_schedule__student_group').order_by(
        'daily_schedule__week_day', 'lesson_number'
    )[:10]
    
    context = {
        'teacher_info': teacher_info,
        'students': students,
        'subjects': subjects,
        'recent_lessons': recent_lessons,
        'today': timezone.now().date(),
        'grade_types': Grade.GradeType.choices,  # Добавляем типы оценок
    }
    
    return render(request, 'teacher_portal/grade_form.html', context)


@teacher_required
def edit_grade(request, grade_id):
    """Редактирование оценки"""
    grade = get_object_or_404(Grade, id=grade_id, teacher=request.user)
    teacher_info = get_teacher_info(request.user)
    
    if request.method == 'POST':
        value = request.POST.get('value')
        grade_type = request.POST.get('grade_type')
        comment = request.POST.get('comment', '')
        
        # Валидация
        errors = []
        
        if not value:
            errors.append('Введите оценку')
        else:
            try:
                value = float(value)
                if value < 1 or value > 5:
                    errors.append('Оценка должна быть от 1 до 5')
            except ValueError:
                errors.append('Оценка должна быть числом')
        
        if not grade_type:
            errors.append('Выберите тип оценки')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                grade.value = value
                grade.grade_type = grade_type
                grade.comment = comment
                grade.save()
                
                messages.success(request, 'Оценка успешно обновлена')
                return redirect('teacher_portal:grades')  # Исправлено!
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении оценки: {str(e)}')
    
    context = {
        'teacher_info': teacher_info,
        'grade': grade,
        'grade_types': Grade.GradeType.choices,  # Добавляем типы оценок
    }
    
    return render(request, 'teacher_portal/grade_form.html', context)


@teacher_required
def delete_homework(request, homework_id):
    """Удаление домашнего задания"""
    homework = get_object_or_404(Homework, id=homework_id, schedule_lesson__teacher=request.user)
    
    if request.method == 'POST':
        title = homework.title
        homework.delete()
        messages.success(request, f'Задание "{title}" удалено')
        return redirect('teacher_portal:homework')
    
    # Если GET запрос - редирект на список
    return redirect('teacher_portal:homework')


@teacher_required
def delete_grade(request, grade_id):
    """Удаление оценки"""
    grade = get_object_or_404(Grade, id=grade_id, teacher=request.user)
    
    if request.method == 'POST':
        student_name = grade.student.get_full_name()
        grade.delete()
        messages.success(request, f'Оценка для {student_name} удалена')
    
    return redirect('teacher_portal:grades')


@teacher_required
def manage_attendance(request):
    """Управление посещаемостью"""
    teacher_info = get_teacher_info(request.user)
    
    # Фильтры
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # По умолчанию - сегодня
    selected_date = request.GET.get('date', timezone.now().date().isoformat())
    
    try:
        selected_date_obj = datetime.strptime(selected_date, '%Y-%m-%d').date()
    except ValueError:
        selected_date_obj = timezone.now().date()
    
    # Определяем день недели
    week_day = selected_date_obj.strftime('%a').upper()[:3]
    
    # Получаем уроки на выбранную дату
    lessons = ScheduleLesson.objects.filter(
        teacher=request.user,
        daily_schedule__week_day=week_day,
        daily_schedule__is_active=True,
        daily_schedule__is_weekend=False
    ).select_related('subject', 'daily_schedule__student_group').order_by('lesson_number')
    
    # Применяем фильтры
    if group_id:
        lessons = lessons.filter(daily_schedule__student_group_id=group_id)
    
    if subject_id:
        lessons = lessons.filter(subject_id=subject_id)
    
    # Получаем учеников для каждого урока
    attendance_data = []
    for lesson in lessons:
        # Получаем учеников группы
        students = StudentProfile.objects.filter(
            student_group=lesson.daily_schedule.student_group
        ).select_related('user').order_by('user__last_name', 'user__first_name')
        
        # Получаем посещаемость для этого урока
        attendance_records = {
            record.student_id: record 
            for record in Attendance.objects.filter(
                schedule_lesson=lesson,
                date=selected_date_obj
            )
        }
        
        lesson_data = {
            'lesson': lesson,
            'students': [],
        }
        
        for student_profile in students:
            student = student_profile.user
            attendance = attendance_records.get(student.id)
            
            lesson_data['students'].append({
                'student': student,
                'profile': student_profile,
                'attendance': attendance,
                'status': attendance.status if attendance else None,
            })
        
        attendance_data.append(lesson_data)
    
    # Данные для фильтров
    groups = teacher_info['all_groups']
    subjects = teacher_info['subjects']
    
    context = {
        'teacher_info': teacher_info,
        'attendance_data': attendance_data,
        'selected_date': selected_date_obj,
        'groups': groups,
        'subjects': subjects,
        'filters': {
            'group_id': group_id,
            'subject_id': subject_id,
            'date_from': date_from,
            'date_to': date_to,
        },
    }
    
    return render(request, 'teacher_portal/attendance.html', context)


@require_http_methods(["POST"])
@teacher_required
def save_attendance(request):
    """Сохранение посещаемости"""
    print(f"DEBUG: save_attendance called by {request.user.username}")
    
    try:
        # Читаем тело запроса
        body = request.body.decode('utf-8')
        print(f"DEBUG: Request body: {body}")
        
        data = json.loads(body)
        print(f"DEBUG: Parsed data: {data}")
        
        date_str = data.get('date')
        attendance_data = data.get('attendance', {})
        
        print(f"DEBUG: Date: {date_str}")
        print(f"DEBUG: Attendance data: {attendance_data}")
        
        if not date_str:
            print("DEBUG: No date provided")
            return JsonResponse({
                'success': False,
                'error': 'Дата не указана'
            }, status=400)
        
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        saved_count = 0
        
        # Обрабатываем каждый урок
        for lesson_id, student_statuses in attendance_data.items():
            print(f"DEBUG: Processing lesson {lesson_id}")
            try:
                lesson = ScheduleLesson.objects.get(id=lesson_id, teacher=request.user)
                print(f"DEBUG: Found lesson: {lesson.id} - {lesson.subject.name}")
                
                # Проверяем, что урок существует и учитель ведет его
                if lesson.teacher != request.user:
                    print(f"DEBUG: Lesson teacher mismatch")
                    continue
                
                # Обрабатываем каждого ученика в уроке
                for student_id, status in student_statuses.items():
                    print(f"DEBUG: Processing student {student_id} with status {status}")
                    try:
                        student = User.objects.get(id=student_id)
                        print(f"DEBUG: Found student: {student.get_full_name()}")
                        
                        # Проверяем, что ученик в группе урока
                        if not StudentProfile.objects.filter(
                            user=student,
                            student_group=lesson.daily_schedule.student_group
                        ).exists():
                            print(f"DEBUG: Student not in lesson group")
                            continue
                        
                        # Проверяем корректность статуса
                        valid_statuses = ['P', 'A', 'L']
                        if status not in valid_statuses:
                            print(f"DEBUG: Invalid status: {status}")
                            continue
                        
                        print(f"DEBUG: Saving attendance for {student.get_full_name()}")
                        
                        # Обновляем или создаем запись посещаемости
                        attendance, created = Attendance.objects.update_or_create(
                            student=student,
                            schedule_lesson=lesson,
                            date=date_obj,
                            defaults={'status': status}
                        )
                        
                        saved_count += 1
                        print(f"DEBUG: Saved count: {saved_count}")
                        
                    except User.DoesNotExist:
                        print(f"DEBUG: Student {student_id} does not exist")
                        continue
                    except Exception as e:
                        print(f"DEBUG: Error saving attendance for student {student_id}: {str(e)}")
                        continue
                        
            except ScheduleLesson.DoesNotExist:
                print(f"DEBUG: Lesson {lesson_id} does not exist")
                continue
            except Exception as e:
                print(f"DEBUG: Error processing lesson {lesson_id}: {str(e)}")
                continue
        
        print(f"DEBUG: Total saved: {saved_count}")
        return JsonResponse({
            'success': True,
            'message': f'Посещаемость для {saved_count} учеников сохранена'
        })
        
    except json.JSONDecodeError as e:
        print(f"DEBUG: JSON decode error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'Неверный формат данных'
        }, status=400)
    except Exception as e:
        print(f"DEBUG: General exception: {str(e)}")
        import traceback
        print(f"DEBUG: Traceback: {traceback.format_exc()}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

@teacher_required
def edit_homework(request, homework_id):
    """Редактирование домашнего задания"""
    homework = get_object_or_404(Homework, id=homework_id, schedule_lesson__teacher=request.user)
    teacher_info = get_teacher_info(request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        due_date = request.POST.get('due_date')
        due_time = request.POST.get('due_time', '23:59')
        attachment = request.FILES.get('attachment')
        
        # Валидация
        errors = []
        
        if not title:
            errors.append('Введите название задания')
        if not due_date:
            errors.append('Укажите срок сдачи')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Обновляем данные
                homework.title = title
                homework.description = description
                
                # Обновляем дату сдачи
                due_datetime = datetime.strptime(f'{due_date} {due_time}', '%Y-%m-%d %H:%M')
                homework.due_date = due_datetime
                
                # Обновляем файл, если загружен новый
                if attachment:
                    homework.attachment = attachment
                
                homework.save()
                
                messages.success(request, f'Задание "{title}" обновлено')
                return redirect('teacher_portal:homework')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении задания: {str(e)}')
    
    # Данные для формы
    lessons = ScheduleLesson.objects.filter(
        teacher=request.user
    ).select_related('subject', 'daily_schedule__student_group').order_by(
        'daily_schedule__week_day', 'lesson_number'
    )[:50]
    
    groups = teacher_info['all_groups']
    
    context = {
        'teacher_info': teacher_info,
        'homework': homework,
        'lessons': lessons,
        'groups': groups,
        'today': timezone.now().date(),
        'edit_mode': True,  # Флаг для режима редактирования
    }
    
    return render(request, 'teacher_portal/homework_form.html', context)

@teacher_required
def manage_homework(request):
    """Управление домашними заданиями"""
    teacher_info = get_teacher_info(request.user)
    
    # Фильтры
    group_id = request.GET.get('group', '')
    subject_id = request.GET.get('subject', '')
    status_filter = request.GET.get('status', 'active')
    
    # Базовый запрос ДЗ
    homework_qs = Homework.objects.filter(
        schedule_lesson__teacher=request.user
    ).select_related('schedule_lesson__subject', 'student_group').order_by('-created_at')
    
    # Применяем фильтры
    if group_id:
        homework_qs = homework_qs.filter(student_group_id=group_id)
    
    if subject_id:
        homework_qs = homework_qs.filter(schedule_lesson__subject_id=subject_id)
    
    if status_filter == 'active':
        homework_qs = homework_qs.filter(due_date__gte=timezone.now().date())
    elif status_filter == 'overdue':
        homework_qs = homework_qs.filter(due_date__lt=timezone.now().date())
    elif status_filter == 'completed':
        # ДЗ, по которым все сдали работы
        pass  # Можно добавить логику
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(homework_qs, 20)
    page_obj = paginator.get_page(page_number)
    
    # Считаем статистику по каждому ДЗ
    for homework in page_obj:
        homework.submission_count = HomeworkSubmission.objects.filter(
            homework=homework
        ).count()
        
        # ВРЕМЕННО УБИРАЕМ ЭТУ СТРОКУ - НЕТ СВЯЗИ МЕЖДУ GRADE И HOMEWORKSUBMISSION
        # homework.graded_count = Grade.objects.filter(
        #     homework_submission__homework=homework,
        #     grade_type='HW'
        # ).count()
        
        homework.graded_count = 0  # Показываем 0, пока не настроим связь
        
        homework.total_students = StudentProfile.objects.filter(
            student_group=homework.student_group
        ).count()
    
    # Данные для фильтров
    groups = teacher_info['all_groups']
    subjects = teacher_info['subjects']
    
    context = {
        'teacher_info': teacher_info,
        'page_obj': page_obj,
        'groups': groups,
        'subjects': subjects,
        'filters': {
            'group_id': group_id,
            'subject_id': subject_id,
            'status_filter': status_filter,
        },
    }
    
    return render(request, 'teacher_portal/homework.html', context)

@teacher_required
def create_homework(request, homework_id=None):
    """Создание или редактирование домашнего задания"""
    homework = None
    edit_mode = False
    
    # Если передан homework_id - это режим редактирования
    if homework_id:
        homework = get_object_or_404(Homework, id=homework_id, schedule_lesson__teacher=request.user)
        edit_mode = True
    
    teacher_info = get_teacher_info(request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        description = request.POST.get('description', '').strip()
        due_date = request.POST.get('due_date')
        due_time = request.POST.get('due_time', '23:59')
        attachment = request.FILES.get('attachment')
        
        # Валидация
        errors = []
        
        if not title:
            errors.append('Введите название задания')
        if not due_date:
            errors.append('Укажите срок сдачи')
        
        if edit_mode:
            # В режиме редактирования не требуем урок и класс
            lesson = homework.schedule_lesson
            group = homework.student_group
        else:
            # В режиме создания требуем урок и класс
            lesson_id = request.POST.get('lesson')
            group_id = request.POST.get('group')
            
            if not lesson_id:
                errors.append('Выберите урок')
            if not group_id:
                errors.append('Выберите класс')
            
            if not errors:
                lesson = ScheduleLesson.objects.get(id=lesson_id, teacher=request.user)
                group = StudentGroup.objects.get(id=group_id)
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Создаем дату с временем
                due_datetime = datetime.strptime(f'{due_date} {due_time}', '%Y-%m-%d %H:%M')
                
                if edit_mode:
                    # Обновляем существующее задание
                    homework.title = title
                    homework.description = description
                    homework.due_date = due_datetime
                    
                    if attachment:
                        homework.attachment = attachment
                    
                    homework.save()
                    messages.success(request, f'Задание "{title}" обновлено')
                else:
                    # Создаем новое задание
                    homework = Homework.objects.create(
                        title=title,
                        description=description,
                        schedule_lesson=lesson,
                        student_group=group,
                        due_date=due_datetime,
                    )
                    
                    if attachment:
                        homework.attachment = attachment
                        homework.save()
                    
                    messages.success(request, f'Задание "{title}" создано')
                
                return redirect('teacher_portal:homework')
                
            except Exception as e:
                messages.error(request, f'Ошибка: {str(e)}')
    
    # Данные для формы
    lessons = ScheduleLesson.objects.filter(
        teacher=request.user
    ).select_related('subject', 'daily_schedule__student_group').order_by(
        'daily_schedule__week_day', 'lesson_number'
    )[:50]
    
    groups = teacher_info['all_groups']
    
    context = {
        'teacher_info': teacher_info,
        'lessons': lessons,
        'groups': groups,
        'homework': homework,
        'today': timezone.now().date(),
        'default_due_date': (timezone.now() + timedelta(days=7)).date(),
    }
    
    return render(request, 'teacher_portal/homework_form.html', context)

@teacher_required
def homework_submissions(request, homework_id):
    """Проверка работ по домашнему заданию"""
    homework = get_object_or_404(Homework, id=homework_id, schedule_lesson__teacher=request.user)
    teacher_info = get_teacher_info(request.user)
    
    # Получаем все отправки
    submissions = HomeworkSubmission.objects.filter(
        homework=homework
    ).select_related('student').order_by('submitted_at')
    
    # Пока не можем получить оценки за эти работы, т.к. нет связи
    # Вместо этого создаем пустой словарь
    grades = {}
    
    # Получаем всех учеников группы
    all_students = StudentProfile.objects.filter(
        student_group=homework.student_group
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Создаем полный список
    students_data = []
    for student_profile in all_students:
        student = student_profile.user
        
        # Ищем отправку
        submission = None
        for sub in submissions:
            if sub.student == student:
                submission = sub
                break
        
        # Ищем оценку (пока не можем, т.к. нет связи)
        grade = None
        
        students_data.append({
            'student': student,
            'profile': student_profile,
            'submission': submission,
            'grade': grade,
        })
    
    context = {
        'teacher_info': teacher_info,
        'homework': homework,
        'students_data': students_data,
    }
    
    return render(request, 'teacher_portal/homework_submissions.html', context)


@require_http_methods(["POST"])
@teacher_required
def grade_submission(request, submission_id):
    """Выставление оценки за домашнюю работу"""
    submission = get_object_or_404(HomeworkSubmission, id=submission_id)
    
    # Проверяем, что ДЗ создано этим учителем
    if submission.homework.schedule_lesson.teacher != request.user:
        return JsonResponse({'error': 'Доступ запрещен'}, status=403)
    
    try:
        value = float(request.POST.get('value', 0))
        comment = request.POST.get('comment', '')
        
        if value < 1 or value > 5:
            return JsonResponse({'error': 'Оценка должна быть от 1 до 5'}, status=400)
        
        # Создаем оценку, но не связываем с homework_submission (пока нет поля)
        grade = Grade.objects.create(
            student=submission.student,
            subject=submission.homework.schedule_lesson.subject,
            schedule_lesson=submission.homework.schedule_lesson,
            teacher=request.user,
            value=value,
            grade_type='HW',
            date=timezone.now().date(),
            comment=comment
            # Нет поля homework_submission!
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Оценка выставлена',
            'grade': {
                'value': grade.value,
                'comment': grade.comment,
                'date': grade.date.isoformat(),
            }
        })
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@teacher_required
def view_schedule(request):
    """Просмотр расписания"""
    teacher_info = get_teacher_info(request.user)
    
    # Фильтр по группе
    group_id = request.GET.get('group', '')
    
    # Получаем расписание
    schedule_qs = ScheduleLesson.objects.filter(
        teacher=request.user
    ).select_related(
        'subject', 'daily_schedule__student_group'
    ).order_by('daily_schedule__week_day', 'lesson_number')
    
    if group_id:
        schedule_qs = schedule_qs.filter(daily_schedule__student_group_id=group_id)
    
    # Группируем по дням недели
    schedule_by_day = {}
    for lesson in schedule_qs:
        day = lesson.daily_schedule.get_week_day_display()
        if day not in schedule_by_day:
            schedule_by_day[day] = {
                'day_name': day,
                'day_code': lesson.daily_schedule.week_day,
                'lessons': [],
            }
        schedule_by_day[day]['lessons'].append(lesson)
    
    # Сортируем по порядку дней недели
    day_order = {
        'Понедельник': 1, 'Вторник': 2, 'Среда': 3,
        'Четверг': 4, 'Пятница': 5, 'Суббота': 6, 'Воскресенье': 7
    }
    schedule_by_day = dict(sorted(
        schedule_by_day.items(),
        key=lambda x: day_order.get(x[0], 99)
    ))
    
    # Рассчитываем статистику
    total_lessons = schedule_qs.count()
    
    # Уникальные классы
    unique_groups = schedule_qs.values(
        'daily_schedule__student_group'
    ).distinct().count()
    
    # Уникальные предметы
    unique_subjects = schedule_qs.values(
        'subject'
    ).distinct().count()
    
    # Среднее количество уроков в день
    days_with_lessons = len(schedule_by_day)
    average_lessons_per_day = total_lessons / days_with_lessons if days_with_lessons > 0 else 0
    
    context = {
        'teacher_info': teacher_info,
        'schedule_by_day': schedule_by_day,
        'groups': teacher_info['all_groups'],
        'selected_group': group_id,
        # Статистические данные
        'total_lessons': total_lessons,
        'unique_groups': unique_groups,
        'unique_subjects': unique_subjects,
        'average_lessons_per_day': average_lessons_per_day,
    }
    
    return render(request, 'teacher_portal/schedule.html', context)


@teacher_required
def edit_announcement(request, announcement_id):
    """Редактирование существующего объявления"""
    announcement = get_object_or_404(Announcement, id=announcement_id, author=request.user)
    teacher_info = get_teacher_info(request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        group_id = request.POST.get('group', '')
        is_for_all = request.POST.get('is_for_all') == 'on'
        
        # Валидация
        errors = []
        
        if not title:
            errors.append('Введите заголовок')
        if not content:
            errors.append('Введите содержание')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Обновляем объявление
                announcement.title = title
                announcement.content = content
                announcement.is_for_all = is_for_all
                
                # Обновляем группу
                if not is_for_all and group_id:
                    group = StudentGroup.objects.get(id=group_id)
                    announcement.student_group = group
                else:
                    announcement.student_group = None
                
                announcement.save()
                messages.success(request, 'Объявление обновлено')
                return redirect('teacher_portal:announcements')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении объявления: {str(e)}')
    
    context = {
        'teacher_info': teacher_info,
        'announcement': announcement,
        'groups': teacher_info['all_groups'],
        'edit_mode': True,  # Флаг для шаблона
    }
    
    return render(request, 'teacher_portal/announcement_form.html', context)


@teacher_required
def delete_announcement(request, announcement_id):
    """Удаление объявления"""
    announcement = get_object_or_404(Announcement, id=announcement_id, author=request.user)
    
    if request.method == 'POST':
        title = announcement.title
        announcement.delete()
        messages.success(request, f'Объявление "{title}" удалено')
        return redirect('teacher_portal:announcements')
    
    # Если GET запрос - редирект на список
    return redirect('teacher_portal:announcements')


@teacher_required
def manage_announcements(request):
    """Управление объявлениями"""
    teacher_info = get_teacher_info(request.user)
    
    # Фильтры
    group_id = request.GET.get('group', '')
    status_filter = request.GET.get('status', 'all')
    
    # Базовый запрос объявлений
    announcements_qs = Announcement.objects.filter(
        author=request.user
    ).select_related('student_group').order_by('-created_at')
    
    # Применяем фильтры
    if group_id:
        if group_id == 'all':
            announcements_qs = announcements_qs.filter(is_for_all=True)
        else:
            announcements_qs = announcements_qs.filter(student_group_id=group_id)
    
    if status_filter == 'active':
        # Активные (последние 7 дней)
        week_ago = timezone.now() - timedelta(days=7)
        announcements_qs = announcements_qs.filter(created_at__gte=week_ago)
    elif status_filter == 'expired':
        # Старые
        week_ago = timezone.now() - timedelta(days=7)
        announcements_qs = announcements_qs.filter(created_at__lt=week_ago)
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(announcements_qs, 20)
    page_obj = paginator.get_page(page_number)
    
    context = {
        'teacher_info': teacher_info,
        'page_obj': page_obj,
        'groups': teacher_info['all_groups'],
        'filters': {
            'group_id': group_id,
            'status_filter': status_filter,
        },
    }
    
    return render(request, 'teacher_portal/announcements.html', context)


@teacher_required
def create_announcement(request):
    """Создание объявления"""
    teacher_info = get_teacher_info(request.user)
    
    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        content = request.POST.get('content', '').strip()
        group_id = request.POST.get('group', '')
        is_for_all = request.POST.get('is_for_all') == 'on'
        
        # Валидация
        errors = []
        
        if not title:
            errors.append('Введите заголовок')
        if not content:
            errors.append('Введите содержание')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Создаем объявление
                announcement = Announcement.objects.create(
                    title=title,
                    content=content,
                    author=request.user,
                    is_for_all=is_for_all,
                )
                
                # Если не "для всех", привязываем к группе
                if not is_for_all and group_id:
                    group = StudentGroup.objects.get(id=group_id)
                    announcement.student_group = group
                    announcement.save()
                
                messages.success(request, 'Объявление опубликовано')
                return redirect('teacher_announcements')
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании объявления: {str(e)}')
    
    context = {
        'teacher_info': teacher_info,
        'groups': teacher_info['all_groups'],
    }
    
    return render(request, 'teacher_portal/announcement_form.html', context)


@teacher_required
def view_students(request):
    """Список учеников"""
    teacher_info = get_teacher_info(request.user)
    
    # Фильтры
    group_id = request.GET.get('group', '')
    search_query = request.GET.get('search', '')
    
    # Базовый запрос учеников
    students_qs = StudentProfile.objects.filter(
        student_group__in=teacher_info['all_groups']
    ).select_related('user', 'student_group').order_by('user__last_name', 'user__first_name')
    
    # Применяем фильтры
    if group_id:
        students_qs = students_qs.filter(student_group_id=group_id)
    
    if search_query:
        students_qs = students_qs.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(patronymic__icontains=search_query) |
            Q(user__username__icontains=search_query)
        )
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(students_qs, 30)
    page_obj = paginator.get_page(page_number)
    
    # Для каждого ученика получаем статистику
    total_attendance_stats = {'present': 0, 'total': 0}
    total_grade_stats = {'sum': 0, 'count': 0}
    
    for student_profile in page_obj:
        student = student_profile.user
        
        # Статистика оценок
        grade_stats = Grade.objects.filter(
            student=student,
            teacher=request.user
        ).aggregate(
            total=Count('id'),
            average=Avg('value'),
            latest=Max('date'),
        )
        
        student_profile.grade_stats = grade_stats
        
        if grade_stats['total'] and grade_stats['average']:
            total_grade_stats['sum'] += grade_stats['average'] * grade_stats['total']
            total_grade_stats['count'] += grade_stats['total']
        
        # Статистика посещаемости
        attendance_stats = Attendance.objects.filter(
            student=student,
            schedule_lesson__teacher=request.user
        ).aggregate(
            total=Count('id'),
            present=Count(Case(When(status='P', then=1))),
            absent=Count(Case(When(status='A', then=1))),
            late=Count(Case(When(status='L', then=1))),
        )
        
        student_profile.attendance_stats = attendance_stats
        
        # Рассчитываем процент присутствия
        if attendance_stats['total'] and attendance_stats['total'] > 0:
            attendance_stats['present_percentage'] = round(
                (attendance_stats['present'] / attendance_stats['total']) * 100, 
                1
            )
        else:
            attendance_stats['present_percentage'] = 0
        
        total_attendance_stats['present'] += attendance_stats['present'] or 0
        total_attendance_stats['total'] += attendance_stats['total'] or 0
    
    # Рассчитываем общую статистику
    avg_grades = total_grade_stats['sum'] / total_grade_stats['count'] if total_grade_stats['count'] > 0 else 0
    
    if total_attendance_stats['total'] > 0:
        attendance_rate = round((total_attendance_stats['present'] / total_attendance_stats['total']) * 100, 1)
    else:
        attendance_rate = 0
    
    # Считаем активных учеников (тех, у кого были оценки или посещаемость в последние 30 дней)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    active_students = User.objects.filter(
        id__in=students_qs.values_list('user_id', flat=True)
    ).filter(
        Q(grades__teacher=request.user, grades__date__gte=thirty_days_ago) |
        Q(attendances__schedule_lesson__teacher=request.user, attendances__date__gte=thirty_days_ago)
    ).distinct().count()
    
    context = {
        'teacher_info': teacher_info,
        'page_obj': page_obj,
        'groups': teacher_info['all_groups'],
        'filters': {
            'group_id': group_id,
            'search_query': search_query,
        },
        'avg_grades': avg_grades,
        'attendance_rate': attendance_rate,
        'active_students': active_students,
    }
    
    return render(request, 'teacher_portal/students.html', context)


@teacher_required
def student_detail(request, student_id):
    """Детальная информация об ученике"""
    student_profile = get_object_or_404(StudentProfile, user_id=student_id)
    
    # Проверяем, что ученик в группе учителя
    teacher_info = get_teacher_info(request.user)
    if student_profile.student_group not in teacher_info['all_groups']:
        messages.error(request, 'Доступ запрещен')
        return redirect('teacher_students')
    
    student = student_profile.user
    
    # Оценки от этого учителя
    grades = Grade.objects.filter(
        student=student,
        teacher=request.user
    ).select_related('subject').order_by('-date')[:20]
    
    # Статистика по оценкам
    grade_stats = Grade.objects.filter(
        student=student,
        teacher=request.user
    ).aggregate(
        total=Count('id'),
        average=Avg('value'),
        excellent=Count(Case(When(value__gte=4.5, then=1))),
        good=Count(Case(When(value__gte=3.5, value__lt=4.5, then=1))),
        satisfactory=Count(Case(When(value__gte=2.5, value__lt=3.5, then=1))),
        poor=Count(Case(When(value__lt=2.5, then=1))),
    )
    
    # Посещаемость
    attendance = Attendance.objects.filter(
        student=student,
        schedule_lesson__teacher=request.user
    ).select_related('schedule_lesson__subject').order_by('-date')[:20]
    
    # Статистика посещаемости
    attendance_stats = Attendance.objects.filter(
        student=student,
        schedule_lesson__teacher=request.user
    ).aggregate(
        total=Count('id'),
        present=Count(Case(When(status='P', then=1))),
        absent=Count(Case(When(status='A', then=1))),
        late=Count(Case(When(status='L', then=1))),
    )
    
    # Домашние задания
    homework_submissions = HomeworkSubmission.objects.filter(
        student=student,
        homework__schedule_lesson__teacher=request.user
    ).select_related('homework', 'homework__schedule_lesson__subject').order_by('-submitted_at')[:10]
    
    context = {
        'teacher_info': teacher_info,
        'student_profile': student_profile,
        'student': student,
        'grades': grades,
        'grade_stats': grade_stats,
        'attendance': attendance,
        'attendance_stats': attendance_stats,
        'homework_submissions': homework_submissions,
    }
    
    return render(request, 'teacher_portal/student_detail.html', context)


@teacher_required
def view_statistics(request):
    """Статистика для учителя"""
    teacher_info = get_teacher_info(request.user)
    
    # Получаем период из GET-параметров (по умолчанию 30 дней)
    days = int(request.GET.get('days', 30))
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=days)
    
    # Статистика по оценкам
    grade_stats_by_subject = []
    for subject in teacher_info['subjects']:
        stats = Grade.objects.filter(
            teacher=request.user,
            subject=subject,
            date__range=[start_date, end_date]
        ).aggregate(
            total=Count('id'),
            average=Avg('value'),
            excellent=Count(Case(When(value__gte=4.5, then=1))),
            good=Count(Case(When(value__gte=3.5, value__lt=4.5, then=1))),
            satisfactory=Count(Case(When(value__gte=2.5, value__lt=3.5, then=1))),
            poor=Count(Case(When(value__lt=2.5, then=1))),
        )
        
        grade_stats_by_subject.append({
            'subject': subject,
            'stats': stats,
        })
    
    # Статистика по посещаемости
    attendance_stats_by_group = []
    for group in teacher_info['all_groups']:
        stats = Attendance.objects.filter(
            schedule_lesson__teacher=request.user,
            schedule_lesson__daily_schedule__student_group=group,
            date__range=[start_date, end_date]
        ).aggregate(
            total=Count('id'),
            present=Count(Case(When(status='P', then=1))),
            absent=Count(Case(When(status='A', then=1))),
            late=Count(Case(When(status='L', then=1))),
        )
        
        if stats['total'] > 0:
            stats['present_percentage'] = round((stats['present'] / stats['total']) * 100, 1)
        else:
            stats['present_percentage'] = 0
        
        attendance_stats_by_group.append({
            'group': group,
            'stats': stats,
        })
    
    # Статистика по ДЗ
    homework_stats = Homework.objects.filter(
        schedule_lesson__teacher=request.user,
        created_at__range=[start_date, end_date]
    ).aggregate(
        total=Count('id'),
        with_submissions=Count(Case(When(submissions__isnull=False, then=1), distinct=True)),
    )
    
    # Добавляем отдельный запрос для проверенных работ
    graded_hw_count = Grade.objects.filter(
        teacher=request.user,
        grade_type='HW',
        date__range=[start_date, end_date]
    ).count()
    
    homework_stats['graded'] = graded_hw_count
    
    # Еженедельная активность
    weekly_activity = []
    for i in range(4, -1, -1):  # Последние 5 недель
        week_start = end_date - timedelta(days=(i * 7) + 6)
        week_end = end_date - timedelta(days=i * 7)
        
        grades_count = Grade.objects.filter(
            teacher=request.user,
            date__range=[week_start, week_end]
        ).count()
        
        attendance_count = Attendance.objects.filter(
            schedule_lesson__teacher=request.user,
            date__range=[week_start, week_end]
        ).count()
        
        homework_count = Homework.objects.filter(
            schedule_lesson__teacher=request.user,
            created_at__range=[week_start, week_end]
        ).count()
        
        weekly_activity.append({
            'week': f'{week_start:%d.%m} - {week_end:%d.%m}',
            'grades': grades_count,
            'attendance': attendance_count,
            'homework': homework_count,
        })
    
    # Считаем общее количество оценок
    total_grades = Grade.objects.filter(
        teacher=request.user,
        date__range=[start_date, end_date]
    ).count()
    
    # Считаем среднюю посещаемость
    total_attendance = Attendance.objects.filter(
        schedule_lesson__teacher=request.user,
        date__range=[start_date, end_date]
    ).aggregate(
        total=Count('id'),
        present=Count(Case(When(status='P', then=1))),
    )
    
    if total_attendance['total'] > 0:
        avg_attendance = round((total_attendance['present'] / total_attendance['total']) * 100, 1)
    else:
        avg_attendance = 0
    
    context = {
        'teacher_info': teacher_info,
        'period': {
            'start': start_date,
            'end': end_date,
        },
        'grade_stats_by_subject': grade_stats_by_subject,
        'attendance_stats_by_group': attendance_stats_by_group,
        'homework_stats': homework_stats,
        'weekly_activity': weekly_activity,
        'days': days,
        'total_grades': total_grades,
        'avg_attendance': avg_attendance,
    }
    
    return render(request, 'teacher_portal/statistics.html', context)