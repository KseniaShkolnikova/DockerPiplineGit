from datetime import datetime
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib.auth.models import User, Group
from django.contrib.auth import authenticate, login as django_login, logout as django_logout
from django.views.decorators.http import require_http_methods
from .decorators import custom_login_required, admin_required, student_required
from django.db.models import Q, Count, Avg,  Max, Min

# Импортируем твои модели
from api.models import *

@require_http_methods(["GET"])
def login_page(request):
    """HTML страница авторизации"""
    if request.user.is_authenticated:
        # Если уже авторизован, перенаправляем в зависимости от роли
        if request.user.is_superuser or request.user.groups.filter(name='admin').exists():
            return redirect('admin_dashboard_page')
        return redirect('dashboard_page')  
    return render(request, 'index.html')


@require_http_methods(["POST"])
def login(request):
    """Обработка формы входа (POST запрос)"""
    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    
    print(f"DEBUG: Попытка входа для пользователя: {username}")
    
    if not username or not password:
        return render(request, 'index.html', {'error': 'Логин и пароль обязательны'})
    
    user = authenticate(username=username, password=password)
    
    if user is not None and user.is_active:
        print(f"DEBUG: Пользователь {username} аутентифицирован")
        
        # Логиним пользователя
        django_login(request, user)
        
        # Определяем куда редиректить
        if user.is_superuser or user.groups.filter(name='admin').exists():
            return redirect('admin_dashboard_page')
        elif user.groups.filter(name='teacher').exists():
            # ПЕРЕНАПРАВЛЯЕМ УЧИТЕЛЕЙ НА ИХ ПОРТАЛ
            return redirect('teacher_portal:dashboard')
        elif user.groups.filter(name='student').exists():
            return redirect('student_dashboard')
        else:
            return redirect('dashboard_page')
    
    print(f"DEBUG: Аутентификация не удалась для {username}")
    return render(request, 'index.html', {'error': 'Неверный логин или пароль'})


@require_http_methods(["GET"])
@custom_login_required
def dashboard_page(request):
    """HTML страница дашборда после авторизации"""
    # Проверяем роль пользователя
    if request.user.is_superuser or request.user.groups.filter(name='admin').exists():
        return redirect('admin_dashboard_page')
    
    # Если пользователь - студент, перенаправляем на студенческий дашборд
    if request.user.groups.filter(name='student').exists():
        return redirect('student_dashboard')
    
    # Если пользователь - учитель, перенаправляем на учительский дашборд
    if request.user.groups.filter(name='teacher').exists():
        # ПЕРЕНАПРАВЛЯЕМ НА УЧИТЕЛЬСКИЙ ПОРТАЛ
        return redirect('teacher_portal:dashboard')  # Используем namespace микросервиса
    
    # Для остальных ролей (или если нет шаблона dashboard.html)
    try:
        return render(request, 'dashboard.html')
    except:
        return render(request, 'index.html', {'error': 'Нет доступных страниц для вашей роли'})


@require_http_methods(["GET"])
@custom_login_required
@admin_required
def admin_dashboard_page(request):
    """HTML страница админ панели"""
    
    # Считаем все данные прямо в view
    total_users = User.objects.count()
    
    # Последние пользователи
    recent_users_qs = User.objects.order_by('-date_joined')[:5]
    
    # Подготавливаем данные для шаблона
    recent_users = []
    for user in recent_users_qs:
        role = 'user'
        if user.is_superuser or user.groups.filter(name='admin').exists():
            role = 'admin'
        elif user.groups.filter(name='teacher').exists():
            role = 'teacher'
        elif user.groups.filter(name='student').exists():
            role = 'student'
        
        recent_users.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'email': user.email,
            'date_joined': user.date_joined,
            'role': role
        })
    
    # Получаем остальные данные с обработкой исключений
    try:
        total_subjects = Subject.objects.count()
    except:
        total_subjects = 0
    
    try:
        total_groups = StudentGroup.objects.count()
    except:
        total_groups = 0
    
    try:
        active_homework = Homework.objects.filter(is_active=True).count()
    except:
        active_homework = 0
    
    context = {
        'total_users': total_users,
        'recent_users': recent_users,
        'total_subjects': total_subjects,
        'total_groups': total_groups,
        'active_homework': active_homework,
    }
    
    return render(request, 'admin_dashboard.html', context)


@require_http_methods(["GET"])
def logout_view(request):
    """HTML выход из системы"""
    django_logout(request)
    return redirect('/')


from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.db.models import Q

# ===== СТРАНИЦЫ УПРАВЛЕНИЯ КЛАССАМИ =====

@custom_login_required
@admin_required
def groups_list(request):
    """Список всех классов"""
    groups = StudentGroup.objects.all().select_related('curator').prefetch_related('students')
    
    # Считаем количество учеников в каждом классе
    for group in groups:
        group.student_count = group.students.count()
    
    context = {
        'groups': groups,
    }
    return render(request, 'admin/groups_list.html', context)


