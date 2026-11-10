from django.contrib.sessions.models import Session


def browser_session(request, create=False):
    # Accessing session data validates any incoming session key first.
    request.session.get("auction_lab")
    if request.session.session_key is None and create:
        request.session.create()
    return request.session.session_key


def lock_browser_session(request):
    key = browser_session(request, create=True)
    return Session.objects.select_for_update().get(pk=key)
