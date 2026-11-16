from django.urls import path
from . import views
from accounts.views import change_password_view

app_name = 'coach'

urlpatterns = [
    path('',                                views.dashboard,      name='dashboard'),
    path('trainees/',                       views.trainee_list,   name='trainee_list'),
    path('trainees/add/',                   views.trainee_add,    name='trainee_add'),
    path('trainees/<int:pk>/edit/',         views.trainee_edit,   name='trainee_edit'),
    path('trainees/<int:pk>/detail/',       views.trainee_detail, name='trainee_detail'),
    path('trainees/<int:pk>/toggle/',       views.trainee_toggle, name='trainee_toggle'),
    path('trainees/<int:pk>/delete/',       views.trainee_delete, name='trainee_delete'),
    path('exercises/',                      views.exercise_list,  name='exercise_list'),
    path('exercises/add/',                  views.exercise_add,   name='exercise_add'),
    path('exercises/<int:pk>/edit/',        views.exercise_edit,  name='exercise_edit'),
    path('exercises/<int:pk>/delete/',      views.exercise_delete,name='exercise_delete'),
    path('programs/<int:trainee_pk>/create/', views.program_create, name='program_create'),
    path('programs/<int:pk>/view/',         views.program_view,   name='program_view'),
    path('programs/<int:pk>/edit/',         views.program_edit,   name='program_edit'),
    path('programs/<int:pk>/copy/',         views.program_copy,   name='program_copy'),
    path('nutrition/<int:trainee_pk>/create/', views.nutrition_create, name='nutrition_create'),
    path('nutrition/<int:pk>/view/',        views.nutrition_view, name='nutrition_view'),
    path('nutrition/<int:pk>/edit/',        views.nutrition_edit, name='nutrition_edit'),
    path('nutrition/<int:pk>/copy/',        views.nutrition_copy, name='nutrition_copy'),
    path('notifications/',                  views.notifications,  name='notifications'),
    path('change-password/',                change_password_view, name='change_password'),
]
