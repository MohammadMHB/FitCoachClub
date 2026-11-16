from django.contrib import admin
from .models import Exercise, WorkoutProgram, WorkoutDay, WorkoutExercise, Notification
admin.site.register(Exercise)
admin.site.register(WorkoutProgram)
admin.site.register(Notification)
