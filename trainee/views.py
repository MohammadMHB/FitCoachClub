from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.conf import settings
import json
import traceback
import logging

from accounts.models import TraineeProfile, BodyMetricHistory
from coach.models import WorkoutProgram, Notification, NutritionPlan


def trainee_required(view_func):
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != 'trainee':
            messages.error(request, 'دسترسی غیرمجاز.')
            return redirect('accounts:login')
        return view_func(request, *args, **kwargs)
    return wrapper


def nutrition_required(view_func):
    """قابلیت رژیم غذایی فعلاً موقتاً غیرفعال است؛ دسترسی مستقیم به صفحاتش هم بسته می‌شود."""
    def wrapper(request, *args, **kwargs):
        if not settings.NUTRITION_ENABLED:
            messages.error(request, 'این قابلیت در دسترس نیست.')
            return redirect('trainee:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def get_trainee_profile(request):
    return get_object_or_404(TraineeProfile, user=request.user)


def get_unread(request):
    return Notification.objects.filter(recipient=request.user, is_read=False).count()


@trainee_required
def dashboard(request):
    profile = get_trainee_profile(request)
    active_program = WorkoutProgram.objects.filter(
        trainee=profile, is_active=True
    ).prefetch_related('days__exercises__exercise').first()
    if active_program:
        active_program.maybe_notify_renewal()
    active_diet = NutritionPlan.objects.filter(
        trainee=profile, is_active=True
    ).prefetch_related('days__meals').first()
    if active_diet:
        active_diet.maybe_notify_renewal()
    unread = get_unread(request)
    return render(request, 'trainee/dashboard.html', {
        'profile': profile,
        'active_program': active_program,
        'active_diet': active_diet,
        'unread_notifications': unread,
        'unread_count': unread,
    })


@trainee_required
def my_program(request):
    profile = get_trainee_profile(request)
    active_program = WorkoutProgram.objects.filter(
        trainee=profile, is_active=True
    ).prefetch_related('days__exercises__exercise').first()
    if active_program:
        active_program.maybe_notify_renewal()
    return render(request, 'trainee/my_program.html', {
        'profile': profile,
        'program': active_program,
        'unread_count': get_unread(request),
    })


@trainee_required
def past_programs(request):
    profile = get_trainee_profile(request)
    programs = WorkoutProgram.objects.filter(
        trainee=profile, is_active=False
    ).prefetch_related('days').order_by('-created_at')
    return render(request, 'trainee/past_programs.html', {
        'profile': profile,
        'programs': programs,
        'unread_count': get_unread(request),
    })


@trainee_required
def program_detail(request, pk):
    profile = get_trainee_profile(request)
    program = get_object_or_404(WorkoutProgram, pk=pk, trainee=profile)
    return render(request, 'trainee/program_detail.html', {
        'profile': profile,
        'program': program,
        'unread_count': get_unread(request),
    })


@trainee_required
@nutrition_required
def my_diet(request):
    profile = get_trainee_profile(request)
    active_diet = NutritionPlan.objects.filter(
        trainee=profile, is_active=True
    ).prefetch_related('days__meals').first()
    if active_diet:
        active_diet.maybe_notify_renewal()
    return render(request, 'trainee/my_diet.html', {
        'profile': profile,
        'plan': active_diet,
        'unread_count': get_unread(request),
    })


@trainee_required
@nutrition_required
def past_diets(request):
    profile = get_trainee_profile(request)
    diets = NutritionPlan.objects.filter(
        trainee=profile, is_active=False
    ).prefetch_related('days').order_by('-created_at')
    return render(request, 'trainee/past_diets.html', {
        'profile': profile,
        'diets': diets,
        'unread_count': get_unread(request),
    })


@trainee_required
@nutrition_required
def diet_detail(request, pk):
    profile = get_trainee_profile(request)
    plan = get_object_or_404(
        NutritionPlan.objects.prefetch_related('days__meals'),
        pk=pk, trainee=profile,
    )
    return render(request, 'trainee/diet_detail.html', {
        'profile': profile,
        'plan': plan,
        'unread_count': get_unread(request),
    })


@trainee_required
def profile_view(request):
    profile = get_trainee_profile(request)
    return render(request, 'trainee/profile.html', {
        'profile': profile,
        'unread_count': get_unread(request),
    })


@trainee_required
def update_metrics(request):
    profile = get_trainee_profile(request)
    if request.method == 'POST':
        w = request.POST.get('weight')
        h = request.POST.get('height')
        a = request.POST.get('age')
        if w: profile.weight = float(w)
        if h: profile.height = float(h)
        if a: profile.age = int(a)
        profile.save()
        BodyMetricHistory.objects.create(
            trainee=profile,
            weight=profile.weight,
            height=profile.height,
            age=profile.age,
            bmi=profile.bmi,
        )
        messages.success(request, 'اطلاعات جسمانی به‌روزرسانی شد.')
        return redirect('trainee:profile')

    history = profile.metric_history.all()
    history_data = {
        'labels': [h.recorded_at.strftime('%m/%d') for h in history],
        'weight': [h.weight for h in history],
        'bmi':    [h.bmi    for h in history],
    }
    return render(request, 'trainee/update_metrics.html', {
        'profile': profile,
        'history_json': json.dumps(history_data, ensure_ascii=False),
        'unread_count': get_unread(request),
    })


@trainee_required
def download_pdf(request, pk=None):
    """
    PDF برنامه‌ی تمرینی را با reportlab می‌سازد و مستقیم دانلود می‌کند.
    این روش فقط با pip نصب می‌شود (بدون Chromium/pango/cairo)، پس روی هر
    سروری بدون هیچ نصب اضافه‌ای کار می‌کند.
    """
    profile = get_trainee_profile(request)
    if pk:
        program = get_object_or_404(
            WorkoutProgram.objects.prefetch_related('days__exercises__exercise'),
            pk=pk, trainee=profile,
        )
    else:
        program = WorkoutProgram.objects.filter(
            trainee=profile, is_active=True
        ).prefetch_related('days__exercises__exercise').first()

    if not program:
        messages.error(request, 'برنامه‌ای برای دانلود وجود ندارد.')
        return redirect('trainee:my_program')

    try:
        from trainee.pdf_utils import render_program_pdf
        pdf_bytes = render_program_pdf(program, profile)
    except Exception as e:
        logging.getLogger(__name__).error(f'PDF error: {traceback.format_exc()}')
        messages.error(request, f'خطا در تولید PDF: {str(e)}')
        return redirect('trainee:my_program')

    resp = HttpResponse(pdf_bytes, content_type='application/octet-stream')
    resp['Content-Disposition'] = f'attachment; filename="fitcoach_{profile.user.username}_{program.pk}.pdf"'
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@trainee_required
@nutrition_required
def download_diet_pdf(request, pk=None):
    """
    PDF رژیم غذایی را با reportlab می‌سازد و مستقیم دانلود می‌کند
    (همون روش PDF برنامه‌ی تمرینی، بدون نیاز به Chromium/pango/cairo).
    """
    profile = get_trainee_profile(request)
    if pk:
        plan = get_object_or_404(
            NutritionPlan.objects.prefetch_related('days__meals'),
            pk=pk, trainee=profile,
        )
    else:
        plan = NutritionPlan.objects.filter(
            trainee=profile, is_active=True
        ).prefetch_related('days__meals').first()

    if not plan:
        messages.error(request, 'رژیم غذایی‌ای برای دانلود وجود ندارد.')
        return redirect('trainee:my_diet')

    try:
        from trainee.pdf_utils import render_diet_pdf
        pdf_bytes = render_diet_pdf(plan, profile)
    except Exception as e:
        logging.getLogger(__name__).error(f'Diet PDF error: {traceback.format_exc()}')
        messages.error(request, f'خطا در تولید PDF: {str(e)}')
        return redirect('trainee:my_diet')

    resp = HttpResponse(pdf_bytes, content_type='application/octet-stream')
    resp['Content-Disposition'] = f'attachment; filename="fitcoach_diet_{profile.user.username}_{plan.pk}.pdf"'
    resp['X-Content-Type-Options'] = 'nosniff'
    return resp


@trainee_required
def notifications_view(request):
    profile = get_trainee_profile(request)
    notifs = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')
    notifs.filter(is_read=False).update(is_read=True)
    return render(request, 'trainee/notifications.html', {
        'notifications': notifs,
        'profile': profile,
        'unread_count': 0,
    })
