from django.contrib import admin
from .models import User, TraineeProfile, BodyMetricHistory
admin.site.register(User)
admin.site.register(TraineeProfile)
admin.site.register(BodyMetricHistory)
