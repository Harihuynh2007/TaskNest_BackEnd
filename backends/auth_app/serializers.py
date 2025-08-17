# auth_app/serializers.py
from rest_framework import serializers
from django.contrib.auth import get_user_model, authenticate
from .models import Profile

User = get_user_model()

# Lightweight serializer cho avatar display trong cards/members
class UserAvatarSerializer(serializers.ModelSerializer):
    """Lightweight serializer cho avatar display trong cards/members"""
    id = serializers.IntegerField(source='user.id', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    display_name = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    avatar_thumbnail_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Profile
        fields = ['id', 'email', 'display_name', 'initials', 'avatar_url', 'avatar_thumbnail_url']
    
    def get_display_name(self, profile):
        return profile.get_display_name()
    
    def get_initials(self, profile):
        return profile.get_initials()
    
    def get_avatar_url(self, profile):
        request = self.context.get('request')
        if profile.avatar and request:
            return request.build_absolute_uri(profile.avatar.url)
        return None
    
    def get_avatar_thumbnail_url(self, profile):
        request = self.context.get('request')
        if profile.avatar_thumbnail and request:
            return request.build_absolute_uri(profile.avatar_thumbnail.url)
        return None

# Updated ProfileSerializer for settings page
class ProfileSerializer(serializers.ModelSerializer):
    """Full profile serializer cho settings page"""
    avatar_url = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField() 
    display_name_computed = serializers.SerializerMethodField()
    initials = serializers.SerializerMethodField()
    
    # Separate fields cho upload
    avatar = serializers.ImageField(write_only=True, required=False)
    banner = serializers.ImageField(write_only=True, required=False)
    
    def validate(self, data):
        """Custom validation to handle potential data type issues"""
        # Ensure boolean fields are properly typed
        if 'is_discoverable' in data:
            if isinstance(data['is_discoverable'], str):
                data['is_discoverable'] = data['is_discoverable'].lower() in ('true', '1', 'on')
        
        if 'show_boards_on_profile' in data:
            if isinstance(data['show_boards_on_profile'], str):
                data['show_boards_on_profile'] = data['show_boards_on_profile'].lower() in ('true', '1', 'on')
        
        return data
    
    class Meta:
        model = Profile
        fields = [
            'display_name', 'bio', 'is_discoverable', 'show_boards_on_profile',
            'avatar', 'banner', 'avatar_url', 'banner_url', 
            'display_name_computed', 'initials'
        ]
        
    def get_avatar_url(self, profile):
        request = self.context.get('request')
        if profile.avatar and request:
            return request.build_absolute_uri(profile.avatar.url)
        return None
        
    def get_banner_url(self, profile):
        request = self.context.get('request')
        if profile.banner and request:
            return request.build_absolute_uri(profile.banner.url)
        return None
    
    def get_display_name_computed(self, profile):
        return profile.get_display_name()
    
    def get_initials(self, profile):
        return profile.get_initials()

# Enhanced user serializer with profile info  
class UserSerializer(serializers.ModelSerializer):
    """
    Enhanced user serializer với profile info - cho MeView và general use
    """
    profile = ProfileSerializer(read_only=True) # <-- SỬA Ở ĐÂY

    role = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'email', 'profile', 'role')

    def get_role(self, user):
        """
        Xác định vai trò của người dùng.
        """
        return "admin" if user.is_superuser else "user"

# Giữ nguyên các serializers khác
class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer để xử lý việc đăng ký của người dùng mới.
    Validate dữ liệu và tạo user.
    """
    password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        error_messages={
            "min_length": "Mật khẩu phải có ít nhất 8 ký tự."
        }
    )

    class Meta:
        model = User
        fields = ('email', 'password')

    def validate_email(self, value):
        """
        Kiểm tra xem email đã tồn tại hay chưa.
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email này đã được đăng ký.")
        return value

    def create(self, validated_data):
        """
        Tạo user mới với mật khẩu đã được hash.
        """
        user = User.objects.create_user(
            username=validated_data['email'], # Dùng email làm username mặc định
            email=validated_data['email'],
            password=validated_data['password']
        )
        # Signal 'post_save' sẽ tự động tạo Profile cho user này.
        return user

class LoginSerializer(serializers.Serializer):
    """
    Serializer để xử lý việc đăng nhập.
    Không kế thừa từ ModelSerializer vì nó không tạo hay cập nhật model.
    """
    email = serializers.CharField(label="Email/Username", write_only=True)
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email_or_username = data.get('email')
        password = data.get('password')

        if not email_or_username or not password:
            raise serializers.ValidationError(
                "Phải cung cấp cả email/username và mật khẩu.",
                code='authorization'
            )

        # Thử tìm user bằng email trước
        try:
            user_obj = User.objects.get(email=email_or_username)
            username = user_obj.username
        except User.DoesNotExist:
            # Nếu không thấy, coi như người dùng đã nhập username
            username = email_or_username

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError(
                "Email hoặc mật khẩu không đúng.",
                code='authorization'
            )

        # Nếu xác thực thành công, trả về đối tượng user
        data['user'] = user
        return data

class GoogleLoginSerializer(serializers.Serializer):
    """
    Serializer để validate token từ Google.
    """
    token = serializers.CharField(write_only=True, required=True)