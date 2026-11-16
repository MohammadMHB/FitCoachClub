from django.urls import path
from . import views
from accounts.views import change_password_view

app_name = 'admin_panel'

urlpatterns = [
    path('',                             views.dashboard,      name='dashboard'),
    path('coaches/',                     views.coach_list,     name='coach_list'),
    path('coaches/add/',                 views.coach_add,      name='coach_add'),
    path('coaches/<int:pk>/edit/',       views.coach_edit,     name='coach_edit'),
    path('coaches/<int:pk>/delete/',     views.coach_delete,   name='coach_delete'),
    path('coaches/<int:pk>/toggle/',     views.coach_toggle,   name='coach_toggle'),
    path('trainees/',                    views.trainee_list,   name='trainee_list'),
    path('trainees/<int:pk>/',           views.trainee_detail, name='trainee_detail'),
    path('trainees/<int:pk>/edit/',      views.trainee_edit,   name='trainee_edit'),
    path('trainees/<int:pk>/delete/',    views.trainee_delete, name='trainee_delete'),
    path('exercises/',                   views.exercise_list,  name='exercise_list'),
    path('exercises/add/',               views.exercise_add,   name='exercise_add'),
    path('exercises/<int:pk>/edit/',     views.exercise_edit,  name='exercise_edit'),
    path('exercises/<int:pk>/delete/',   views.exercise_delete,name='exercise_delete'),
    path('food/',                        views.food_list,      name='food_list'),
    path('food/add/',                    views.food_add,       name='food_add'),
    path('food/<int:pk>/edit/',          views.food_edit,      name='food_edit'),
    path('food/<int:pk>/delete/',        views.food_delete,    name='food_delete'),
    path('activity-log/',                views.activity_log,   name='activity_log'),
    path('change-password/',             change_password_view, name='change_password'),
]
