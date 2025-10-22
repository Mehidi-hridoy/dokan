from django.shortcuts import redirect
from django.contrib import messages

def update_user_profile(strategy, details, backend, user=None, *args, **kwargs):
    if user and backend.name == 'google-oauth2':
        # Update user profile with Google data if needed
        if details.get('first_name'):
            user.first_name = details.get('first_name', '')
        if details.get('last_name'):
            user.last_name = details.get('last_name', '')
        if details.get('email'):
            user.email = details.get('email', '')
        
        # Set user type to customer for Google OAuth users
        user.user_type = 'customer'
        user.save()
    
    return {'user': user}