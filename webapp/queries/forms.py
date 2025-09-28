from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault('class', 'form-control')


class QueryForm(forms.Form):
    text = forms.CharField(
        label="What biomedical question would you like to explore?",
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "e.g. What are the recent clinical trials for BRCA1 related therapies?",
            "class": "form-control"
        })
    )
