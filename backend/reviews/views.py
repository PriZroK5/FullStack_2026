from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from .models import Review
from .serializers import RegisterSerializer, LoginSerializer, ReviewSerializer
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django.conf import settings
import json
import ssl
import smtplib


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response({
                'token': token.key,
                'name': user.first_name,
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            name = serializer.validated_data['name']
            password = serializer.validated_data['password']
            try:
                user_obj = User.objects.get(first_name=name)
                user = authenticate(username=user_obj.username, password=password)
                if user:
                    token, _ = Token.objects.get_or_create(user=user)
                    return Response({
                        'token': token.key,
                        'name': user.first_name,
                    })
                return Response({'error': 'Неверный пароль'}, status=status.HTTP_400_BAD_REQUEST)
            except User.DoesNotExist:
                return Response({'error': 'Пользователь не найден'}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ReviewListCreateView(generics.ListCreateAPIView):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer

    def get_permissions(self):
        if self.request.method == 'POST':
            return [IsAuthenticated()]
        return [AllowAny()]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class SendEmailView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        try:
            data = json.loads(request.body)
            name = data.get('name', '')
            contact = data.get('contact', '')
            text = data.get('text', '')

            if not contact or not text:
                return Response(
                    {'error': 'Заполните контакт и вопрос'},
                    status=400
                )

            subject = 'Новый вопрос с сайта ХАБ'
            html_message = f"""
            <h3>Новый вопрос с сайта</h3>
            <p><strong>Имя:</strong> {name or 'Не указано'}</p>
            <p><strong>Контакт:</strong> {contact}</p>
            <p><strong>Вопрос:</strong><br/>{text.replace('\n', '<br/>')}</p>
            """
            plain_message = f"Имя: {name or 'Не указано'}\nКонтакт: {contact}\nВопрос: {text}"

            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = settings.EMAIL_HOST_USER
            msg['To'] = settings.EMAIL_RECIPIENT
            msg.attach(MIMEText(plain_message, 'plain'))
            msg.attach(MIMEText(html_message, 'html'))

            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE

            with smtplib.SMTP_SSL(settings.EMAIL_HOST, settings.EMAIL_PORT, context=context) as server:
                server.login(settings.EMAIL_HOST_USER, settings.EMAIL_HOST_PASSWORD)
                server.sendmail(settings.EMAIL_HOST_USER, [settings.EMAIL_RECIPIENT], msg.as_string())

            return Response({'success': True})
        except Exception as e:
            print(f"Ошибка отправки: {e}")
            return Response({'error': str(e)}, status=500)