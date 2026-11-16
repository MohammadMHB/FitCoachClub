from django.urls import path
from . import views
from accounts.views import change_password_view

app_name = 'trainee'

urlpatterns = [
    path('',                          views.dashboard,          name='dashboard'),
    path('program/',                  views.my_program,         name='my_program'),
    path('program/past/',             views.past_programs,      name='past_programs'),
    path('program/<int:pk>/',         views.program_detail,     name='program_detail'),
    path('program/download/',         views.download_pdf,       name='download_pdf'),
    path('program/<int:pk>/download/',views.download_pdf,       name='download_pdf_pk'),
    path('diet/',                     views.my_diet,            name='my_diet'),
    path('diet/past/',                views.past_diets,         name='past_diets'),
    path('diet/download/',            views.download_diet_pdf,  name='download_diet_pdf'),
    path('diet/<int:pk>/download/',   views.download_diet_pdf,  name='download_diet_pdf_pk'),
    path('diet/<int:pk>/',            views.diet_detail,        name='diet_detail'),
    path('profile/',                  views.profile_view,       name='profile'),
    path('profile/update-metrics/',   views.update_metrics,     name='update_metrics'),
    path('notifications/',            views.notifications_view, name='notifications'),
    path('change-password/',          change_password_view,     name='change_password'),
]
