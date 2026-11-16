"""Create three demo accounts without printing their shared random password."""
import os
from io import StringIO

import django
from django.core.management import call_command


def main():
    password = os.environ.get('DEMO_LOGIN_PASSWORD', '')
    if len(password) < 16:
        raise RuntimeError('Set DEMO_LOGIN_PASSWORD to a random value of at least 16 characters.')
    django.setup()
    from accounts.models import User, TraineeProfile
    call_command('setup_fitcoach', stdout=StringIO())
    for user in User.objects.filter(username__in=['admin', 'coach1', 'trainee1']):
        user.set_password(password)
        user.last_password_plain = None
        user.phone = ''
        user.save()
    TraineeProfile.objects.filter(user__username='trainee1').update(last_password_plain=None)
    print('Demo ready: admin / coach1 / trainee1. Use DEMO_LOGIN_PASSWORD from Render Environment.')


if __name__ == '__main__':
    main()
