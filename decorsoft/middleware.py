class SessionTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Setează doar dacă sesiunea nu are deja o preferință setată
        if 'session_persistent' not in request.session:
            request.session.set_expiry(0)  # Default: expiră la închidere
        
        response = self.get_response(request)
        return response