from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from accounts.models import Student, Teacher, Parent, Reception

class Command(BaseCommand):
    help = 'Удаляет всех пользователей, кроме администратора (superuser), и связанные объекты.'

    def handle(self, *args, **options):
        User = get_user_model()
        admins = User.objects.filter(is_superuser=True)
        if not admins.exists():
            self.stdout.write(self.style.ERROR('Нет ни одного администратора!'))
            return
        admin_ids = admins.values_list('id', flat=True)
        # Удаляем всех, кроме админов
        deleted_users = User.objects.exclude(id__in=admin_ids)
        count = deleted_users.count()
        deleted_users.delete()
        # Очищаем связанные объекты (если остались)
        Student.objects.exclude(user__in=admins).delete()
        Teacher.objects.exclude(user__in=admins).delete()
        Parent.objects.exclude(user__in=admins).delete()
        Reception.objects.exclude(user__in=admins).delete()
        self.stdout.write(self.style.SUCCESS(f'Удалено пользователей: {count}. Администратор(ы) сохранены.'))
