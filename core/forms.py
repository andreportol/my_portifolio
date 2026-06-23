from django import forms


class ContatoForms(forms.Form):
    nome = forms.CharField(max_length=50, required=True)
    telefone = forms.CharField(max_length=15, required=True)
    email = forms.CharField(max_length=30, required=True)
    assunto = forms.CharField(max_length=400, widget=forms.Textarea)


class LoginForms(forms.Form):
    email = forms.EmailField(
        max_length=254,
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'seu@email.com',
            'autocomplete': 'email',
            'style': 'width:100%; display:block;',
        }),
    )
    senha = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Sua senha',
            'autocomplete': 'current-password',
            'style': 'width:100%; display:block;',
        }),
    )


class LicencaGestaoOficinaForm(forms.Form):
    machine_id = forms.CharField(
        label='ID da máquina',
        max_length=64,
        min_length=64,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Cole o hash SHA-256 da máquina',
            'autocomplete': 'off',
            'spellcheck': 'false',
        }),
    )
    customer = forms.CharField(
        label='Cliente',
        max_length=120,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Nome do cliente',
            'autocomplete': 'off',
            'spellcheck': 'false',
        }),
    )

