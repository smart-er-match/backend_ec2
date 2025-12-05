from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch, MagicMock
from django.contrib.auth import get_user_model

User = get_user_model()

class KakaoLoginTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.url = reverse('kakao_login')

    @patch('accounts.views.requests.post')
    @patch('accounts.views.requests.get')
    def test_kakao_login_success(self, mock_get, mock_post):
        # Mock Token Response
        mock_token_response = MagicMock()
        mock_token_response.status_code = 200
        mock_token_response.json.return_value = {
            "access_token": "dummy_access_token",
            "refresh_token": "dummy_refresh_token"
        }
        mock_post.return_value = mock_token_response

        # Mock User Info Response
        mock_user_info_response = MagicMock()
        mock_user_info_response.status_code = 200
        mock_user_info_response.json.return_value = {
            "id": 123456789,
            "kakao_account": {
                "email": "kakao_test@example.com",
                "profile": {
                    "nickname": "Kakao User"
                }
            }
        }
        mock_get.return_value = mock_user_info_response

        # Request
        data = {"code": "dummy_auth_code"}
        response = self.client.post(self.url, data, format='json')

        # Assertions
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        
        # Check User Creation
        user = User.objects.get(email="kakao_test@example.com")
        self.assertEqual(user.username, "123456789")  # username = kakao_id
        self.assertEqual(user.kakao_id, "123456789")
        self.assertEqual(user.sign_kind, User.SignKind.KAKAO)
