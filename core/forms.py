from django import forms


class ContatoForms(forms.Form):
    nome = forms.CharField(max_length=50, required=True)
    telefone = forms.CharField(max_length=14, required=True)
    email = forms.CharField(max_length=30, required=True)
    assunto = forms.CharField(max_length=400, widget=forms.Textarea)

