from django.contrib.auth import authenticate, login, logout, get_user_model
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.tokens import RefreshToken
import requests
from boards.models import Workspace
from .models import Profile
from django.core.files.base import ContentFile

User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, req):
        email = req.data.get("email") or req.data.get("username")
        password = req.data.get("password")
        if not email or not password:
            return Response({"error": "Missing credentials"}, status=400)

        if User.objects.filter(email=email).exists():
            return Response({"error": "Email already registered"}, status=400)

        user = User.objects.create_user(username=email, email=email, password=password)
        
            
        tokens = get_tokens_for_user(user)
        return Response({
            "ok": True,
            "email": user.email,
            "token": tokens["access"],
            "refresh": tokens["refresh"]
        }, status=201)

class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, req):
        identifier = req.data.get("email") or req.data.get("username")
        password = req.data.get("password")

        if not identifier or not password:
            return Response({"error": "Missing credentials"}, status=400)

        try:
            user_obj = User.objects.get(email=identifier)
            username = user_obj.username
        except User.DoesNotExist:
            username = identifier

        user = authenticate(req, username=username, password=password)
        if not user:
            return Response({"error": "Bad credentials"}, status=401)

        login(req, user)
        tokens = get_tokens_for_user(user)

        return Response({
            "ok": True,
            "email": user.email,
            "token": tokens["access"],
            "refresh": tokens["refresh"]
        })

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    def post(self, req):
        logout(req)
        return Response({"ok": True})

class MeView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        profile = getattr(user, 'profile', None)
        avatar_url = None
        if profile and profile.avatar:
            avatar_url = request.build_absolute_uri(profile.avatar.url)
        return Response({
            "email": user.email or user.username,
            "username": user.username,
            "role": "admin" if user.is_superuser else "user",
            "avatar": avatar_url,
        })

class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get('token')
        if not token:
            return Response({'error': 'No token'}, status=400)

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
            picture = data.get('picture')

            print('[GoogleLogin] Google email:', email)

            if not email:
                return Response({'error': 'No email in token'}, status=400)

            # 2. Lấy hoặc tạo user
            user, created = User.objects.get_or_create(username=email, defaults={'email': email})
            
             # Vì là OneToOneField với related_name='profile', bạn có thể truy cập trực tiếp
            profile = user.profile
            
            # 3. Đăng nhập user (Django session login)
            login(request, user)

            # 4. Tạo JWT token
            tokens = get_tokens_for_user(user)

            # ✅ Tạo workspace mặc định nếu chưa có
            if not Workspace.objects.filter(owner=user).exists():
                Workspace.objects.create(name='Hard Spirit', owner=user)
            profile, _ = Profile.objects.get_or_create(user=user)

            if picture:
                try:
                    resp_img = requests.get(picture, timeout=5)
                    resp_img.raise_for_status()
                    # Tên file: user_<id>.jpg
                    fname = f'user_{user.id}.jpg'
                    profile.avatar.save(fname, ContentFile(resp_img.content), save=True)
                except Exception as e:
                    print("Failed to fetch Google avatar:", e)

                # 5. Chuẩn bị URL avatar để trả về
            if profile.avatar:
                avatar = request.build_absolute_uri(profile.avatar.url)
            else:
                avatar = picture

            # 5. Trả response về frontend
            return Response({
                'token': tokens['access'],
                'refresh': tokens['refresh'],
                'email': user.email,
                'name': name,
                'avatar': avatar,
            })

        except Exception as e:
            import traceback
            print('[GoogleLogin] Exception:', str(e))
            traceback.print_exc()  # ✅ in rõ stacktrace lỗi
            return Response({'error': 'Internal server error'}, status=500)