from django.contrib.auth import authenticate, login, logout, get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
import requests
from boards.models import Workspace
from django.core.files.base import ContentFile
import traceback

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    GoogleLoginSerializer
)

User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True) # Tự động trả về lỗi 400 nếu dữ liệu không hợp lệ
        user = serializer.save() 

        tokens = get_tokens_for_user(user)
        return Response({
            "ok": True,
            "user": UserSerializer(user).data, # Dùng UserSerializer để hiển thị thông tin
            "token": tokens["access"],
            "refresh": tokens["refresh"]
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user'] # Lấy user đã được xác thực từ serializer

        login(request, user) # Cần cho Django Admin và các tính năng session-based khác
        tokens = get_tokens_for_user(user)

        # Logic kiểm tra workspace cho user cũ có thể vẫn giữ lại nếu cần
        if not Workspace.objects.filter(owner=user).exists():
            Workspace.objects.create(name="Hard Spirit", owner=user)

        return Response({
            "ok": True,
            "user": UserSerializer(user).data, 
            "token": tokens["access"],
            "refresh": tokens["refresh"]
        })

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication] # Thêm dòng này để chắc chắn nó xác thực bằng JWT

    def post(self, request):
        logout(request)
        return Response({"ok": True, "message": "Logged out successfully."})

class MeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # Chỉ cần truyền user và context có request vào UserSerializer
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # 1. Validate đầu vào
        input_serializer = GoogleLoginSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        token = input_serializer.validated_data['token']

        try:
            # 1. Xác minh với Google
            verify_url = f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={token}"
            google_res = requests.get(verify_url)

            if google_res.status_code != 200:
                print('[GoogleLogin] Invalid Google response:', google_res.text)
                return Response({'error': 'Invalid token'}, status=400)

            data = google_res.json()
            email = data.get('email')
            name = data.get('name')

            if not email:
                return Response({'error': 'No email in token'}, status=400)

            # 2. Lấy hoặc tạo user
            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            
            # Vì là OneToOneField với related_name='profile', bạn có thể truy cập trực tiếp
            # Lấy profile đã được signal tạo ra
            profile = user.profile

            login(request, user)
            tokens = get_tokens_for_user(user)

            # 3. Xử lý avatar
            picture = data.get('picture')
            if picture:
                try:
                    resp_img = requests.get(picture, timeout=5)
                    resp_img.raise_for_status()
                    # Tên file: user_<id>.jpg
                    fname = f'user_{user.id}.jpg'
                    profile.avatar.save(fname, ContentFile(resp_img.content), save=True)
                except Exception as e:
                    print("Failed to fetch Google avatar:", e)

            
            user_data = UserSerializer(user, context={'request': request}).data

            
            return Response({
                'ok': True,
                'user': user_data,
                'name': name,
                'token': tokens['access'],
                'refresh': tokens['refresh'],
            })

        except requests.exceptions.HTTPError:
            return Response({'error': 'Invalid Google token'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            print('[GoogleLogin] Exception:', str(e))
            traceback.print_exc()
            return Response({'error': 'Internal server error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)