@custom_login_required
@admin_required
def group_create(request):
    """Создание нового класса"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        year = request.POST.get('year', '').strip()
        curator_id = request.POST.get('curator', '').strip()
        
        # Валидация
        errors = []
        if not name:
            errors.append('Название класса обязательно')
        if not year or not year.isdigit():
            errors.append('Год обучения должен быть числом')
        else:
            year = int(year)
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Получаем классного руководителя
                curator = None
                if curator_id:
                    curator = User.objects.get(id=curator_id)
                    # Проверяем, что это учитель
                    if not curator.groups.filter(name='teacher').exists() and not curator.teacher_profile.exists():
                        messages.error(request, 'Классным руководителем может быть только учитель')
                        curator = None
                
                # Создаем класс
                group = StudentGroup.objects.create(
                    name=name,
                    year=year,
                    curator=curator
                )
                
                messages.success(request, f'Класс "{group.name}" успешно создан')
                return redirect('groups_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании класса: {str(e)}')
    
    # Получаем всех учителей для выпадающего списка
    teachers = User.objects.filter(
        Q(groups__name='teacher') | Q(teacher_profile__isnull=False)
    ).distinct().order_by('last_name', 'first_name')
    
    context = {
        'teachers': teachers,
    }
    return render(request, 'admin/group_form.html', context)


@custom_login_required
@admin_required
def group_edit(request, group_id):
    """Редактирование класса"""
    group = get_object_or_404(StudentGroup, id=group_id)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        year = request.POST.get('year', '').strip()
        curator_id = request.POST.get('curator', '').strip()
        
        # Валидация
        errors = []
        if not name:
            errors.append('Название класса обязательно')
        if not year or not year.isdigit():
            errors.append('Год обучения должен быть числом')
        else:
            year = int(year)
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Получаем классного руководителя
                curator = None
                if curator_id:
                    curator = User.objects.get(id=curator_id)
                    # Проверяем, что это учитель
                    if not curator.groups.filter(name='teacher').exists() and not curator.teacher_profile.exists():
                        messages.error(request, 'Классным руководителем может быть только учитель')
                        curator = group.curator  # Оставляем текущего
                
                # Обновляем класс
                group.name = name
                group.year = year
                if curator:
                    group.curator = curator
                group.save()
                
                messages.success(request, f'Класс "{group.name}" успешно обновлен')
                return redirect('groups_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении класса: {str(e)}')
    
    # Получаем всех учителей для выпадающего списка
    teachers = User.objects.filter(
        Q(groups__name='teacher') | Q(teacher_profile__isnull=False)
    ).distinct().order_by('last_name', 'first_name')
    
    # Получаем учеников этого класса
    students = StudentProfile.objects.filter(student_group=group).select_related('user')
    
    context = {
        'group': group,
        'teachers': teachers,
        'students': students,
    }
    return render(request, 'admin/group_form.html', context)


@custom_login_required
@admin_required
def group_delete(request, group_id):
    """Удаление класса"""
    group = get_object_or_404(StudentGroup, id=group_id)
    
    if request.method == 'POST':
        group_name = group.name
        group.delete()
        messages.success(request, f'Класс "{group_name}" успешно удален')
        return redirect('groups_list')
    
    # Если GET запрос - редирект на список классов
    return redirect('groups_list')

@custom_login_required
@admin_required
def group_students(request, group_id):
    """Управление учениками в классе"""
    group = get_object_or_404(StudentGroup, id=group_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        student_id = request.POST.get('student_id')
        
        if action == 'add':
            # Добавление ученика в класс
            user = get_object_or_404(User, id=student_id)
            
            # Проверяем, что это ученик
            if not user.groups.filter(name='student').exists():
                return redirect('group_students', group_id=group_id)
            else:
                # Получаем или создаем профиль ученика
                student_profile, created = StudentProfile.objects.get_or_create(
                    user=user,
                    defaults={'course': group.year}  # Устанавливаем курс как у группы
                )
                
                # Проверяем соответствие курса ученика и года группы
                if student_profile.course != group.year:
                    messages.error(
                        request, 
                        f'Нельзя добавить ученика {user.get_full_name()} (курс {student_profile.course}) '
                        f'в группу {group.name} (год {group.year}). '
                        f'Курс ученика должен соответствовать году обучения группы.'
                    )
                else:
                    student_profile.student_group = group
                    student_profile.save()
                    messages.success(request, f'Ученик {user.get_full_name()} добавлен в группу')
        
        elif action == 'remove':
            # Удаление ученика из класса
            student_profile = get_object_or_404(StudentProfile, user_id=student_id)
            student_profile.student_group = None
            student_profile.save()
            messages.success(request, f'Ученик удален из группы')
        
        return redirect('group_students', group_id=group_id)
    
    # Получаем учеников в классе
    students_in_group = StudentProfile.objects.filter(
        student_group=group
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Получаем учеников без класса, но с соответствующим курсом
    students_without_group = StudentProfile.objects.filter(
        student_group__isnull=True,
        user__groups__name='student',
        course=group.year  # Только ученики с соответствующим курсом
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Ищем пользователей без профиля, но с ролью student
    users_without_profile = User.objects.filter(
        groups__name='student'
    ).exclude(
        id__in=StudentProfile.objects.values_list('user_id', flat=True)
    ).order_by('last_name', 'first_name')
    
    context = {
        'group': group,
        'students_in_group': students_in_group,
        'students_without_group': students_without_group,
        'users_without_profile': users_without_profile,
    }
    return render(request, 'admin/group_students.html', context)

@custom_login_required
@admin_required
def subjects_list(request):
    """Список всех предметов"""
    subjects = Subject.objects.all().order_by('name')
    
    # Считаем количество учителей и уроков для каждого предмета
    for subject in subjects:
        subject.teacher_count = TeacherSubject.objects.filter(subject=subject).count()
        subject.lesson_count = ScheduleLesson.objects.filter(subject=subject).count()
    
    context = {
        'subjects': subjects,
    }
    return render(request, 'admin/subjects_list.html', context)


@custom_login_required
@admin_required
def subject_create(request):
    """Создание нового предмета"""
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        # Валидация
        errors = []
        if not name:
            errors.append('Название предмета обязательно')
        elif len(name) < 2:
            errors.append('Название предмета должно быть не менее 2 символов')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Проверяем, нет ли уже предмета с таким названием
                if Subject.objects.filter(name__iexact=name).exists():
                    messages.error(request, 'Предмет с таким названием уже существует')
                else:
                    # Создаем предмет
                    subject = Subject.objects.create(
                        name=name,
                        description=description
                    )
                    return redirect('subjects_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании предмета: {str(e)}')
    
    return render(request, 'admin/subject_form.html')


@custom_login_required
@admin_required
def subject_edit(request, subject_id):
    """Редактирование предмета"""
    subject = get_object_or_404(Subject, id=subject_id)
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        # Валидация
        errors = []
        if not name:
            errors.append('Название предмета обязательно')
        elif len(name) < 2:
            errors.append('Название предмета должно быть не менее 2 символов')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Проверяем, нет ли уже предмета с таким названием (кроме текущего)
                if Subject.objects.filter(name__iexact=name).exclude(id=subject_id).exists():
                    messages.error(request, 'Предмет с таким названием уже существует')
                else:
                    # Обновляем предмет
                    subject.name = name
                    subject.description = description
                    subject.save()
                    return redirect('subjects_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении предмета: {str(e)}')
    
    context = {
        'subject': subject,
    }
    return render(request, 'admin/subject_form.html', context)


@custom_login_required
@admin_required
def subject_delete(request, subject_id):
    """Удаление предмета"""
    subject = get_object_or_404(Subject, id=subject_id)
    
    if request.method == 'POST':
        # Проверяем, не используется ли предмет
        teacher_count = TeacherSubject.objects.filter(subject=subject).count()
        lesson_count = ScheduleLesson.objects.filter(subject=subject).count()
        
        if teacher_count > 0 or lesson_count > 0:
            messages.error(request, f'Невозможно удалить предмет "{subject.name}", так как он используется ({teacher_count} учителей, {lesson_count} уроков)')
            return redirect('subjects_list')
        
        subject_name = subject.name
        subject.delete()
        return redirect('subjects_list')
    
    # Если GET запрос - редирект на список
    return redirect('subjects_list')

# ===== СТРАНИЦЫ УПРАВЛЕНИЯ УЧИТЕЛЯМИ =====

from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.contrib.auth.hashers import make_password

@custom_login_required
@admin_required
def teachers_list(request):
    """Список всех учителей с поиском и фильтрами"""
    # Получаем всех пользователей с ролью teacher
    teachers_qs = User.objects.filter(
        Q(groups__name='teacher') | Q(teacher_profile__isnull=False)
    ).distinct().order_by('last_name', 'first_name')
    
    # Поиск
    search_query = request.GET.get('search', '').strip()
    if search_query:
        teachers_qs = teachers_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(teacher_profile__patronymic__icontains=search_query)
        ).distinct()
    
    # Фильтрация по статусу аккаунта
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        teachers_qs = teachers_qs.filter(is_active=True)
    elif status_filter == 'inactive':
        teachers_qs = teachers_qs.filter(is_active=False)
    
    # Фильтрация по наличию предметов
    subject_filter = request.GET.get('subject', '')
    if subject_filter:
        if subject_filter == 'with_subjects':
            teachers_qs = teachers_qs.filter(
                teacher_profile__teacher_subjects__isnull=False
            ).distinct()
        elif subject_filter == 'without_subjects':
            teachers_qs = teachers_qs.filter(
                teacher_profile__teacher_subjects__isnull=True
            ).distinct()
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(teachers_qs, 20)  # 20 учителей на странице
    page_obj = paginator.get_page(page_number)
    
    # Подготавливаем данные для шаблона
    teachers = []
    for user in page_obj:
        try:
            profile = user.teacher_profile
            patronymic = profile.patronymic
            phone = profile.phone
            qualification = profile.qualification
        except TeacherProfile.DoesNotExist:
            patronymic = ''
            phone = ''
            qualification = ''
        
        # Получаем предметы учителя
        subjects = Subject.objects.filter(
            subject_teachers__teacher__user=user
        ).order_by('name')
        
        teachers.append({
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'patronymic': patronymic,
            'email': user.email,
            'phone': phone,
            'qualification': qualification,
            'is_active': user.is_active,
            'date_joined': user.date_joined,
            'last_login': user.last_login,
            'subject_count': subjects.count(),
            'subjects': subjects[:3],  # Первые 3 предмета для показа
            'all_subjects': list(subjects),  # Все предметы
            'has_profile': hasattr(user, 'teacher_profile'),
        })
    
    # Получаем все предметы для фильтра
    all_subjects = Subject.objects.all().order_by('name')
    
    context = {
        'teachers': teachers,
        'page_obj': page_obj,
        'search_query': search_query,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'total_count': teachers_qs.count(),
        'active_count': User.objects.filter(
            Q(groups__name='teacher') | Q(teacher_profile__isnull=False),
            is_active=True
        ).distinct().count(),
        'inactive_count': User.objects.filter(
            Q(groups__name='teacher') | Q(teacher_profile__isnull=False),
            is_active=False
        ).distinct().count(),
        'all_subjects': all_subjects,
    }
    return render(request, 'admin/teachers_list.html', context)


@custom_login_required
@admin_required
def teacher_create(request):
    """Создание нового учителя"""
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        qualification = request.POST.get('qualification', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Валидация
        errors = []
        
        if not username:
            errors.append('Имя пользователя обязательно')
        elif User.objects.filter(username=username).exists():
            errors.append('Пользователь с таким именем уже существует')
        
        if email and User.objects.filter(email=email).exists():
            errors.append('Пользователь с таким email уже существует')
        
        if not password:
            errors.append('Пароль обязателен')
        elif len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        elif password != confirm_password:
            errors.append('Пароли не совпадают')
        
        if not first_name:
            errors.append('Имя обязательно')
        if not last_name:
            errors.append('Фамилия обязательна')
        if not patronymic:
            errors.append('Отчество обязательно')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Создаем пользователя
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=is_active
                )
                
                # Добавляем в группу teachers
                teacher_group = Group.objects.get(name='teacher')
                user.groups.add(teacher_group)
                
                # Создаем профиль учителя
                TeacherProfile.objects.create(
                    user=user,
                    patronymic=patronymic,
                    phone=phone,
                    qualification=qualification
                )
                
                messages.success(request, f'Учитель {user.get_full_name()} успешно создан')
                return redirect('teachers_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании учителя: {str(e)}')
    
    return render(request, 'admin/teacher_form.html')


@custom_login_required
@admin_required
def teacher_edit(request, teacher_id):
    """Редактирование учителя"""
    user = get_object_or_404(User, id=teacher_id)
    
    # Проверяем, что это учитель
    if not user.groups.filter(name='teacher').exists() and not hasattr(user, 'teacher_profile'):
        messages.error(request, 'Пользователь не является учителем')
        return redirect('teachers_list')
    
    try:
        profile = user.teacher_profile
    except TeacherProfile.DoesNotExist:
        profile = None
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        qualification = request.POST.get('qualification', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Валидация
        errors = []
        
        if not username:
            errors.append('Имя пользователя обязательно')
        elif username != user.username and User.objects.filter(username=username).exists():
            errors.append('Пользователь с таким именем уже существует')
        
        if email and email != user.email and User.objects.filter(email=email).exists():
            errors.append('Пользователь с таким email уже существует')
        
        if password:
            if len(password) < 6:
                errors.append('Пароль должен быть не менее 6 символов')
            elif password != confirm_password:
                errors.append('Пароли не совпадают')
        
        if not first_name:
            errors.append('Имя обязательно')
        if not last_name:
            errors.append('Фамилия обязательна')
        if not patronymic:
            errors.append('Отчество обязательно')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Обновляем пользователя
                user.username = username
                user.email = email
                user.first_name = first_name
                user.last_name = last_name
                user.is_active = is_active
                
                if password:
                    user.password = make_password(password)
                
                user.save()
                
                # Обновляем или создаем профиль
                if profile:
                    profile.patronymic = patronymic
                    profile.phone = phone
                    profile.qualification = qualification
                    profile.save()
                else:
                    TeacherProfile.objects.create(
                        user=user,
                        patronymic=patronymic,
                        phone=phone,
                        qualification=qualification
                    )
                    # Добавляем в группу если не был
                    if not user.groups.filter(name='teacher').exists():
                        teacher_group = Group.objects.get(name='teacher')
                        user.groups.add(teacher_group)
                
                messages.success(request, f'Данные учителя {user.get_full_name()} успешно обновлены')
                return redirect('teachers_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении учителя: {str(e)}')
    
    context = {
        'teacher_user': user,
        'profile': profile,
        'subjects': Subject.objects.filter(subject_teachers__teacher__user=user) if profile else [],
    }
    return render(request, 'admin/teacher_form.html', context)


@custom_login_required
@admin_required
def teacher_toggle_active(request, teacher_id):
    """Блокировка/разблокировка аккаунта учителя"""
    user = get_object_or_404(User, id=teacher_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle':
            user.is_active = not user.is_active
            user.save()
            
            status = "активирован" if user.is_active else "заблокирован"
            messages.success(request, f'Аккаунт учителя {user.get_full_name()} {status}')
        
        return redirect('teachers_list')
    
    # Если GET запрос - редирект на список
    return redirect('teachers_list')


@custom_login_required
@admin_required
def teacher_delete(request, teacher_id):
    """Удаление учителя"""
    user = get_object_or_404(User, id=teacher_id)
    
    if request.method == 'POST':
        # Проверяем, не связан ли учитель с уроками
        lesson_count = ScheduleLesson.objects.filter(teacher=user).count()
        grade_count = Grade.objects.filter(teacher=user).count()
        
        if lesson_count > 0 or grade_count > 0:
            messages.error(request, 
                f'Невозможно удалить учителя "{user.get_full_name()}", так как он ведет уроки '
                f'({lesson_count} уроков) и выставил оценки ({grade_count} оценок)'
            )
            return redirect('teachers_list')
        
        username = user.get_full_name()
        user.delete()
        messages.success(request, f'Учитель {username} успешно удален')
        return redirect('teachers_list')
    
    return redirect('teachers_list')


@custom_login_required
@admin_required
def teacher_subjects(request, teacher_id):
    """Управление предметами учителя"""
    user = get_object_or_404(User, id=teacher_id)
    
    # Проверяем, что это учитель
    if not user.groups.filter(name='teacher').exists():
        messages.error(request, 'Пользователь не является учителем')
        return redirect('teachers_list')
    
    # Получаем или создаем профиль учителя
    profile, created = TeacherProfile.objects.get_or_create(user=user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        subject_id = request.POST.get('subject_id')
        
        if action == 'add' and subject_id:
            subject = get_object_or_404(Subject, id=subject_id)
            
            # Проверяем, не преподает ли уже этот предмет
            if not TeacherSubject.objects.filter(teacher=profile, subject=subject).exists():
                TeacherSubject.objects.create(teacher=profile, subject=subject)
                messages.success(request, f'Предмет "{subject.name}" добавлен учителю')
        
        elif action == 'remove' and subject_id:
            subject = get_object_or_404(Subject, id=subject_id)
            TeacherSubject.objects.filter(teacher=profile, subject=subject).delete()
            messages.success(request, f'Предмет "{subject.name}" удален у учителя')
        
        return redirect('teacher_subjects', teacher_id=teacher_id)
    
    # Получаем предметы, которые преподает учитель
    teacher_subjects = TeacherSubject.objects.filter(teacher=profile).select_related('subject')
    
    # Получаем все доступные предметы (кроме тех, что уже преподает)
    available_subjects = Subject.objects.exclude(
        id__in=teacher_subjects.values_list('subject_id', flat=True)
    ).order_by('name')
    
    # Получаем расписание учителя
    schedule_lessons = ScheduleLesson.objects.filter(teacher=user).select_related(
        'daily_schedule', 'subject', 'daily_schedule__student_group'
    ).order_by('daily_schedule__week_day', 'lesson_number')[:10]  # Последние 10 уроков
    
    context = {
        'teacher_user': user,
        'profile': profile,
        'teacher_subjects': teacher_subjects,
        'available_subjects': available_subjects,
        'schedule_lessons': schedule_lessons,
        'lesson_count': ScheduleLesson.objects.filter(teacher=user).count(),
    }
    return render(request, 'admin/teacher_subjects.html', context)


@custom_login_required
@admin_required
def teacher_detail(request, teacher_id):
    """Детальная информация об учителе"""
    user = get_object_or_404(User, id=teacher_id)
    
    # Проверяем, что это учитель
    if not user.groups.filter(name='teacher').exists():
        messages.error(request, 'Пользователь не является учителем')
        return redirect('teachers_list')
    
    try:
        profile = user.teacher_profile
    except TeacherProfile.DoesNotExist:
        profile = None
    
    # Получаем предметы учителя
    subjects = TeacherSubject.objects.filter(teacher__user=user).select_related('subject')
    
    # Получаем расписание учителя
    schedule_lessons = ScheduleLesson.objects.filter(teacher=user).select_related(
        'daily_schedule', 'subject', 'daily_schedule__student_group'
    ).order_by('daily_schedule__week_day', 'lesson_number')
    
    # Группируем расписание по дням недели
    schedule_by_day = {}
    for lesson in schedule_lessons:
        day = lesson.daily_schedule.get_week_day_display()
        if day not in schedule_by_day:
            schedule_by_day[day] = []
        schedule_by_day[day].append(lesson)
    
    # Получаем классы, в которых преподает учитель
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user
    ).distinct().order_by('year', 'name')
    
    # Получаем статистику по оценкам
    grades_given = Grade.objects.filter(teacher=user).count()
    
    context = {
        'teacher_user': user,
        'profile': profile,
        'subjects': subjects,
        'schedule_by_day': schedule_by_day,
        'teaching_groups': teaching_groups,
        'grades_given': grades_given,
        'lesson_count': schedule_lessons.count(),
    }
    return render(request, 'admin/teacher_detail.html', context)


# Дополнение к views.py (добавить в конец)

# ===== СТРАНИЦЫ УПРАВЛЕНИЯ УЧЕНИКАМИ =====

@custom_login_required
@admin_required
def students_list(request):
    """Список всех учеников с поиском и фильтрацией"""
    # Базовый запрос
    students_qs = StudentProfile.objects.select_related(
        'user', 'student_group'
    ).order_by('user__last_name', 'user__first_name')
    
    # Поиск
    search_query = request.GET.get('search', '').strip()
    if search_query:
        students_qs = students_qs.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(patronymic__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Фильтрация по классу
    group_filter = request.GET.get('group', '')
    if group_filter:
        if group_filter == 'no_group':
            students_qs = students_qs.filter(student_group__isnull=True)
        else:
            students_qs = students_qs.filter(student_group_id=group_filter)
    
    # Фильтрация по курсу
    course_filter = request.GET.get('course', '')
    if course_filter and course_filter.isdigit():
        students_qs = students_qs.filter(course=int(course_filter))
    
    # Фильтрация по статусу аккаунта
    status_filter = request.GET.get('status', '')
    if status_filter == 'active':
        students_qs = students_qs.filter(user__is_active=True)
    elif status_filter == 'inactive':
        students_qs = students_qs.filter(user__is_active=False)
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(students_qs, 25)  # 25 учеников на странице
    page_obj = paginator.get_page(page_number)
    
    # Получаем все классы для фильтра
    all_groups = StudentGroup.objects.all().order_by('year', 'name')
    
    # Статистика
    total_students = students_qs.count()
    active_students = students_qs.filter(user__is_active=True).count()
    inactive_students = total_students - active_students
    
    context = {
        'students': page_obj,
        'page_obj': page_obj,
        'all_groups': all_groups,
        'search_query': search_query,
        'group_filter': group_filter,
        'course_filter': course_filter,
        'status_filter': status_filter,
        'total_count': total_students,
        'active_count': active_students,
        'inactive_count': inactive_students,
    }
    return render(request, 'admin/students_list.html', context)


@custom_login_required
@admin_required
def student_detail(request, student_id):
    """Детальная информация об ученике с оценками и расписанием"""
    student_profile = get_object_or_404(StudentProfile, user_id=student_id)
    student_user = student_profile.user
    
    # Получаем все оценки ученика
    grades = Grade.objects.filter(
        student=student_user
    ).select_related('subject', 'teacher', 'schedule_lesson').order_by('-date')
    
    # Рассчитываем средние оценки по предметам
    subject_grades = {}
    for grade in grades:
        subject_name = grade.subject.name
        if subject_name not in subject_grades:
            subject_grades[subject_name] = {
                'subject': grade.subject,
                'grades': [],
                'average': 0
            }
        subject_grades[subject_name]['grades'].append(grade)
    
    # Вычисляем средние
    for subject_data in subject_grades.values():
        grades_list = [float(g.value) for g in subject_data['grades']]
        subject_data['average'] = round(sum(grades_list) / len(grades_list), 1) if grades_list else 0
    
    # Получаем расписание группы ученика (если есть группа)
    schedule_data = []
    if student_profile.student_group:
        daily_schedules = DailySchedule.objects.filter(
            student_group=student_profile.student_group,
            is_active=True,
            is_weekend=False
        ).prefetch_related('lessons__subject').order_by('week_day')
        
        for day_schedule in daily_schedules:
            lessons = day_schedule.lessons.all().order_by('lesson_number')
            schedule_data.append({
                'day': day_schedule.get_week_day_display(),
                'lessons': lessons
            })
    
    # Получаем домашние задания ученика
    homeworks = Homework.objects.filter(
        student_group=student_profile.student_group
    ).order_by('-created_at')[:5] if student_profile.student_group else []
    
    # Статистика
    total_grades = grades.count()
    homework_grades = grades.filter(grade_type='HW').count()
    test_grades = grades.filter(grade_type='TEST').count()
    
    # Последние оценки (10 последних)
    recent_grades = grades[:10]
    
    context = {
        'student_profile': student_profile,
        'student_user': student_user,
        'subject_grades': subject_grades,
        'schedule_data': schedule_data,
        'homeworks': homeworks,
        'total_grades': total_grades,
        'homework_grades': homework_grades,
        'test_grades': test_grades,
        'recent_grades': recent_grades,
        'grades': grades[:20],  # Ограничиваем для производительности
    }
    return render(request, 'admin/student_detail.html', context)


@custom_login_required
@admin_required
def student_create(request):
    """Создание нового ученика"""
    # Получаем все группы для выпадающего списка
    groups = StudentGroup.objects.all().order_by('year', 'name')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        birth_date = request.POST.get('birth_date', '').strip()
        course = request.POST.get('course', '1').strip()
        address = request.POST.get('address', '').strip()
        group_id = request.POST.get('group', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Валидация
        errors = []
        
        if not username:
            errors.append('Имя пользователя обязательно')
        elif User.objects.filter(username=username).exists():
            errors.append('Пользователь с таким именем уже существует')
        
        if email and User.objects.filter(email=email).exists():
            errors.append('Пользователь с таким email уже существует')
        
        if not password:
            errors.append('Пароль обязателен')
        elif len(password) < 6:
            errors.append('Пароль должен быть не менее 6 символов')
        elif password != confirm_password:
            errors.append('Пароли не совпадают')
        
        if not first_name:
            errors.append('Имя обязательно')
        if not last_name:
            errors.append('Фамилия обязательна')
        if not patronymic:
            errors.append('Отчество обязательно')
        
        if not course or not course.isdigit():
            errors.append('Курс должен быть числом')
        else:
            course_int = int(course)
            if course_int < 1 or course_int > 4:
                errors.append('Курс должен быть от 1 до 4')
            
            # Проверка соответствия группы и курса
            if group_id and group_id.isdigit():
                student_group_obj = StudentGroup.objects.filter(id=int(group_id)).first()
                if student_group_obj:
                    if student_group_obj.year != course_int:
                        errors.append(f'Курс студента ({course_int}) не соответствует году обучения группы ({student_group_obj.year})')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Создаем пользователя
                user = User.objects.create_user(
                    username=username,
                    email=email if email else '',  # Сохраняем email
                    password=password,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=is_active
                )
                
                # Добавляем в группу students
                student_group_role = Group.objects.get(name='student')
                user.groups.add(student_group_role)
                
                # Получаем учебный класс
                student_group_obj = None
                if group_id and group_id.isdigit():
                    student_group_obj = StudentGroup.objects.filter(id=int(group_id)).first()
                
                # Преобразуем дату рождения
                birth_date_obj = None
                if birth_date:
                    try:
                        birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                
                # Создаем профиль ученика
                StudentProfile.objects.create(
                    user=user,
                    patronymic=patronymic,
                    phone=phone,
                    birth_date=birth_date_obj,
                    address=address,
                    course=int(course),
                    student_group=student_group_obj
                )
                
                messages.success(request, f'Ученик {user.get_full_name()} успешно создан')
                return redirect('students_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при создании ученика: {str(e)}')
    
    context = {
        'groups': groups,
    }
    return render(request, 'admin/student_form.html', context)

@custom_login_required
@admin_required
def student_edit(request, student_id):
    """Редактирование ученика"""
    student_profile = get_object_or_404(StudentProfile, user_id=student_id)
    student_user = student_profile.user
    
    # Получаем все группы для выпадающего списка
    groups = StudentGroup.objects.all().order_by('year', 'name')
    
    if request.method == 'POST':
        username = request.POST.get('username', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        birth_date = request.POST.get('birth_date', '').strip()
        course = request.POST.get('course', '1').strip()
        address = request.POST.get('address', '').strip()
        group_id = request.POST.get('group', '').strip()
        is_active = request.POST.get('is_active') == 'on'
        
        # Валидация
        errors = []
        
        if not username:
            errors.append('Имя пользователя обязательно')
        elif username != student_user.username and User.objects.filter(username=username).exists():
            errors.append('Пользователь с таким именем уже существует')
        
        if email and email != student_user.email and User.objects.filter(email=email).exists():
            errors.append('Пользователь с таким email уже существует')
        
        if password:
            if len(password) < 6:
                errors.append('Пароль должен быть не менее 6 символов')
            elif password != confirm_password:
                errors.append('Пароли не совпадают')
        
        if not first_name:
            errors.append('Имя обязательно')
        if not last_name:
            errors.append('Фамилия обязательна')
        if not patronymic:
            errors.append('Отчество обязательно')
        
        if not course or not course.isdigit():
            errors.append('Курс должен быть числом')
        else:
            course_int = int(course)
            if course_int < 1 or course_int > 4:
                errors.append('Курс должен быть от 1 до 4')
            
            # Проверка соответствия группы и курса
            if group_id and group_id.isdigit():
                student_group_obj = StudentGroup.objects.filter(id=int(group_id)).first()
                if student_group_obj:
                    if student_group_obj.year != course_int:
                        errors.append(f'Курс студента ({course_int}) не соответствует году обучения группы ({student_group_obj.year})')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Обновляем пользователя
                student_user.username = username
                student_user.email = email if email else student_user.email
                student_user.first_name = first_name
                student_user.last_name = last_name
                student_user.is_active = is_active
                
                if password:
                    student_user.password = make_password(password)
                
                student_user.save()
                
                # Обновляем профиль
                # Получаем учебный класс
                student_group_obj = None
                if group_id and group_id.isdigit():
                    student_group_obj = StudentGroup.objects.filter(id=int(group_id)).first()
                elif group_id == '':  # Если группа была сброшена
                    student_group_obj = None
                
                # Преобразуем дату рождения
                birth_date_obj = None
                if birth_date:
                    if birth_date == '':  # Если пустая строка - сбрасываем дату
                        birth_date_obj = None
                    else:
                        try:
                            birth_date_obj = datetime.strptime(birth_date, '%Y-%m-%d').date()
                        except ValueError:
                            birth_date_obj = student_profile.birth_date
                
                student_profile.patronymic = patronymic
                student_profile.phone = phone
                student_profile.birth_date = birth_date_obj
                student_profile.address = address
                student_profile.course = int(course)
                student_profile.student_group = student_group_obj
                student_profile.save()
                
                messages.success(request, f'Данные ученика {student_user.get_full_name()} успешно обновлены')
                return redirect('students_list')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении ученика: {str(e)}')
    
    context = {
        'student_profile': student_profile,
        'student_user': student_user,
        'groups': groups,
    }
    return render(request, 'admin/student_form.html', context)

@custom_login_required
@admin_required
def student_toggle_active(request, student_id):
    """Блокировка/разблокировка аккаунта ученика"""
    student_profile = get_object_or_404(StudentProfile, user_id=student_id)
    student_user = student_profile.user
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'toggle':
            student_user.is_active = not student_user.is_active
            student_user.save()
            
            status = "активирован" if student_user.is_active else "заблокирован"
            messages.success(request, f'Аккаунт ученика {student_user.get_full_name()} {status}')
        
        return redirect('students_list')
    
    # Если GET запрос - редирект на список
    return redirect('students_list')


@custom_login_required
@admin_required
def student_delete(request, student_id):
    """Удаление ученика"""
    student_profile = get_object_or_404(StudentProfile, user_id=student_id)
    student_user = student_profile.user
    
    if request.method == 'POST':
        # Проверяем, не связан ли ученик с оценками
        grade_count = Grade.objects.filter(student=student_user).count()
        attendance_count = Attendance.objects.filter(student=student_user).count()
        homework_count = HomeworkSubmission.objects.filter(student=student_user).count()
        
        if grade_count > 0 or attendance_count > 0 or homework_count > 0:
            messages.error(request, 
                f'Невозможно удалить ученика "{student_user.get_full_name()}", так как у него есть '
                f'оценки ({grade_count}), посещаемость ({attendance_count}) и домашние задания ({homework_count})'
            )
            return redirect('students_list')
        
        full_name = student_user.get_full_name()
        
        # Удаляем профиль и пользователя
        student_profile.delete()
        student_user.delete()
        
        messages.success(request, f'Ученик {full_name} успешно удален')
        return redirect('students_list')
    
    return redirect('students_list')

# Добавить в views.py

from datetime import datetime, date, timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Sum

# ===== СТРАНИЦЫ ДЛЯ УЧЕНИКОВ =====

# В существующую функцию student_dashboard добавляем получение объявлений

@custom_login_required
@student_required
def student_dashboard(request):
    """Главная страница ученика"""
    today = timezone.now().date()
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        student_profile = StudentProfile.objects.create(
            user=request.user,
            patronymic='',
            course=1
        )
    
    # Только оценки за СЕГОДНЯ
    recent_grades = Grade.objects.filter(
        student=request.user,
        date=today
    ).select_related('subject', 'teacher').order_by('-date')[:10]
    
    # Расписание на сегодня
    today_schedule = []
    current_week_day = ''
    if student_profile.student_group:
        current_week_day = today.strftime('%a').upper()[:3]
        try:
            daily_schedule = DailySchedule.objects.get(
                student_group=student_profile.student_group,
                week_day=current_week_day,
                is_active=True,
                is_weekend=False
            )
            today_schedule = daily_schedule.lessons.select_related(
                'subject', 'teacher'
            ).order_by('lesson_number')
        except DailySchedule.DoesNotExist:
            today_schedule = []
    
    # Домашние задания
    homeworks = Homework.objects.filter(
        student_group=student_profile.student_group,
        due_date__gte=today
    ).select_related('schedule_lesson__subject').order_by('due_date')[:5] if student_profile.student_group else []
    
    # Считаем средний балл и общее количество оценок
    all_grades = Grade.objects.filter(student=request.user)
    total_grades = all_grades.count()
    
    # Вычисляем средний балл
    avg_result = all_grades.aggregate(avg=Avg('value'))
    average_grade = round(avg_result['avg'], 1) if avg_result['avg'] else 0
    
    # Количество предметов
    subject_count = Subject.objects.filter(
        grades__student=request.user
    ).distinct().count()
    
    # === ВОТ СЮДА ДОБАВЛЯЕМ ОБЪЯВЛЕНИЯ ===
    # Получаем объявления для ученика
    announcements = []
    if student_profile.student_group:
        # Объявления для класса ученика и общие объявления
        announcements = Announcement.objects.filter(
            Q(student_group=student_profile.student_group) | Q(is_for_all=True),
            created_at__gte=today - timedelta(days=7)  # За последние 7 дней
        ).select_related('author', 'student_group').order_by('-created_at')[:10]
    
    # Считаем количество непрочитанных объявлений
    announcements_count = announcements.count()
    
    context = {
        'student_profile': student_profile,
        'today_schedule': today_schedule,
        'homeworks': homeworks,
        'recent_grades': recent_grades,
        'today': today,
        'current_week_day': current_week_day,
        'total_grades': total_grades,
        'average_grade': average_grade,
        'subject_count': subject_count,
        # Добавляем объявления в контекст
        'announcements': announcements,
        'announcements_count': announcements_count,
    }
    return render(request, 'student/dashboard.html', context)

@custom_login_required
@student_required 
def student_schedule(request):
    """Расписание ученика"""
    if not request.user.groups.filter(name='student').exists():
        messages.error(request, 'Доступ только для учеников')
        return redirect('dashboard_page')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        student_profile = None
    
    # Получаем расписание на всю неделю
    weekly_schedule = []
    if student_profile and student_profile.student_group:
        week_days = ['MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT']
        
        for day_code in week_days:
            try:
                daily_schedule = DailySchedule.objects.get(
                    student_group=student_profile.student_group,
                    week_day=day_code,
                    is_active=True,
                    is_weekend=False
                )
                lessons = daily_schedule.lessons.select_related(
                    'subject', 'teacher'
                ).order_by('lesson_number')
                
                weekly_schedule.append({
                    'day_code': day_code,
                    'day_name': daily_schedule.get_week_day_display(),
                    'lessons': lessons,
                    'is_weekend': daily_schedule.is_weekend,
                    'is_active': daily_schedule.is_active,
                })
            except DailySchedule.DoesNotExist:
                weekly_schedule.append({
                    'day_code': day_code,
                    'day_name': dict(DailySchedule.WeekDay.choices).get(day_code, day_code),
                    'lessons': [],
                    'is_weekend': False,
                    'is_active': False,
                })
    
    context = {
        'student_profile': student_profile,
        'weekly_schedule': weekly_schedule,
    }
    return render(request, 'student/schedule.html', context)


@custom_login_required
@student_required
def student_grades(request):
    """Оценки ученика - таблица по предметам"""
    # Получаем все предметы, по которым есть оценки
    subjects_with_grades = Subject.objects.filter(
        grades__student=request.user
    ).distinct().order_by('name')
    
    # Подготавливаем данные для таблицы
    subject_data = []
    for subject in subjects_with_grades:
        # Получаем все оценки по предмету
        grades = Grade.objects.filter(
            student=request.user,
            subject=subject
        ).order_by('-date')
        
        # Вычисляем средний балл
        average = grades.aggregate(avg=Avg('value'))['avg'] or 0
        
        subject_data.append({
            'subject': subject,
            'grades': grades,
            'average': round(average, 1),
            'count': grades.count(),
        })
    
    # Статистика для круговой диаграммы
    all_grades = Grade.objects.filter(student=request.user)
    total_grades = all_grades.count()
    
    # Группируем оценки по значениям
    grade_stats = {}
    for value in [2, 3, 4, 5]:
        count = all_grades.filter(value=value).count()
        if count > 0:
            percentage = round((count / total_grades) * 100, 1) if total_grades > 0 else 0
            grade_stats[value] = {
                'count': count,
                'percentage': percentage
            }
    
    context = {
        'subject_data': subject_data,
        'total_grades': total_grades,
        'grade_stats': grade_stats,
        'student_profile': request.user.student_profile if hasattr(request.user, 'student_profile') else None,
    }
    return render(request, 'student/grades.html', context)

@custom_login_required
@student_required
def student_homework(request):
    """Домашние задания ученика"""
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        student_profile = None
    
    # Предметы для фильтра
    subjects = Subject.objects.filter(
        schedule_lessons__daily_schedule__student_group=student_profile.student_group
    ).distinct().order_by('name') if student_profile and student_profile.student_group else Subject.objects.none()
    
    # Фильтры
    status_filter = request.GET.get('status', '')
    subject_filter = request.GET.get('subject', '')
    
    # Базовый запрос
    homeworks_qs = Homework.objects.filter(
        student_group=student_profile.student_group
    ).select_related('schedule_lesson__subject') if student_profile and student_profile.student_group else Homework.objects.none()
    
    homeworks_qs = homeworks_qs.order_by('due_date')
    
    # Применяем фильтры
    if status_filter == 'active':
        homeworks_qs = homeworks_qs.filter(due_date__gte=timezone.now())
    elif status_filter == 'overdue':
        homeworks_qs = homeworks_qs.filter(due_date__lt=timezone.now())
    
    if subject_filter:
        homeworks_qs = homeworks_qs.filter(schedule_lesson__subject_id=subject_filter)
    
    # Получаем отправленные работы
    submissions = HomeworkSubmission.objects.filter(
        student=request.user
    ).select_related('homework')
    
    # Создаем словарь для быстрой проверки
    submission_dict = {sub.homework_id: sub for sub in submissions}
    
    context = {
        'homeworks': homeworks_qs,
        'subjects': subjects,
        'submission_dict': submission_dict,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
        'student_profile': student_profile,
    }
    return render(request, 'student/homework.html', context)

@custom_login_required
@student_required 
def student_attendance(request):
    """Посещаемость ученика"""
    if not request.user.groups.filter(name='student').exists():
        messages.error(request, 'Доступ только для учеников')
        return redirect('dashboard_page')
    
    # Фильтры
    month_filter = request.GET.get('month', '')
    subject_filter = request.GET.get('subject', '')
    
    # Определяем месяц для фильтрации
    today = timezone.now().date()
    if month_filter:
        try:
            year, month = map(int, month_filter.split('-'))
            start_date = date(year, month, 1)
            end_date = date(year, month + 1, 1) if month < 12 else date(year + 1, 1, 1)
        except (ValueError, IndexError):
            start_date = date(today.year, today.month, 1)
            end_date = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
    else:
        start_date = date(today.year, today.month, 1)
        end_date = date(today.year, today.month + 1, 1) if today.month < 12 else date(today.year + 1, 1, 1)
    
    # Получаем посещаемость
    attendance_qs = Attendance.objects.filter(
        student=request.user,
        date__gte=start_date,
        date__lt=end_date
    ).select_related(
        'schedule_lesson__subject',
        'schedule_lesson__daily_schedule'
    ).order_by('-date')
    
    # Фильтрация по предмету
    if subject_filter:
        attendance_qs = attendance_qs.filter(schedule_lesson__subject_id=subject_filter)
    
    # Группируем по дате
    attendance_by_date = {}
    for record in attendance_qs:
        date_str = record.date.strftime('%Y-%m-%d')
        if date_str not in attendance_by_date:
            attendance_by_date[date_str] = {
                'date': record.date,
                'records': []
            }
        attendance_by_date[date_str]['records'].append(record)
    
    # Считаем статистику
    total_lessons = attendance_qs.count()
    present_count = attendance_qs.filter(status='P').count()
    absent_count = attendance_qs.filter(status='A').count()
    late_count = attendance_qs.filter(status='L').count()
    
    # Предметы для фильтра
    subjects = Subject.objects.filter(
        schedule_lessons__attendances__student=request.user
    ).distinct().order_by('name')
    
    # Генерируем список месяцев для выбора
    months = []
    for i in range(6):  # Последние 6 месяцев
        month_date = today - timedelta(days=30*i)
        months.append(month_date.strftime('%Y-%m'))
    
    context = {
        'attendance_by_date': attendance_by_date.values(),
        'total_lessons': total_lessons,
        'present_count': present_count,
        'absent_count': absent_count,
        'late_count': late_count,
        'attendance_rate': round((present_count / total_lessons * 100), 1) if total_lessons > 0 else 0,
        'subjects': subjects,
        'months': months,
        'selected_month': month_filter or today.strftime('%Y-%m'),
        'subject_filter': subject_filter,
        'start_date': start_date,
        'end_date': end_date,
    }
    return render(request, 'student/attendance.html', context)


@custom_login_required
@student_required 
def student_profile_view(request):
    """Профиль ученика"""
    if not request.user.groups.filter(name='student').exists():
        messages.error(request, 'Доступ только для учеников')
        return redirect('dashboard_page')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        student_profile = StudentProfile.objects.create(
            user=request.user,
            patronymic='',
            course=1
        )
    
    if request.method == 'POST':
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        birth_date = request.POST.get('birth_date', '').strip()
        address = request.POST.get('address', '').strip()
        
        # Обновляем профиль
        student_profile.patronymic = patronymic
        student_profile.phone = phone
        
        if birth_date:
            try:
                student_profile.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
            except ValueError:
                pass
        
        student_profile.address = address
        student_profile.save()
        
        messages.success(request, 'Профиль успешно обновлен')
        return redirect('student_profile')
    
    context = {
        'student_profile': student_profile,
    }
    return render(request, 'student/profile.html', context)


@custom_login_required
@student_required 
def student_announcements(request):
    """Объявления для ученика"""
    if not request.user.groups.filter(name='student').exists():
        messages.error(request, 'Доступ только для учеников')
        return redirect('dashboard_page')
    
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        student_profile = None
    
    # Получаем объявления
    announcements_qs = Announcement.objects.filter(
        Q(student_group=student_profile.student_group) | Q(is_for_all=True)
    ).select_related('author', 'student_group').order_by('-created_at')
    
    # Фильтрация
    group_filter = request.GET.get('group', '')
    if group_filter == 'all':
        announcements_qs = announcements_qs.filter(is_for_all=True)
    elif group_filter and group_filter != 'all':
        announcements_qs = announcements_qs.filter(student_group_id=group_filter)
    
    # Пагинация
    page_number = request.GET.get('page', 1)
    paginator = Paginator(announcements_qs, 15)
    page_obj = paginator.get_page(page_number)
    
    # Группы для фильтра (только те, к которым ученик принадлежит)
    groups = StudentGroup.objects.filter(
        Q(announcements__isnull=False) | Q(students__user=request.user)
    ).distinct().order_by('year', 'name') if student_profile else []
    
    context = {
        'announcements': page_obj,
        'page_obj': page_obj,
        'groups': groups,
        'group_filter': group_filter,
        'student_profile': student_profile,
    }
    return render(request, 'student/announcements.html', context)
# Добавьте в views.py

@require_http_methods(["POST"])
@custom_login_required
@student_required 
def submit_homework(request):
    """Обработка сдачи домашнего задания"""
    if not request.user.groups.filter(name='student').exists():
        return JsonResponse({'error': 'Доступ только для учеников'}, status=403)
    
    homework_id = request.POST.get('homework_id')
    submission_text = request.POST.get('submission_text', '')
    submission_file = request.FILES.get('submission_file')
    
    if not homework_id:
        return JsonResponse({'error': 'ID задания не указан'}, status=400)
    
    try:
        homework = Homework.objects.get(id=homework_id)
        
        # Проверяем, не сдавал ли уже ученик это задание
        if HomeworkSubmission.objects.filter(
            homework=homework, 
            student=request.user
        ).exists():
            return JsonResponse({'error': 'Вы уже сдали это задание'}, status=400)
        
        # Проверяем срок сдачи
        if homework.due_date < timezone.now():
            return JsonResponse({'error': 'Срок сдачи истек'}, status=400)
        
        # Проверяем, что файл не превышает 10MB
        if submission_file and submission_file.size > 10 * 1024 * 1024:
            return JsonResponse({'error': 'Файл слишком большой (макс. 10MB)'}, status=400)
        
        # Создаем отправку
        submission = HomeworkSubmission.objects.create(
            homework=homework,
            student=request.user,
            submission_text=submission_text,
            submitted_at=timezone.now()
        )
        
        if submission_file:
            submission.submission_file = submission_file
            submission.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Работа успешно сдана'
        })
        
    except Homework.DoesNotExist:
        return JsonResponse({'error': 'Задание не найдено'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    
@custom_login_required
@student_required
def homework_detail(request, homework_id):
    """Детальная страница домашнего задания"""
    homework = get_object_or_404(Homework, id=homework_id)
    
    # Проверяем, что задание для класса студента
    student_profile = get_object_or_404(StudentProfile, user=request.user)
    if homework.student_group != student_profile.student_group:
        messages.error(request, 'Доступ запрещен')
        return redirect('student_homework')
    
    # Получаем отправку студента (если есть)
    submission = HomeworkSubmission.objects.filter(
        homework=homework,
        student=request.user
    ).first()
    
    context = {
        'homework': homework,
        'submission': submission,
        'student_profile': student_profile,
    }
    return render(request, 'student/homework_detail.html', context)

@require_http_methods(["POST"])
@custom_login_required
@student_required
def delete_submission(request, submission_id):
    """Удаление отправленной работы"""
    submission = get_object_or_404(HomeworkSubmission, id=submission_id, student=request.user)
    
    # Проверяем, можно ли удалить (если срок не истек)
    if submission.homework.due_date < timezone.now():
        messages.error(request, 'Нельзя удалить работу после срока сдачи')
    else:
        submission.delete()
        messages.success(request, 'Работа удалена')
    
    return redirect('student_homework')


from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm

@require_http_methods(["POST"])
@custom_login_required
@student_required
def change_password(request):
    """Смена пароля пользователя"""
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        
        if form.is_valid():
            user = form.save()
            # Обновляем сессию, чтобы пользователь не разлогинился
            update_session_auth_hash(request, user)
            messages.success(request, 'Пароль успешно изменен!')
        else:
            for error in form.errors.values():
                messages.error(request, error[0])
        
        return redirect('student_profile')
    
    return redirect('student_profile')


@custom_login_required
@student_required
def student_profile_view(request):
    """Профиль ученика"""
    # Получаем или создаем профиль ученика
    try:
        student_profile = StudentProfile.objects.get(user=request.user)
    except StudentProfile.DoesNotExist:
        # Создаем профиль с базовыми данными
        student_profile = StudentProfile.objects.create(
            user=request.user,
            patronymic='',
            course=1
        )
        messages.info(request, 'Пожалуйста, заполните свой профиль')
    
    if request.method == 'POST':
        # Получаем данные из формы
        last_name = request.POST.get('last_name', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        patronymic = request.POST.get('patronymic', '').strip()
        phone = request.POST.get('phone', '').strip()
        birth_date = request.POST.get('birth_date', '').strip()
        address = request.POST.get('address', '').strip()
        email = request.POST.get('email', '').strip()
        
        # Валидация обязательных полей
        errors = []
        if not last_name:
            errors.append('Фамилия обязательна')
        if not first_name:
            errors.append('Имя обязательно')
        if not patronymic:
            errors.append('Отчество обязательно')
        
        if errors:
            for error in errors:
                messages.error(request, error)
        else:
            try:
                # Обновляем пользователя
                user = request.user
                user.last_name = last_name
                user.first_name = first_name
                
                if email and email != user.email:
                    # Проверяем, не занят ли email
                    if User.objects.filter(email=email).exclude(id=user.id).exists():
                        messages.error(request, 'Этот email уже используется')
                    else:
                        user.email = email
                
                user.save()
                
                # Обновляем профиль ученика
                student_profile.patronymic = patronymic
                student_profile.phone = phone
                student_profile.address = address
                
                if birth_date:
                    try:
                        student_profile.birth_date = datetime.strptime(birth_date, '%Y-%m-%d').date()
                    except ValueError:
                        student_profile.birth_date = None
                else:
                    student_profile.birth_date = None
                
                student_profile.save()
                
                messages.success(request, 'Профиль успешно обновлен')
                return redirect('student_profile')
                
            except Exception as e:
                messages.error(request, f'Ошибка при обновлении профиля: {str(e)}')
    
    context = {
        'student_profile': student_profile,
    }
    return render(request, 'student/profile.html', context)

# ===== АУДИТ ЛОГОВ =====

from django.contrib.admin.views.decorators import staff_member_required
from django.utils import timezone
from django.db.models import Q, Count
from datetime import datetime, timedelta

@custom_login_required
@admin_required
def audit_logs(request):
    """Просмотр логов аудита"""
    # Получаем все логи
    logs_qs = AuditLog.objects.select_related('user').order_by('-timestamp')
    
    # Фильтры
    action_filter = request.GET.get('action', '')
    model_filter = request.GET.get('model', '')
    user_filter = request.GET.get('user', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Применяем фильтры
    if action_filter:
        logs_qs = logs_qs.filter(action=action_filter)
    
    if model_filter:
        logs_qs = logs_qs.filter(model_name=model_filter)
    
    if user_filter and user_filter.isdigit():
        logs_qs = logs_qs.filter(user_id=int(user_filter))
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            logs_qs = logs_qs.filter(timestamp__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            logs_qs = logs_qs.filter(timestamp__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        logs_qs = logs_qs.filter(
            Q(model_name__icontains=search_query) |
            Q(object_id__icontains=search_query) |
            Q(user__username__icontains=search_query) |
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query)
        )
    
    # Статистика
    total_logs = logs_qs.count()
    
    # Статистика по действиям
    action_stats = AuditLog.objects.values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Статистика по моделям
    model_stats = AuditLog.objects.values('model_name').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Пагинация
    from django.core.paginator import Paginator
    page_number = request.GET.get('page', 1)
    paginator = Paginator(logs_qs, 50)  # 50 логов на странице
    page_obj = paginator.get_page(page_number)
    
    # Получаем уникальные значения для фильтров
    users_with_logs = User.objects.filter(
        audit_logs__isnull=False
    ).distinct().order_by('username')
    
    # Подготавливаем данные логов
    logs = []
    for log in page_obj:
        changes_summary = ''
        if log.action == 'CREATE':
            changes_summary = f'Создан объект {log.model_name}'
            if log.new_values:
                # Показываем основные поля
                fields = []
                for key in list(log.new_values.keys())[:3]:  # Показываем первые 3 поля
                    if key not in ['id', 'created_at', 'updated_at']:
                        value = log.new_values.get(key, '')
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:50] + '...'
                        fields.append(f"{key}: {value}")
                if fields:
                    changes_summary = "Поля: " + ", ".join(fields)
        elif log.action == 'UPDATE' and log.old_values and log.new_values:
            changes = []
            for field in log.old_values:
                if field in log.new_values and log.old_values[field] != log.new_values[field]:
                    old_val = str(log.old_values[field])
                    new_val = str(log.new_values[field])
                    
                    # Обрезаем длинные значения
                    if len(old_val) > 30:
                        old_val = old_val[:30] + '...'
                    if len(new_val) > 30:
                        new_val = new_val[:30] + '...'
                    
                    changes.append(f"{field}: {old_val} → {new_val}")
            if changes:
                changes_summary = "Изменения: " + ", ".join(changes[:3])  # Показываем первые 3 изменения
                if len(changes) > 3:
                    changes_summary += f" ...и еще {len(changes) - 3}"
        
        logs.append({
            'id': log.id,
            'user': log.user,
            'action': log.action,
            'action_display': log.get_action_display(),
            'model_name': log.model_name,
            'object_id': log.object_id,
            'changes_summary': changes_summary,
            'timestamp': log.timestamp,
            'ip_address': log.ip_address,
            'user_agent': log.user_agent,
            'request_path': log.request_path,
            'request_method': log.request_method,
            'old_values': log.old_values,
            'new_values': log.new_values,
            'is_system_action': log.is_system_action,
        })
    
    # Определяем доступные модели из логов
    available_models = AuditLog.objects.values_list(
        'model_name', flat=True
    ).distinct().order_by('model_name')
    
    context = {
        'logs': logs,
        'page_obj': page_obj,
        'total_logs': total_logs,
        'action_stats': action_stats,
        'model_stats': model_stats,
        'users_with_logs': users_with_logs,
        'available_models': available_models,
        'action_choices': AuditLog.ActionType.choices,
        'action_filter': action_filter,
        'model_filter': model_filter,
        'user_filter': user_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'today': timezone.now().date(),
        'yesterday': (timezone.now() - timedelta(days=1)).date(),
        'week_ago': (timezone.now() - timedelta(days=7)).date(),
    }
    return render(request, 'admin/audit_logs.html', context)


@custom_login_required
@admin_required
def audit_log_detail(request, log_id):
    """Детальный просмотр записи аудита"""
    log = get_object_or_404(AuditLog, id=log_id)
    
    # Форматируем JSON данные для красивого отображения
    def format_json_data(data):
        if not data:
            return None
        import json
        try:
            return json.dumps(data, indent=2, ensure_ascii=False)
        except:
            return str(data)
    
    context = {
        'log': log,
        'old_values_formatted': format_json_data(log.old_values),
        'new_values_formatted': format_json_data(log.new_values),
        'action_choices': dict(AuditLog.ActionType.choices),
    }
    return render(request, 'admin/audit_log_detail.html', context)


@require_http_methods(["POST"])
@custom_login_required
@admin_required
def clear_audit_logs(request):
    """Очистка старых логов аудита"""
    if request.method == 'POST':
        days_to_keep = request.POST.get('days_to_keep', '90')
        
        try:
            days = int(days_to_keep)
            if days < 1:
                days = 90
            
            # Удаляем логи старше указанного количества дней
            cutoff_date = timezone.now() - timedelta(days=days)
            deleted_count, _ = AuditLog.objects.filter(
                timestamp__lt=cutoff_date
            ).delete()
            
            messages.success(request, f'Удалено {deleted_count} записей аудита старше {days} дней')
        except ValueError:
            messages.error(request, 'Неверное количество дней')
        
        return redirect('admin/audit_logs')
    
    return redirect('admin/audit_logs')


# ===== ПРОСМОТР ОЦЕНОК И СТАТИСТИКИ ПО ГРУППАМ =====

@custom_login_required
@admin_required
def group_grades_overview(request):
    """Обзор оценок по группам"""
    # Получаем все группы
    groups = StudentGroup.objects.all().select_related('curator').order_by('year', 'name')
    
    # Статистика по группам
    groups_stats = []
    for group in groups:
        # Количество учеников в группе
        student_count = StudentProfile.objects.filter(student_group=group).count()
        
        # Средняя оценка по группе
        avg_grade_result = Grade.objects.filter(
            student__student_profile__student_group=group
        ).aggregate(avg=Avg('value'))
        avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
        
        # Количество оценок
        grades_count = Grade.objects.filter(
            student__student_profile__student_group=group
        ).count()
        
        groups_stats.append({
            'group': group,
            'student_count': student_count,
            'avg_grade': avg_grade,
            'grades_count': grades_count,
        })
    
    context = {
        'groups_stats': groups_stats,
    }
    return render(request, 'admin/group_grades_overview.html', context)


@custom_login_required
@admin_required
def group_grades_detail(request, group_id):
    """Детальная статистика оценок по группе"""
    group = get_object_or_404(StudentGroup, id=group_id)
    
    # Получаем предметы, которые есть у группы в расписании
    subjects_in_schedule = Subject.objects.filter(
        schedule_lessons__daily_schedule__student_group=group
    ).distinct().order_by('name')
    
    # Получаем всех учеников группы
    students = StudentProfile.objects.filter(
        student_group=group
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Статистика по предметам
    subjects_stats = []
    for subject in subjects_in_schedule:
        # Учителя, которые ведут этот предмет в этой группе
        teachers = User.objects.filter(
            schedule_lessons__daily_schedule__student_group=group,
            schedule_lessons__subject=subject
        ).distinct()
        
        # Оценки по этому предмету в группе
        grades = Grade.objects.filter(
            student__student_profile__student_group=group,
            subject=subject
        )
        
        # Средняя оценка по предмету
        avg_result = grades.aggregate(avg=Avg('value'))
        avg_grade = round(avg_result['avg'], 1) if avg_result['avg'] else 0
        
        # Количество оценок
        grades_count = grades.count()
        
        # Распределение оценок
        grade_distribution = {}
        for value in [5, 4, 3, 2]:
            count = grades.filter(value=value).count()
            if count > 0:
                grade_distribution[value] = count
        
        subjects_stats.append({
            'subject': subject,
            'teachers': teachers,
            'avg_grade': avg_grade,
            'grades_count': grades_count,
            'grade_distribution': grade_distribution,
        })
    
    # Общая статистика по группе
    all_grades = Grade.objects.filter(
        student__student_profile__student_group=group
    )
    
    total_grades = all_grades.count()
    overall_avg_result = all_grades.aggregate(avg=Avg('value'))
    overall_avg = round(overall_avg_result['avg'], 1) if overall_avg_result['avg'] else 0
    
    # Статистика по типам оценок
    grade_types_stats = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        count = all_grades.filter(grade_type=grade_type_code).count()
        if count > 0:
            avg_result = all_grades.filter(grade_type=grade_type_code).aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            grade_types_stats.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
            })
    
    # Последние оценки в группе
    recent_grades = all_grades.select_related(
        'student', 'subject', 'teacher'
    ).order_by('-date')[:10]
    
    context = {
        'group': group,
        'students': students,
        'subjects_stats': subjects_stats,
        'total_grades': total_grades,
        'overall_avg': overall_avg,
        'grade_types_stats': grade_types_stats,
        'recent_grades': recent_grades,
        'student_count': students.count(),
    }
    return render(request, 'admin/group_grades_detail.html', context)


@custom_login_required
@admin_required
def group_subject_grades(request, group_id, subject_id):
    """Оценки по конкретному предмету в группе"""
    group = get_object_or_404(StudentGroup, id=group_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Проверяем, есть ли этот предмет в расписании группы
    if not ScheduleLesson.objects.filter(
        daily_schedule__student_group=group,
        subject=subject
    ).exists():
        messages.error(request, f'Предмет "{subject.name}" не входит в расписание группы {group.name}')
        return redirect('group_grades_detail', group_id=group_id)
    
    # Получаем всех учеников группы
    students = StudentProfile.objects.filter(
        student_group=group
    ).select_related('user').order_by('user__last_name', 'user__first_name')
    
    # Получаем учителей, которые ведут этот предмет в группе
    teachers = User.objects.filter(
        schedule_lessons__daily_schedule__student_group=group,
        schedule_lessons__subject=subject
    ).distinct()
    
    # Собираем оценки по ученикам
    students_grades = []
    for student_profile in students:
        grades = Grade.objects.filter(
            student=student_profile.user,
            subject=subject
        ).order_by('-date')
        
        # Средняя оценка ученика по предмету
        avg_result = grades.aggregate(avg=Avg('value'))
        avg_grade = round(avg_result['avg'], 1) if avg_result['avg'] else 0
        
        # Количество оценок
        grades_count = grades.count()
        
        # Последние 5 оценок
        recent_grades = grades[:5]
        
        students_grades.append({
            'student': student_profile,
            'grades': grades,
            'avg_grade': avg_grade,
            'grades_count': grades_count,
            'recent_grades': recent_grades,
        })
    
    # Общая статистика по предмету в группе
    all_grades = Grade.objects.filter(
        student__student_profile__student_group=group,
        subject=subject
    )
    
    total_grades = all_grades.count()
    overall_avg_result = all_grades.aggregate(avg=Avg('value'))
    overall_avg = round(overall_avg_result['avg'], 1) if overall_avg_result['avg'] else 0
    
    # Распределение оценок
    grade_distribution = {}
    for value in [5, 4, 3, 2]:
        count = all_grades.filter(value=value).count()
        percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
        if count > 0:
            grade_distribution[value] = {
                'count': count,
                'percentage': percentage
            }
    
    # Статистика по типам оценок для этого предмета
    grade_types_stats = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        count = all_grades.filter(grade_type=grade_type_code).count()
        if count > 0:
            avg_result = all_grades.filter(grade_type=grade_type_code).aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            grade_types_stats.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
                'percentage': percentage,
            })
    
    context = {
        'group': group,
        'subject': subject,
        'teachers': teachers,
        'students_grades': students_grades,
        'total_grades': total_grades,
        'overall_avg': overall_avg,
        'grade_distribution': grade_distribution,
        'grade_types_stats': grade_types_stats,
    }
    return render(request, 'admin/group_subject_grades.html', context)


# ===== ПРОСМОТР ИНФОРМАЦИИ ОБ УЧИТЕЛЯХ =====

@custom_login_required
@admin_required
def teachers_overview(request):
    """Обзорная страница учителей с подробной информацией"""
    # Получаем всех учителей
    teachers_qs = User.objects.filter(
        Q(groups__name='teacher') | Q(teacher_profile__isnull=False)
    ).distinct().order_by('last_name', 'first_name')
    
    # Фильтры
    search_query = request.GET.get('search', '').strip()
    if search_query:
        teachers_qs = teachers_qs.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(teacher_profile__patronymic__icontains=search_query)
        ).distinct()
    
    # Подготавливаем детальную информацию об учителях
    teachers_info = []
    for user in teachers_qs:
        try:
            profile = user.teacher_profile
            patronymic = profile.patronymic
            phone = profile.phone
            qualification = profile.qualification
            birth_date = profile.birth_date
        except TeacherProfile.DoesNotExist:
            patronymic = ''
            phone = ''
            qualification = ''
            birth_date = None
        
        # Получаем предметы учителя
        subjects = TeacherSubject.objects.filter(
            teacher__user=user
        ).select_related('subject')
        
        # Группы, в которых преподает учитель
        teaching_groups = StudentGroup.objects.filter(
            daily_schedules__lessons__teacher=user
        ).distinct().order_by('year', 'name')
        
        # Расписание учителя
        schedule_lessons = ScheduleLesson.objects.filter(
            teacher=user
        ).select_related(
            'daily_schedule', 'subject', 'daily_schedule__student_group'
        ).order_by('daily_schedule__week_day', 'lesson_number')
        
        # Статистика по оценкам
        grades_stats = Grade.objects.filter(
            teacher=user
        ).aggregate(
            total=Count('id'),
            avg=Avg('value'),
            latest=Max('date')
        )
        
        # Количество учеников у учителя (через оценки)
        unique_students = Grade.objects.filter(
            teacher=user
        ).values('student').distinct().count()
        
        teachers_info.append({
            'id': user.id,
            'user': user,
            'profile': profile if hasattr(user, 'teacher_profile') else None,
            'patronymic': patronymic,
            'phone': phone,
            'qualification': qualification,
            'birth_date': birth_date,
            'subjects': subjects,
            'teaching_groups': teaching_groups,
            'schedule_lessons': schedule_lessons,
            'grades_total': grades_stats['total'] or 0,
            'grades_avg': round(grades_stats['avg'], 1) if grades_stats['avg'] else 0,
            'grades_latest': grades_stats['latest'],
            'unique_students': unique_students,
            'subject_count': subjects.count(),
            'group_count': teaching_groups.count(),
            'lesson_count': schedule_lessons.count(),
        })
    
    # Общая статистика
    total_teachers = teachers_qs.count()
    active_teachers = teachers_qs.filter(is_active=True).count()
    
    # Статистика по предметам среди учителей
    subject_stats = Subject.objects.filter(
        subject_teachers__isnull=False
    ).annotate(
        teacher_count=Count('subject_teachers', distinct=True)
    ).order_by('-teacher_count')[:10]
    
    context = {
        'teachers_info': teachers_info,
        'search_query': search_query,
        'total_teachers': total_teachers,
        'active_teachers': active_teachers,
        'subject_stats': subject_stats,
    }
    return render(request, 'admin/teachers_overview.html', context)


@custom_login_required
@admin_required
def teacher_full_detail(request, teacher_id):
    """Полная детальная информация об учителе"""
    user = get_object_or_404(User, id=teacher_id)
    
    # Проверяем, что это учитель
    if not user.groups.filter(name='teacher').exists() and not hasattr(user, 'teacher_profile'):
        messages.error(request, 'Пользователь не является учителем')
        return redirect('teachers_overview')
    
    try:
        profile = user.teacher_profile
    except TeacherProfile.DoesNotExist:
        profile = None
        messages.warning(request, 'У учителя нет профиля')
    
    # Предметы учителя
    teacher_subjects = TeacherSubject.objects.filter(
        teacher__user=user
    ).select_related('subject')
    
    # Группы, в которых преподает учитель
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user
    ).distinct().order_by('year', 'name')
    
    # Детальное расписание учителя
    schedule_by_day = {}
    schedule_lessons = ScheduleLesson.objects.filter(
        teacher=user
    ).select_related(
        'daily_schedule', 'subject', 'daily_schedule__student_group'
    ).order_by('daily_schedule__week_day', 'lesson_number')
    
    for lesson in schedule_lessons:
        day = lesson.daily_schedule.get_week_day_display()
        day_code = lesson.daily_schedule.week_day
        
        if day_code not in schedule_by_day:
            schedule_by_day[day_code] = {
                'day_name': day,
                'lessons': []
            }
        schedule_by_day[day_code]['lessons'].append(lesson)
    
    # Статистика оценок
    grades_stats = Grade.objects.filter(
        teacher=user
    )
    
    total_grades = grades_stats.count()
    avg_grade_result = grades_stats.aggregate(avg=Avg('value'))
    avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
    
    # Статистика по предметам
    grades_by_subject = []
    for ts in teacher_subjects:
        subject_grades = Grade.objects.filter(
            teacher=user,
            subject=ts.subject
        )
        
        subject_stats = subject_grades.aggregate(
            total=Count('id'),
            avg=Avg('value'),
            first_date=Min('date'),
            last_date=Max('date')
        )
        
        # Распределение оценок по предмету
        grade_distribution = {}
        for value in [5, 4, 3, 2]:
            count = subject_grades.filter(value=value).count()
            if count > 0:
                percentage = round((count / subject_stats['total'] * 100), 1) if subject_stats['total'] > 0 else 0
                grade_distribution[value] = {
                    'count': count,
                    'percentage': percentage
                }
        
        grades_by_subject.append({
            'subject': ts.subject,
            'total': subject_stats['total'] or 0,
            'avg': round(subject_stats['avg'], 1) if subject_stats['avg'] else 0,
            'first_date': subject_stats['first_date'],
            'last_date': subject_stats['last_date'],
            'grade_distribution': grade_distribution,
        })
    
    # Статистика по типам оценок
    grades_by_type = []
    for grade_type_code, grade_type_name in Grade.GradeType.choices:
        type_grades = grades_stats.filter(grade_type=grade_type_code)
        count = type_grades.count()
        if count > 0:
            avg_result = type_grades.aggregate(avg=Avg('value'))
            avg = round(avg_result['avg'], 1) if avg_result['avg'] else 0
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            
            grades_by_type.append({
                'type': grade_type_code,
                'name': grade_type_name,
                'count': count,
                'avg': avg,
                'percentage': percentage,
            })
    
    # Последние выставленные оценки
    recent_grades = grades_stats.select_related(
        'student', 'subject'
    ).order_by('-date')[:10]
    
    # Ученики, у которых учитель преподает
    students_taught = User.objects.filter(
        grades__teacher=user
    ).distinct().count()
    
    context = {
        'teacher_user': user,
        'profile': profile,
        'teacher_subjects': teacher_subjects,
        'teaching_groups': teaching_groups,
        'schedule_by_day': schedule_by_day,
        'total_grades': total_grades,
        'avg_grade': avg_grade,
        'grades_by_subject': grades_by_subject,
        'grades_by_type': grades_by_type,
        'recent_grades': recent_grades,
        'students_taught': students_taught,
        'lesson_count': schedule_lessons.count(),
        'subject_count': teacher_subjects.count(),
        'group_count': teaching_groups.count(),
    }
    return render(request, 'admin/teacher_full_detail.html', context)


@custom_login_required
@admin_required
def teacher_subject_performance(request, teacher_id, subject_id):
    """Производительность учителя по конкретному предмету"""
    user = get_object_or_404(User, id=teacher_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Проверяем, что учитель преподает этот предмет
    if not TeacherSubject.objects.filter(
        teacher__user=user,
        subject=subject
    ).exists():
        messages.error(request, f'Учитель не преподает предмет "{subject.name}"')
        return redirect('teacher_full_detail', teacher_id=teacher_id)
    
    # Группы, в которых учитель ведет этот предмет
    teaching_groups = StudentGroup.objects.filter(
        daily_schedules__lessons__teacher=user,
        daily_schedules__lessons__subject=subject
    ).distinct().order_by('year', 'name')
    
    # Оценки учителя по этому предмету
    grades = Grade.objects.filter(
        teacher=user,
        subject=subject
    ).select_related('student', 'schedule_lesson__daily_schedule__student_group')
    
    total_grades = grades.count()
    avg_grade_result = grades.aggregate(avg=Avg('value'))
    avg_grade = round(avg_grade_result['avg'], 1) if avg_grade_result['avg'] else 0
    
    # Статистика по месяцам
    import calendar
    from django.db.models.functions import TruncMonth
    
    monthly_stats = []
    monthly_data = grades.annotate(
        month=TruncMonth('date')
    ).values('month').annotate(
        count=Count('id'),
        avg=Avg('value')
    ).order_by('-month')[:12]  # Последние 12 месяцев
    
    for stat in monthly_data:
        monthly_stats.append({
            'month': stat['month'].strftime('%Y-%m'),
            'month_name': calendar.month_name[stat['month'].month],
            'year': stat['month'].year,
            'count': stat['count'],
            'avg': round(stat['avg'], 1) if stat['avg'] else 0,
        })
    
    # Статистика по группам
    group_stats = []
    for group in teaching_groups:
        group_grades = grades.filter(
            schedule_lesson__daily_schedule__student_group=group
        )
        group_total = group_grades.count()
        
        if group_total > 0:
            group_avg_result = group_grades.aggregate(avg=Avg('value'))
            group_avg = round(group_avg_result['avg'], 1) if group_avg_result['avg'] else 0
            
            group_stats.append({
                'group': group,
                'total': group_total,
                'avg': group_avg,
            })
    
    # Распределение оценок
    grade_distribution = {}
    for value in [5, 4, 3, 2]:
        count = grades.filter(value=value).count()
        if count > 0:
            percentage = round((count / total_grades * 100), 1) if total_grades > 0 else 0
            grade_distribution[value] = {
                'count': count,
                'percentage': percentage
            }
    
    # Последние оценки
    recent_grades = grades.order_by('-date')[:20]
    
    context = {
        'teacher_user': user,
        'subject': subject,
        'teaching_groups': teaching_groups,
        'total_grades': total_grades,
        'avg_grade': avg_grade,
        'monthly_stats': monthly_stats,
        'group_stats': group_stats,
        'grade_distribution': grade_distribution,
        'recent_grades': recent_grades,
    }
    return render(request, 'admin/teacher_subject_performance.html', context)