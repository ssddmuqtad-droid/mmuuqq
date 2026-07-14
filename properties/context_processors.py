import json
import os

from .constants import GOVERNORATE_CITIES, IRAQ_GOVERNORATES
from .models import SiteSettings
from .permissions import can_access_dashboard, can_access_admin_panel, can_manage_brokers, get_broker


def oauth_context(request):
    """Context processor to check OAuth configuration status."""
    google_configured = bool(os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', '').strip() and 
                            os.getenv('SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET', '').strip())
    facebook_configured = bool(os.getenv('SOCIAL_AUTH_FACEBOOK_KEY', '').strip() and 
                               os.getenv('SOCIAL_AUTH_FACEBOOK_SECRET', '').strip())
    
    return {
        'google_oauth_configured': google_configured,
        'facebook_oauth_configured': facebook_configured,
    }


def site_context(request):
    try:
        settings = SiteSettings.get_solo()
    except Exception:
        settings = None
    ctx = {
        'site_settings': settings,
        'governorates': IRAQ_GOVERNORATES,
        'governorate_cities_json': json.dumps(GOVERNORATE_CITIES, ensure_ascii=False),
    }
    try:
        if request.user.is_authenticated:
            ctx['current_broker'] = get_broker(request.user)
            ctx['can_access_dashboard'] = can_access_dashboard(request.user)
            ctx['can_access_admin_panel'] = can_access_admin_panel(request.user)
            ctx['can_manage_brokers'] = can_manage_brokers(request.user)
        else:
            ctx['current_broker'] = None
            ctx['can_access_dashboard'] = False
            ctx['can_access_admin_panel'] = False
            ctx['can_manage_brokers'] = False
    except Exception:
        ctx['current_broker'] = None
        ctx['can_access_dashboard'] = False
        ctx['can_access_admin_panel'] = False
        ctx['can_manage_brokers'] = False
    return ctx
