from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

User = get_user_model()

class AuthViewsTests(TestCase):
    def setUp(self):
        # Creăm un user existent pentru teste login
        self.user = User.objects.create_user(
            denumire='Firma Test',
            email='test@example.com',
            password='testpassword123'
        )

    # ------------------------------
    # Signup tests
    # ------------------------------
    def test_signup_view_get(self):
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'main/signup.html')
        self.assertIn('form', response.context)

    def test_signup_view_post_success(self):
        data = {
            'denumire': 'Firma Noua',
            'email': 'newuser@example.com',
            'parola': 'Newpassword123',
            'confirmare_parola': 'Newpassword123',
        }
        response = self.client.post(reverse('signup'), data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('login'))
        self.assertTrue(User.objects.filter(email='newuser@example.com').exists())

    def test_signup_view_post_invalid(self):
        data = {
            'denumire': '',
            'email': '',
            'parola': '',
            'confirmare_parola': '',
        }
        response = self.client.post(reverse('signup'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'main/signup.html')
        form = response.context['form']
        self.assertFalse(form.is_valid())
        self.assertIn('denumire', form.errors)
        self.assertIn('email', form.errors)
        self.assertIn('parola', form.errors)
        self.assertIn('confirmare_parola', form.errors)

    # ------------------------------
    # Login tests
    # ------------------------------
    def test_login_view_get(self):
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'main/login.html')
        self.assertIn('form', response.context)

    def test_login_view_post_success(self):
        data = {
            'email': 'test@example.com',
            'parola': 'testpassword123',
        }
        response = self.client.post(reverse('login'), data)
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard_firma'))

    def test_login_view_post_invalid(self):
        data = {
            'email': 'test@example.com',
            'parola': 'wrongpassword',
        }
        response = self.client.post(reverse('login'), data)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'main/login.html')
        self.assertIn('form', response.context)
        # În views, mesajul de eroare se adaugă cu messages.error
        messages_list = list(response.context['messages'])
        self.assertTrue(any("Email sau parola incorectă" in str(m) for m in messages_list))







