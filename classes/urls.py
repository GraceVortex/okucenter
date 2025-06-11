from django.urls import path
from . import views
from . import parent_views
from . import non_scheduled_lesson_views

app_name = 'classes'

urlpatterns = [
    # URL-маршруты для управления классами
    path('', views.class_list, name='class_list'),
    path('class/<int:class_id>/', views.class_detail, name='class_detail'),
    path('create/', views.create_class, name='create_class'),
    path('<int:class_id>/update/', views.update_class, name='update_class'),
    path('<int:class_id>/delete/', views.delete_class, name='delete_class'),
    path('<int:class_id>/add-schedule/', views.add_schedule, name='add_schedule'),
    path('schedule/<int:schedule_id>/update/', views.update_schedule, name='update_schedule'),
    path('schedule/<int:schedule_id>/delete/', views.delete_schedule, name='delete_schedule'),
    path('<int:class_id>/add-homework/', views.add_homework, name='add_homework'),
    path('homework/<int:homework_id>/update/', views.update_homework, name='update_homework'),
    path('homework/<int:homework_id>/delete/', views.delete_homework, name='delete_homework'),
    path('homework/<int:homework_id>/submit/', views.submit_homework, name='submit_homework'),
    path('homework/<int:homework_id>/submit-ajax/', views.submit_homework_ajax, name='submit_homework_ajax'),
    path('homework-submission/<int:submission_id>/grade/', views.grade_homework, name='grade_homework'),
    path('homework-submission/<int:submission_id>/grade-ajax/', views.grade_homework_submission, name='grade_homework_submission_ajax'),
    
    # URL-маршруты для работы с материалами занятий
    path('<int:class_id>/materials/', views.class_materials, name='class_materials'),
    path('<int:class_id>/upload-material/', views.upload_classwork_file, name='upload_classwork_file'),
    path('<int:class_id>/upload-material/schedule/<int:schedule_id>/date/<str:date>/', views.upload_classwork_file, name='upload_classwork_file_with_schedule'),
    path('<int:class_id>/lesson-calendar/', views.class_lesson_calendar, name='class_lesson_calendar'),
    path('material/<int:file_id>/delete/', views.delete_classwork_file, name='delete_classwork_file'),
    path('homework-submission/<int:submission_id>/cancel/', views.cancel_homework_submission, name='cancel_homework_submission'),
    path('<int:class_id>/student/<int:student_id>/homework/', views.student_homework, name='student_homework'),
    path('<int:class_id>/add-student/', views.add_student, name='add_student'),
    path('enrollment/<int:enrollment_id>/remove/', views.remove_student, name='remove_student'),
    path('teacher/', views.teacher_classes, name='teacher_classes'),
    path('teacher/today/', views.teacher_today_schedule, name='teacher_today_schedule'),
    path('teacher/schedule/', views.teacher_schedule, name='teacher_schedule'),
    path('teacher/schedule/week_offset=<int:week_offset>/', views.teacher_schedule, name='teacher_schedule_with_offset'),
    path('lesson/<int:class_id>/<int:schedule_id>/<str:date>/', views.lesson_detail, name='lesson_detail'),
    # Родительские представления
    path('parent/child/<int:student_id>/lessons/', parent_views.parent_child_lessons, name='parent_child_lessons'),
    path('parent/child/<int:student_id>/past-lessons/', parent_views.parent_child_past_lessons, name='parent_child_past_lessons'),
    path('parent/child/<int:student_id>/schedule/', parent_views.parent_child_schedule, name='parent_child_schedule'),
    path('parent/child/<int:student_id>/homework/', parent_views.parent_child_homework, name='parent_child_homework'),
    path('parent/child/<int:student_id>/lesson/<int:schedule_id>/', parent_views.parent_child_lesson_detail, name='parent_child_lesson_detail'),
    path('parent/child/<int:student_id>/class/<int:class_id>/', parent_views.parent_class_detail, name='parent_class_detail'),
    
    # Старые URL-маршруты для обратной совместимости
    path('parent-child-lessons/<int:student_id>/', parent_views.parent_child_lessons, name='parent_child_lessons_old'),
    path('parent-child-past-lessons/<int:student_id>/', parent_views.parent_child_past_lessons, name='parent_child_past_lessons_old'),
    path('parent-child-homework/<int:student_id>/', parent_views.parent_child_homework, name='parent_child_homework_old'),
    path('parent-child-schedule/<int:student_id>/', parent_views.parent_child_schedule, name='parent_child_schedule_old'),
    path('student/', views.student_classes, name='student_classes'),
    
    # URL-маршруты для студентов
    path('student/schedule/', views.student_schedule, name='student_schedule'),
    path('student/past-lessons/', views.student_past_lessons, name='student_past_lessons'),
    path('student/lesson/<int:class_id>/<int:schedule_id>/<str:date>/', views.student_lesson_detail, name='student_lesson_detail'),
    path('all-student-homework/', views.all_student_homework, name='all_student_homework'),
    path('unchecked-student-homework/', views.unchecked_student_homework, name='unchecked_student_homework'),
    path('unchecked-teacher-homework/', views.unchecked_teacher_homework, name='unchecked_teacher_homework'),
    path('class/<int:class_id>/unchecked-homework/', views.unchecked_class_homework, name='unchecked_class_homework'),
    
    # URL-маршруты для родителей
    path('parent/child/<int:student_id>/schedule/', parent_views.parent_child_schedule, name='parent_child_schedule'),
    
    # URL-маршруты для уроков не по расписанию
    path('non-scheduled-lessons/', non_scheduled_lesson_views.non_scheduled_lesson_list, name='non_scheduled_lesson_list'),
    path('non-scheduled-lessons/create/', non_scheduled_lesson_views.create_non_scheduled_lesson, name='create_non_scheduled_lesson'),
    path('non-scheduled-lessons/<int:lesson_id>/', non_scheduled_lesson_views.non_scheduled_lesson_detail, name='non_scheduled_lesson_detail'),
    path('non-scheduled-lessons/<int:lesson_id>/update-trial-status/', non_scheduled_lesson_views.update_trial_lesson_status, name='update_trial_lesson_status'),
    path('non-scheduled-lessons/<int:lesson_id>/mark-attendance/', non_scheduled_lesson_views.mark_attendance, name='mark_non_scheduled_attendance'),

]
