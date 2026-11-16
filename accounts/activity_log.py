from .models import ActivityLog


def log_activity(actor, action, description):
    """
    یک رکورد گزارش فعالیت می‌سازه. actor می‌تونه None باشه (اقدام سیستمی)،
    ولی معمولاً همون request.user هست. خطاهای احتمالی رو می‌بلعه تا هیچ‌وقت
    ثبت لاگ باعث خراب شدن عملیات اصلی نشه.
    """
    try:
        ActivityLog.objects.create(
            actor=actor if (actor and actor.is_authenticated) else None,
            actor_name=(actor.get_full_name() or actor.username) if actor else 'سیستم',
            actor_role=getattr(actor, 'role', '') or '',
            action=action,
            description=description,
        )
    except Exception:
        pass
