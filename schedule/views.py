from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from api.models import StudentGroup, Subject, DailySchedule, ScheduleLesson, TeacherSubject, User
from MPTed_base.decorators import admin_required


from django.views.decorators.csrf import ensure_csrf_cookie

@ensure_csrf_cookie
@login_required
@admin_required
def schedule_dashboard(request):
    """Главная страница расписания"""
    groups = StudentGroup.objects.all().order_by('year', 'name')
    subjects = Subject.objects.all().order_by('name')
    
    group_id = request.GET.get('group_id')
    selected_group = None
    week_schedule = None
    
    if group_id:
        selected_group = get_object_or_404(StudentGroup, id=group_id)
        week_schedule = get_week_schedule(selected_group)
    
    context = {
        'groups': groups,
        'subjects': subjects,
        'selected_group': selected_group,
        'week_schedule': week_schedule,
        'week_days': DailySchedule.WeekDay.choices,
    }
    return render(request, 'dashboard.html', context)


def get_week_schedule(group):
    """Получить расписание на неделю для группы"""
    week_days = DailySchedule.WeekDay.choices
    schedule = []
    
    for day_code, day_name in week_days:
        try:
            daily_schedule = DailySchedule.objects.get(
                student_group=group,
                week_day=day_code
            )
            
            # Если день выходной, не показываем уроки
            if daily_schedule.is_weekend:
                lessons = []
                lesson_count = 0
            else:
                lessons = ScheduleLesson.objects.filter(
                    daily_schedule=daily_schedule
                ).order_by('lesson_number').select_related('subject', 'teacher')
                lesson_count = lessons.count()
            
            schedule.append({
                'day_code': day_code,
                'day_name': day_name,
                'daily_schedule': daily_schedule,
                'lessons': lessons,
                'lesson_count': lesson_count,
                'is_weekend': daily_schedule.is_weekend,
            })
        except DailySchedule.DoesNotExist:
            # Создаем пустой день, если расписания нет
            schedule.append({
                'day_code': day_code,
                'day_name': day_name,
                'daily_schedule': None,
                'lessons': [],
                'lesson_count': 0,
                'is_weekend': False,
            })
    
    return schedule


@csrf_protect
@require_http_methods(["POST"])
@login_required
@admin_required
def toggle_weekend_day(request):
    """Переключить день как выходной"""
    if request.method == 'POST':
        group_id = request.POST.get('group_id')
        day_code = request.POST.get('day_code')
        
        if not group_id or not day_code:
            return JsonResponse({
                'success': False,
                'message': 'Не указаны обязательные параметры'
            }, status=400)
        
        group = get_object_or_404(StudentGroup, id=group_id)
        
        daily_schedule, created = DailySchedule.objects.get_or_create(
            student_group=group,
            week_day=day_code,
            defaults={'is_active': True, 'is_weekend': False}
        )
        
        if day_code != 'SUN':
            daily_schedule.is_weekend = not daily_schedule.is_weekend
            daily_schedule.save()
            status = "установлен как выходной" if daily_schedule.is_weekend else "сделан учебным"
        else:
            status = "всегда выходной день"
        
        return JsonResponse({
            'success': True,
            'message': f'{daily_schedule.get_week_day_display()} {status}',
            'is_weekend': daily_schedule.is_weekend
        })


