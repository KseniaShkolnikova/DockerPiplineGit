from django.shortcuts import redirect
from functools import wraps
from django.contrib import messages


def custom_login_required(view_func):
    """Просто проверяет, авторизован ли пользователь"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if request.user.is_authenticated:
            return view_func(request, *args, **kwargs)
        return redirect('/')  # На страницу логина
    return _wrapped_view


def admin_required(view_func):
    """Проверяет, что пользователь - администратор"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/')
        
        # Админ = суперпользователь ИЛИ пользователь в группе 'admin'
        is_admin = request.user.is_superuser or request.user.groups.filter(name='admin').exists()
        
        if not is_admin:
            messages.error(request, 'Доступ только для администраторов')
            return redirect('dashboard_page')  # На главную пользователя
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def student_required(view_func):
    """Проверяет, что пользователь - студент"""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('/')
        
        # Студент = пользователь в группе 'student'
        is_student = request.user.groups.filter(name='student').exists()
        
        if not is_student:
            messages.error(request, 'Доступ только для учеников')
            
            # Если не студент, отправляем в нужное место
            if request.user.is_superuser or request.user.groups.filter(name='admin').exists():
                return redirect('admin_dashboard_page')  # Админа - в админку
            else:
                return redirect('dashboard_page')  # Остальных - на главную
        
        return view_func(request, *args, **kwargs)
    return _wrapped_view