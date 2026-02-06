from django.contrib import admin
from django.contrib.auth.models import User
from api.models import *

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    pass


@admin.register(StudentGroup)
class StudentGroupAdmin(admin.ModelAdmin):
    pass


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    pass


@admin.register(TeacherProfile)
class TeacherProfileAdmin(admin.ModelAdmin):
    pass


@admin.register(TeacherSubject)
class TeacherSubjectAdmin(admin.ModelAdmin):
    pass


@admin.register(DailySchedule)
class DailyScheduleAdmin(admin.ModelAdmin):
    pass


@admin.register(ScheduleLesson)
class ScheduleLessonAdmin(admin.ModelAdmin):
    pass


@admin.register(Homework)
class HomeworkAdmin(admin.ModelAdmin):
    pass


@admin.register(HomeworkSubmission)
class HomeworkSubmissionAdmin(admin.ModelAdmin):
    pass


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    pass


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    pass


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    pass


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    pass