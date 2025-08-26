# backends/boards/serializers.py
from rest_framework import serializers
from .models import Board, Workspace, List, Card, Label, BoardMembership,BoardInviteLink,Comment,CardActivity,CardMembership, Checklist, ChecklistItem, Attachment
from django.contrib.auth import get_user_model
import hashlib

User = get_user_model()

# ===================================================================
# Serializers chính cho các model
# ===================================================================

# Serializer nhỏ này chỉ để lồng thông tin workspace vào các serializer khác
class WorkspaceShortSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['id', 'name']


# Serializer đầy đủ cho Workspace (dùng cho API lấy list workspace)
class WorkspaceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Workspace
        fields = ['id', 'name']


class BoardSerializer(serializers.ModelSerializer):
    workspace = WorkspaceShortSerializer(read_only=True)
    # Cho phép FE gửi workspace_id nếu muốn, nhưng không bắt buộc
    workspace_id = serializers.PrimaryKeyRelatedField(
        source='workspace',
        queryset=Workspace.objects.all(),
        write_only=True,
        required=False
    )
    class Meta:
        model = Board
        # Vẫn trả về 'workspace' ID khi ghi (create/update)
        # Nhưng khi đọc (get), nó sẽ sử dụng serializer lồng ở trên
        fields = ['id', 'name', 'workspace', 'workspace_id', 'created_by', 'background', 'visibility', 'is_closed']
        read_only_fields = ['created_by', 'workspace']
    def create(self, validated_data):
        # ưu tiên workspace từ payload; nếu không có, lấy từ context (set ở view)
        workspace = validated_data.get('workspace') or self.context.get('workspace')
        if not workspace:
            raise serializers.ValidationError({'workspace_id': 'This field is required.'})
        user = self.context['request'].user
        return Board.objects.create(created_by=user, workspace=workspace, **validated_data)


class ListSerializer(serializers.ModelSerializer):
    class Meta:
        model = List
        fields = ['id', 'name', 'background', 'board', 'visibility', 'position']

class UserShortSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'name', 'avatar']

    def get_name(self, obj):
        full = getattr(obj, "get_full_name", lambda: "")() or ""
        return full.strip() or obj.username
    
    def get_avatar(self, obj):
        # Nếu có field avatar trên model:
        if hasattr(obj, "avatar") and obj.avatar:
            try:
                return obj.avatar.url  # ImageField/FileField
            except Exception:
                return str(obj.avatar)
        # Fallback Gravatar theo email (tuỳ chọn)
        if obj.email:
            h = hashlib.md5(obj.email.lower().encode()).hexdigest()
            return f"https://www.gravatar.com/avatar/{h}?d=identicon"
        return None
    
class CardSerializer(serializers.ModelSerializer):
    """Basic card serializer for list views and simple operations"""
    members = UserShortSerializer(many=True, read_only=True)

    class Meta:
        model = Card
        fields = [
            'id', 'name', 'status', 'background', 'visibility', 'list', 
            'description', 'due_date', 'completed', 'position', 
            'created_at','labels', 'members'
        ]
        read_only_fields = ['created_by']
        extra_kwargs = {
            'list': {'required': False, 'allow_null': True}
        }
    
    def create(self, validated_data):
        request = self.context.get('request')
        if request and hasattr(request, 'user'):
            validated_data['created_by'] = request.user
        return super().create(validated_data)
    
    
class LabelSerializer(serializers.ModelSerializer):
    class Meta:
        model = Label
        fields = ['id', 'name', 'color']

# ===================================================================
# Serializers phụ
# ===================================================================
    
class BoardMembershipSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)

    class Meta:
        model = BoardMembership
        fields = ['id', 'user', 'role', 'joined_at']


class BoardInviteLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BoardInviteLink
        fields = ['token', 'role', 'created_at', 'expires_at', 'is_active']
        read_only_fields = ['token', 'created_at']



class UserPublicSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'username', 'name']  

    def get_name(self, obj):
        full = (getattr(obj, "get_full_name", lambda: "")() or "").strip()
        return full or obj.username

class CommentSerializer(serializers.ModelSerializer):
    author = UserShortSerializer(read_only=True)

    class Meta:
        model = Comment
        fields = ['id', 'card', 'author', 'content', 'created_at', 'updated_at']
        read_only_fields = ['author', 'created_at', 'updated_at']

class CardMembershipSerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    assigned_by = UserShortSerializer(read_only=True)
    
    class Meta:
        model = CardMembership
        fields = ['id', 'user', 'assigned_by', 'assigned_at', 'role', 'is_active']

