from django.urls import path, include
from . import views
from .webhooks import webhook
from .views import voicebot_reply  # Import voicebot_reply from views or the correct module
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
urlpatterns = [
    path(
        '',
        views.Checkout.as_view(),
        name='checkout'),

    path(
        'checkout_success/<order_number>',
        views.CheckoutSuccess.as_view(),
        name='checkout_success'),

    path(
        'cache_checkout_data/',
        views.cache_checkout_data,
        name='cache_checkout_data'),

    path('wh/', webhook, name='webhook'),
    path('voicebot-reply/', voicebot_reply, name='voicebot_reply'),
    path('', include('home.urls')), 
]
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)