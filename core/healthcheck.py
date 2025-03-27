from django.http import HttpResponse

def healthcheck(request):
    """
    A simple view that returns a 200 OK response.
    This is used for Railway's healthcheck to verify the application is running.
    """
    return HttpResponse("OK", content_type="text/plain")
