from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, AuthenticationFailed

class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom authentication class that also looks for the access token in a cookie.
    """
    def authenticate(self, request):
        header = self.get_header(request)
        
        if header is None:
            # Check for token in cookie
            raw_token = request.COOKIES.get('access')
            if raw_token is None:
                return None
        else:
            raw_token = self.get_raw_token(header)
            
        if raw_token is None:
            return None

        validated_token = self.get_validated_token(raw_token)
        return self.get_user(validated_token), validated_token
