from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt

from checkout.webhook_handler import StripeWH_Handler

import stripe


@csrf_exempt
@require_POST
def webhook(request):
    """Listen to webhooks from Stripe"""

    # Setup
    wh_secret = settings.STRIPE_WH_SECRET
    stripe.api_key = settings.STRIPE_SECRET_KEY

    # get webhook data and verify its signature
    payload = request.body
    sig_header = request.META['HTTP_STRIPE_SIGNATURE']
    event = None

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, wh_secret
        )
    except ValueError as e:

        # Invalid payload
        return HttpResponse(status=400)

    except stripe.error.SignatureVerificationError as e:

        # Invalid signature
        return HttpResponse(status=400)

    except Exception as e:

        return HttpResponse(content=e, status=400)

    # set up a webhook handler
    handler = StripeWH_Handler(request)

    # map webhook events to relevant handler functions
    event_map = {

        'payment_intent.succeeded': handler.handle_payment_intent_succeeded,
        'payment_intent.payment_failed':
            handler.handle_payment_intent_payment_failed,

    }

    # Get the webhook type from Stripe
    event_type = event['type']

    # If there's a handler for it, get it from the event map
    # Use the generic one by default
    event_handler = event_map.get(event_type, handler.handle_event)

    # Call the event handler with the event
    response = event_handler(event)
    return response
