from django.apps import AppConfig


class BoardsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'boards'

    def ready(self):
        # Import signals để chúng được đăng ký khi Django khởi động
        import boards.signals
