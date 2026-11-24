from django.apps import AppConfig
from django.db.models.signals import post_migrate


def _auto_seed_after_migrate(sender, **kwargs):
    from core.seed_on_deploy import ensure_seeded_on_deploy

    ensure_seeded_on_deploy()


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"

    def ready(self):
        post_migrate.connect(
            _auto_seed_after_migrate,
            sender=self,
            dispatch_uid="core_auto_seed_after_migrate",
        )
