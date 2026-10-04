from django import forms

from .models import AssinaturaSistema


class ProjetoCobrancaForm(forms.ModelForm):
    forma_pagamento = forms.ChoiceField(label="Forma de pagamento", choices=[("PIX", "Pix")])

    class Meta:
        model = AssinaturaSistema
        fields = ("nome_projeto", "valor", "vencimento_atual", "status_projeto")
        labels = {"nome_projeto": "Nome do projeto", "valor": "Valor (R$)", "vencimento_atual": "Data de vencimento", "status_projeto": "Status"}
        widgets = {"vencimento_atual": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"
        self.fields["vencimento_atual"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and (self.instance.asaas_payment_id or self.instance.emissao_pendente):
            if any(field in self.changed_data for field in ("valor", "vencimento_atual")):
                raise forms.ValidationError("Há uma cobrança emitida ou aguardando reconciliação. Resolva-a no Asaas antes de alterar valor ou vencimento.")
        return cleaned
