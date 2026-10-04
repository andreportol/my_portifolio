from django import forms

from .models import AssinaturaSistema


class ProjetoCobrancaForm(forms.ModelForm):
    forma_pagamento = forms.ChoiceField(label="Forma de pagamento", choices=[("PIX", "Pix")])

    atualizar_cobranca_asaas = forms.BooleanField(
        required=False, label="Atualizar também o valor e o vencimento da cobrança pendente no Asaas")

    class Meta:
        model = AssinaturaSistema
        fields = ("nome_projeto", "valor", "vencimento_atual", "status_projeto")
        labels = {"nome_projeto": "Nome do projeto", "valor": "Valor (R$)", "vencimento_atual": "Data de vencimento", "status_projeto": "Status"}
        widgets = {"vencimento_atual": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
        self.fields["vencimento_atual"].input_formats = ["%Y-%m-%d", "%d/%m/%Y"]

    def clean(self):
        cleaned = super().clean()
        if self.instance.pk and (self.instance.asaas_payment_id or self.instance.emissao_pendente):
            if any(field in self.changed_data for field in ("valor", "vencimento_atual")):
                if self.instance.emissao_pendente or not self.instance.asaas_payment_id:
                    raise forms.ValidationError("A emissão aguarda reconciliação no Asaas. Confira a cobrança antes de corrigir os dados.")
                if not cleaned.get('atualizar_cobranca_asaas'):
                    raise forms.ValidationError("Há uma cobrança emitida. Marque a opção de atualizar também no Asaas para corrigir valor ou vencimento. Resolva-a no Asaas se já estiver paga ou cancelada.")
        return cleaned
