from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import Order, UserProfile, Review
from django.core.exceptions import ValidationError

class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ['full_name', 'address', 'payment_method']
        labels = {
            'full_name': 'Полное имя',
            'address': 'Адрес',
            'payment_method': 'Способ оплаты',
        }
        widgets = {
            'full_name': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'payment_method': forms.Select(attrs={'class': 'form-control'}),
        }

class UserProfileForm(forms.ModelForm):
    email = forms.EmailField(required=False)

    class Meta:
        model = UserProfile
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'style': 'display: none;', 'id': 'avatar-input'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.user:
            self.fields['email'].initial = self.instance.user.email

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            profile.save()
        return profile

class SignUpForm(UserCreationForm):
    email = forms.EmailField(max_length=254, help_text='Обязательное поле. Введите действующий email адрес.')

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})
        self.fields['username'].widget.attrs.update({'placeholder': 'Имя пользователя'})
        self.fields['email'].widget.attrs.update({'placeholder': 'Email'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Пароль'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Подтверждение пароля'})

    def clean_password2(self):
        password1 = self.cleaned_data.get("password1")
        password2 = self.cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            raise ValidationError("Пароли не совпадают.")
        return password2

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1")
        if len(password1) < 8:
            raise ValidationError("Пароль должен содержать как минимум 8 символов.")
        if password1.isdigit():
            raise ValidationError("Пароль не может состоять только из цифр.")
        return password1

class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'text']
        widgets = {
            'rating': forms.Select(choices=[(i, i) for i in range(1, 6)]),
            'text': forms.Textarea(attrs={'rows': 4}),
        }

class UserNameForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['username']

class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Имя пользователя'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Пароль'}))
