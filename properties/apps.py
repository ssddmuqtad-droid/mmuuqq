from django.apps import AppConfig


class PropertiesConfig(AppConfig):
    name = 'properties'

    def ready(self):
        """تفعيل الإشارات عند بدء التطبيق"""
        import properties.signals
