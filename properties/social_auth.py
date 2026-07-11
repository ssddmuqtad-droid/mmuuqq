"""
Custom pipeline functions for social authentication.
"""
import requests
import logging
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib import messages
from io import BytesIO
from PIL import Image
import os

User = get_user_model()
logger = logging.getLogger(__name__)


def save_profile_picture(strategy, details, response, user, *args, **kwargs):
    """
    Save profile picture from social media to user profile.
    """
    if not user:
        return

    # Get profile picture URL from response
    picture_url = None
    if 'picture' in response:
        picture_url = response.get('picture')
    elif 'picture' in response.get('data', {}):
        picture_url = response['data']['picture'].get('data', {}).get('url')
    elif 'graphObject' in response:
        # Facebook specific
        try:
            picture_url = response['graphObject'].get('picture', {}).get('data', {}).get('url')
        except (KeyError, AttributeError):
            pass

    if not picture_url:
        return

    try:
        # Download the image
        img_response = requests.get(picture_url, timeout=10)
        if img_response.status_code != 200:
            logger.warning(f"Failed to download profile picture: HTTP {img_response.status_code}")
            return

        # Open and process the image
        img = Image.open(BytesIO(img_response.content))
        
        # Convert to RGB if necessary
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Resize to reasonable size (max 300x300)
        img.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        # Save to BytesIO
        img_io = BytesIO()
        img.save(img_io, 'JPEG', quality=85)
        img_io.seek(0)
        
        # Create SimpleUploadedFile
        image_file = SimpleUploadedFile(
            f"{user.username}_profile.jpg",
            img_io.read(),
            content_type='image/jpeg'
        )
        
        # Get or create user profile
        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Save the image
        profile.profile_picture = image_file
        profile.save()
        
        logger.info(f"Profile picture saved for user {user.username}")
        
    except Exception as e:
        # Log error but don't break authentication
        logger.error(f"Error saving profile picture for user {user.username}: {e}")


def save_social_data(strategy, details, response, user, *args, **kwargs):
    """
    Save social media data to user profile.
    """
    if not user:
        return

    try:
        from .models import UserProfile
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Save full name if not set
        if details.get('fullname') and not profile.full_name:
            profile.full_name = details['fullname']
        
        # Save first and last name
        if details.get('first_name'):
            user.first_name = details['first_name']
        if details.get('last_name'):
            user.last_name = details['last_name']
        
        # Save email if not set
        if details.get('email') and not user.email:
            user.email = details['email']
        
        user.save()
        profile.save()
        
        logger.info(f"Social data saved for user {user.username}")
        
    except Exception as e:
        logger.error(f"Error saving social data for user {user.username}: {e}")


def get_user_avatar(backend, strategy, details, response, user=None, *args, **kwargs):
    """
    Get user avatar from social media and save it.
    """
    if user:
        save_profile_picture(strategy, details, response, user, *args, **kwargs)


def social_auth_error(strategy, details, response, user, *args, **kwargs):
    """
    Handle social authentication errors.
    """
    error = kwargs.get('error')
    if error:
        logger.error(f"Social authentication error: {error}")
        strategy.session_set('social_auth_error', str(error))
    return None
