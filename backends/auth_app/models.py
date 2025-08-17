# auth_app/models.py
from django.db import models
from django.conf import settings
import uuid
from PIL import Image
import io
from django.core.files.base import ContentFile
import logging

logger = logging.getLogger(__name__)

def avatar_upload_to(instance, filename):
    # Sử dụng UUID để tránh conflict và cache-busting
    ext = filename.split('.')[-1].lower()
    new_filename = f'{uuid.uuid4()}.{ext}'
    return f'avatars/user_{instance.user.id}/{new_filename}'

def banner_upload_to(instance, filename):
    ext = filename.split('.')[-1].lower()
    new_filename = f'{uuid.uuid4()}.{ext}'
    return f'banners/user_{instance.user.id}/{new_filename}'

class Profile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile'
    )
    
    # Avatar fields
    avatar = models.ImageField(
        upload_to=avatar_upload_to,
        blank=True,
        null=True,
        help_text="User avatar image"
    )
    avatar_thumbnail = models.ImageField(
        upload_to=avatar_upload_to,
        blank=True,
        null=True,
        help_text="Smaller version for cards and lists (40x40)"
    )
    
    # Banner field (để sau này dùng)
    banner = models.ImageField(
        upload_to=banner_upload_to,
        blank=True,
        null=True,
        help_text="Profile banner image"
    )
    
    # Profile info (giữ nguyên từ code cũ)
    display_name = models.CharField(max_length=50, blank=True)
    bio = models.TextField(blank=True, default="")
    
    # Privacy settings (thêm mới)
    is_discoverable = models.BooleanField(default=True)
    show_boards_on_profile = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'user_profiles'
        
    def __str__(self):
        return f"Profile<{self.user.email}:{self.get_display_name()}>"
    
    def get_display_name(self):
        """Get the best available display name with proper text cleaning"""
        if self.display_name:
            # Strip whitespace and normalize multiple spaces
            cleaned = ' '.join(self.display_name.strip().split())
            if cleaned:
                return cleaned
        
        if hasattr(self.user, 'first_name') and self.user.first_name:
            cleaned = ' '.join(self.user.first_name.strip().split())
            if cleaned:
                return cleaned
                
        return self.user.email.split('@')[0].strip()
    
    def get_initials(self):
        """Get user initials with Unicode support and better handling"""
        name = self.get_display_name()
        
        # Remove extra whitespace and split properly
        parts = name.strip().split()
        
        if len(parts) >= 2:
            # First and last name initials
            first_char = parts[0][0] if parts[0] else ''
            last_char = parts[-1][0] if parts[-1] else ''
            return f"{first_char}{last_char}".upper()
        elif len(parts) == 1 and len(parts[0]) >= 2:
            # Single word, take first 2 characters
            return parts[0][:2].upper()
        elif len(parts) == 1 and len(parts[0]) == 1:
            # Single character, duplicate it
            return f"{parts[0]}{parts[0]}".upper()
        else:
            return "U"  # Ultimate fallback
    
    def save(self, *args, **kwargs):
        # Check if avatar has changed
        avatar_changed = False
        if self.pk:
            try:
                old_instance = Profile.objects.get(pk=self.pk)
                avatar_changed = old_instance.avatar != self.avatar
            except Profile.DoesNotExist:
                avatar_changed = True
        else:
            # New instance
            avatar_changed = bool(self.avatar)
        
        # Save first to ensure avatar file is properly stored
        super().save(*args, **kwargs)
        
        # Create thumbnail only if avatar changed
        if avatar_changed and self.avatar:
            self._create_thumbnail()
    
    def _create_thumbnail(self):
        """Create thumbnail version of avatar - called after main save"""
        try:
            # Use avatar.open() to handle cloud storage properly
            with self.avatar.open('rb') as avatar_file:
                image = Image.open(avatar_file)
                
                # Convert to RGB for JPEG output
                if image.mode in ('RGBA', 'LA', 'P'):
                    # For transparent images, use white background
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    if image.mode == 'P':
                        image = image.convert('RGBA')
                    if image.mode == 'RGBA':
                        rgb_image.paste(image, mask=image.split()[-1])
                    else:
                        rgb_image.paste(image)
                    image = rgb_image
                
                # Create square thumbnail (40x40 for cards)
                image = self._make_square_crop(image)
                thumbnail_size = (40, 40)
                image.thumbnail(thumbnail_size, Image.Resampling.LANCZOS)
                
                # Save as JPEG with proper filename
                thumb_io = io.BytesIO()
                image.save(thumb_io, format='JPEG', quality=85, optimize=True)
                thumb_io.seek(0)
                
                # Generate proper filename with .jpg extension
                thumb_filename = f"thumb_{uuid.uuid4()}.jpg"
                
                # Save thumbnail with save=False to avoid recursion
                self.avatar_thumbnail.save(
                    thumb_filename,
                    ContentFile(thumb_io.read()),
                    save=False
                )
                
                # Update only the thumbnail field to avoid triggering save() again
                Profile.objects.filter(pk=self.pk).update(
                    avatar_thumbnail=self.avatar_thumbnail.name
                )
                
        except Exception as e:
            logger.error(f"Thumbnail creation failed for user {self.user_id}: {e}")
            # In development, you might want to print for debugging
            print(f"Error creating thumbnail: {e}")
    
    def _make_square_crop(self, image):
        """Crop image to square from center"""
        width, height = image.size
        
        if width == height:
            return image
        
        # Crop to square from center
        size = min(width, height)
        left = (width - size) // 2
        top = (height - size) // 2
        right = left + size
        bottom = top + size
        
        return image.crop((left, top, right, bottom))