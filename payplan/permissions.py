from rest_framework import permissions

class IsRegisteredUser(permissions.BasePermission):
    """
    Allows access only to registered users who are verified.
    """
    def has_permission(self, request, view):
        return (
            request.user and 
            request.user.is_authenticated and 
            getattr(request.user, 'role', None) == 'REGISTERED' and 
            getattr(request.user, 'is_verified', False)
        )

class IsPlanCreator(permissions.BasePermission):
    """
    Allows access only to the creator of the plan.
    """
    def has_object_permission(self, request, view, obj):
        # This assumes the object has a 'creator' field
        return obj.creator == request.user