@csrf_protect
@require_http_methods(["POST"])
@login_required
@admin_required
def add_lesson(request):
    """Добавить урок в расписание"""
    try:
        group_id = request.POST.get('group_id')
        day_code = request.POST.get('day_code')
        lesson_number = int(request.POST.get('lesson_number', 0))
        subject_id = request.POST.get('subject_id')
        teacher_user_id = request.POST.get('teacher_id')  # Это User.id учителя
        
        print(f"DEBUG: group_id={group_id}, day_code={day_code}, lesson_number={lesson_number}, subject_id={subject_id}, teacher_user_id={teacher_user_id}")
        
        if not all([group_id, day_code, lesson_number, subject_id, teacher_user_id]):
            return JsonResponse({
                'success': False,
                'message': 'Не все обязательные поля заполнены'
            }, status=400)
        
        group = get_object_or_404(StudentGroup, id=group_id)
        subject = get_object_or_404(Subject, id=subject_id)
        
        # Получаем пользователя (User) учителя
        teacher_user = get_object_or_404(User, id=teacher_user_id)
        
        # Проверяем, что у пользователя есть профиль учителя
        if not hasattr(teacher_user, 'teacher_profile'):
            return JsonResponse({
                'success': False,
                'message': 'Выбранный пользователь не является учителем'
            }, status=400)
        
        # Проверяем, что учитель ведет этот предмет
        teacher_profile = teacher_user.teacher_profile
        if not TeacherSubject.objects.filter(teacher=teacher_profile, subject=subject).exists():
            return JsonResponse({
                'success': False,
                'message': 'Учитель не ведет этот предмет'
            }, status=400)
        
        # Проверяем количество уроков в день (2-5)
        daily_schedule, created = DailySchedule.objects.get_or_create(
            student_group=group,
            week_day=day_code,
            defaults={'is_active': True, 'is_weekend': False}
        )
        
        # Проверяем, не выходной ли это день
        if daily_schedule.is_weekend:
            return JsonResponse({
                'success': False,
                'message': 'Нельзя добавить урок в выходной день'
            }, status=400)
        
        lesson_count = ScheduleLesson.objects.filter(daily_schedule=daily_schedule).count()
        if lesson_count >= 5:
            return JsonResponse({
                'success': False,
                'message': 'В день не может быть больше 5 уроков'
            }, status=400)
        
        # Проверяем, что урок с таким номером еще не существует
        if ScheduleLesson.objects.filter(
            daily_schedule=daily_schedule,
            lesson_number=lesson_number
        ).exists():
            return JsonResponse({
                'success': False,
                'message': f'Урок с номером {lesson_number} уже существует'
            }, status=400)
        
        # Создаем урок (teacher = User объект)
        lesson = ScheduleLesson.objects.create(
            daily_schedule=daily_schedule,
            lesson_number=lesson_number,
            subject=subject,
            teacher=teacher_user  # Используем User объект
        )
        
        return JsonResponse({
            'success': True,
            'lesson_id': lesson.id,
            'subject_name': subject.name,
            'teacher_name': teacher_user.get_full_name(),
        })
        
    except ValueError as e:
        return JsonResponse({
            'success': False,
            'message': f'Некорректные данные: {str(e)}'
        }, status=400)
    except Exception as e:
        print(f"ERROR in add_lesson: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Ошибка сервера: {str(e)}'
        }, status=500)



@require_http_methods(["DELETE"])
@login_required
@admin_required
def delete_lesson(request, lesson_id):
    """Удалить урок из расписания"""
    lesson = get_object_or_404(ScheduleLesson, id=lesson_id)
    lesson.delete()
    
    return JsonResponse({
        'success': True,
        'message': 'Урок удален'
    })


@csrf_protect
@require_http_methods(["POST"])
@login_required
@admin_required
def update_lesson(request, lesson_id):
    """Обновить урок в расписании"""
    lesson = get_object_or_404(ScheduleLesson, id=lesson_id)
    
    subject_id = request.POST.get('subject_id')
    teacher_user_id = request.POST.get('teacher_id')  # User.id
    
    if subject_id:
        subject = get_object_or_404(Subject, id=subject_id)
        lesson.subject = subject
    
    if teacher_user_id:
        teacher_user = get_object_or_404(User, id=teacher_user_id)
        
        # Проверяем, что это учитель
        if not hasattr(teacher_user, 'teacher_profile'):
            return JsonResponse({
                'success': False,
                'message': 'Выбранный пользователь не является учителем'
            })
        
        # Проверяем, что учитель ведет этот предмет
        if subject_id:
            subject = get_object_or_404(Subject, id=subject_id)
            teacher_profile = teacher_user.teacher_profile
            if not TeacherSubject.objects.filter(teacher=teacher_profile, subject=subject).exists():
                return JsonResponse({
                    'success': False,
                    'message': 'Учитель не ведет этот предмет'
                })
        
        lesson.teacher = teacher_user
    
    lesson.save()
    
    return JsonResponse({
        'success': True,
        'message': 'Урок обновлен'
    })


@login_required
@admin_required
def get_subject_teachers(request, subject_id):
    """Получить учителей по предмету"""
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Получаем TeacherSubjects с данным предметом
    teacher_subjects = TeacherSubject.objects.filter(
        subject=subject
    ).select_related('teacher', 'teacher__user').order_by('teacher__user__last_name')
    
    teachers_list = []
    for teacher_subject in teacher_subjects:
        teacher_profile = teacher_subject.teacher
        user = teacher_profile.user  # User объект учителя
        
        teachers_list.append({
            'id': user.id,  # User.id для использования в форме
            'name': teacher_profile.get_full_name(),
            'qualification': teacher_profile.qualification,
            'email': user.email,
            'teacher_profile_id': teacher_profile.pk,
        })
    
    return JsonResponse({
        'success': True,
        'teachers': teachers_list
    })