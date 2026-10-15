from django import forms


class ImportacaoFinanceiraCSVForm(forms.Form):
    origem = forms.CharField(label="Sistema ou planilha de origem", max_length=100)
    arquivo = forms.FileField(
        label="Arquivo CSV", widget=forms.ClearableFileInput(attrs={"accept": ".csv"})
    )

    def clean_arquivo(self):
        arquivo = self.cleaned_data["arquivo"]
        if arquivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("Envie um CSV de até 5 MB.")
        return arquivo