class CardActivitySerializer(serializers.ModelSerializer):
    user = UserShortSerializer(read_only=True)
    target_user = UserShortSerializer(read_only=True)
    
    class Meta:
        model = CardActivity
        fields = ['id', 'user', 'activity_type', 'description', 'target_user', 'created_at']

class EnhancedCardSerializer(serializers.ModelSerializer):
    """Enhanced card serializer with detailed member info, watchers, and activities"""
    members_roles = CardMembershipSerializer(
        source='cardmembership_set', 
        many=True, 
        read_only=True
    )
    watchers = UserShortSerializer(many=True, read_only=True)
    activities = CardActivitySerializer(many=True, read_only=True)
    labels = LabelSerializer(many=True, read_only=True)
    created_by = UserShortSerializer(read_only=True)
    
    class Meta:
        model = Card
        fields = [
            'id', 'name', 'status', 'background', 'visibility', 'list', 
            'description', 'due_date', 'completed', 'position', 
            'created_at', 'created_by', 'labels', 'members_roles', 
            'watchers', 'activities'
        ]


class ChecklistItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChecklistItem
        fields = [
            'id',
            'checklist',
            'text',
            'completed',
            'position',
            'due_date',
            'assigned_to',
            'created_at',
            'updated_at',
            'completed_at',
            'completed_by',
        ]
        read_only_fields = ['id','checklist', 'created_at', 'updated_at', 'completed_at', 'completed_by']


class ChecklistSerializer(serializers.ModelSerializer):
    items = ChecklistItemSerializer(many=True, read_only=True)
    completion_percentage = serializers.ReadOnlyField()

    class Meta:
        model = Checklist
        fields = [
            'id',
            'card',
            'title',
            'position',
            'created_at',
            'updated_at',
            'created_by',
            'items',
            'completion_percentage',
        ]
        read_only_fields = ['id','card','created_at','updated_at','created_by','completion_percentage']



class AttachmentSerializer(serializers.ModelSerializer):
    uploaded_by = UserShortSerializer(read_only=True)
    file_size_human = serializers.ReadOnlyField()
    is_image = serializers.ReadOnlyField()
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = Attachment
        fields = [
            'id', 'name', 'attachment_type', 'file', 'file_url', 'file_size',
            'file_size_human', 'mime_type', 'url', 'uploaded_by',
            'created_at', 'is_cover', 'is_image'
        ]
        read_only_fields = ['uploaded_by', 'created_at', 'file_size', 'mime_type']

    def get_file_url(self, obj):
        # Ưu tiên trả về URL truy cập trực tiếp:
        # - file upload: storage url
        # - link: chính là obj.url
        request = self.context.get('request')
        if obj.attachment_type == 'file' and obj.file:
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        if obj.attachment_type == 'link' and obj.url:
            return obj.url
        return None
    
    def validate(self, attrs):
        a_type = attrs.get('attachment_type') or getattr(self.instance, 'attachment_type', None)
        file_obj = attrs.get('file')
        link_url = attrs.get('url')

        if a_type == 'file':
            if not file_obj and not (self.instance and self.instance.file):
                raise serializers.ValidationError("File attachment requires a file.")
            if link_url:
                raise serializers.ValidationError("File attachment should not include a URL.")
        elif a_type == 'link':
            if not link_url and not (self.instance and self.instance.url):
                raise serializers.ValidationError("Link attachment requires a URL.")
            if file_obj:
                raise serializers.ValidationError("Link attachment should not include a file.")
        else:
            raise serializers.ValidationError("Invalid attachment_type. Use 'file' or 'link'.")

        return attrs
    
    def create(self, validated_data):
        # Auto-fill file_size & mime_type nếu là file
        file_obj = validated_data.get('file')
        if file_obj:
            validated_data['file_size'] = getattr(file_obj, 'size', None)
            validated_data['mime_type'] = getattr(file_obj, 'content_type', '') or ''
            # Đặt name mặc định nếu thiếu
            validated_data.setdefault('name', getattr(file_obj, 'name', 'Attachment'))
        else:
            # Link: đặt name mặc định nếu thiếu
            if not validated_data.get('name'):
                from urllib.parse import urlparse
                parsed = urlparse(validated_data.get('url', ''))
                # ví dụ: example.com/path → "example.com/path"
                default_name = (parsed.netloc + parsed.path).strip('/') or 'Link'
                validated_data['name'] = default_name

        return super().create(validated_data)