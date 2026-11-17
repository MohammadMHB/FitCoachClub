from django.urls import path
from . import views, otp_views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('otp/request/', otp_views.request_code, name='otp_request'),
    path('otp/verify/', otp_views.verify_code, name='otp_verify'),
    path('logout/', views.logout_view, name='logout'),
    path('change-password/', views.change_password_view, name='change_password'),
]
