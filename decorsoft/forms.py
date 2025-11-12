from django import forms
from .models import Firma,RegistruJurnal,PlanConturi
import re
from django.core.exceptions import ValidationError


class SignupForm(forms.ModelForm):
    parola = forms.CharField(widget=forms.PasswordInput)  # field custom, nu în Meta
    confirmare_parola = forms.CharField(widget = forms.PasswordInput)

    class Meta:
        model = Firma
        fields = ["denumire", "cui", "email"]  # exclude "parola" aici

    def clean_cui(self):
        cui = self.cleaned_data.get('cui')
        if cui:
            cui = cui.strip()
            if not re.fullmatch(r'\d{4,10}', cui):
                raise ValidationError("CUI-ul trebuie sa contina doar cifre, intre 4 si 10 caractere")
        return cui

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.strip()
            # if not email.endswith('@firma.ro'):
            #     raise ValidationError("Email-ul trebuie să fie de forma user@firma.ro")
            pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
            if not re.fullmatch(pattern, email):
                raise ValidationError("Email-ul nu are formatul corect.")
        return email

    def clean_parola(self):
        parola = self.cleaned_data.get('parola')
        if parola:
            if len(parola) < 6:
                raise ValidationError("Parola trebuie să aibă cel puțin 6 caractere.")
            if not any(c.isupper() for c in parola):
                raise ValidationError("Parola trebuie să aibă cel puțin o literă mare.")
            if not any(c.isdigit() for c in parola):
                raise ValidationError("Parola trebuie să aibă cel puțin o cifră.")
        return parola
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["parola"])  # criptează parola
        if commit:
            user.save()
        return user

    
    def clean(self):
        cleaned_data = super().clean()
        parola = cleaned_data.get("parola")
        confirmare = cleaned_data.get("confirmare_parola")

        if parola and confirmare and parola != confirmare:
            raise ValidationError("Parola și confirmarea parolei nu coincid!")

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'exemplu@firma.ro'}))
    parola = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Introdu parola'}))

    
class InregistrareFirmaForm(SignupForm):
    class Meta(SignupForm.Meta):
        fields = SignupForm.Meta.fields + ['telefon','regcom','caen','cap_social','judet','sector','localitate','strada','numar','bloc','scara','ap','codpostal']
    def clean_telefon(self):
        telefon = self.cleaned_data.get('telefon')
        if telefon:
            telefon = telefon.strip()
            if not re.fullmatch(r'[\d\s\+\-]+',telefon):
                raise ValidationError('Numarul de telefon contine caractere invalide')
        return telefon
            
    def clean_regcom(self):
        regcom = self.cleaned_data.get('regcom')
        if regcom:
            regcom = regcom.strip()
            if len(regcom) < 3 or len(regcom) > 20:
                raise ValidationError("Numărul din Registrul Comerțului trebuie să aibă între 3 și 20 de caractere.")
            if not re.fullmatch(r'[A-Za-z0-9/]+', regcom):
                raise ValidationError("Numărul din Registrul Comerțului poate conține doar litere, cifre și '/'.")
        return regcom

    # CAEN
    def clean_caen(self):
        caen = self.cleaned_data.get('caen')
        if caen:
            caen = caen.strip()
            if not re.fullmatch(r'\d{4}', caen):
                raise ValidationError("Codul CAEN trebuie să fie format din 4 cifre.")
        return caen

    # Capital social
    def clean_cap_social(self):
        cap_social = self.cleaned_data.get('cap_social')
        if cap_social is not None:
            if cap_social < 0:
                raise ValidationError("Capitalul social nu poate fi negativ.")
        return cap_social

    # Județ
    def clean_judet(self):
        judet = self.cleaned_data.get('judet')
        if judet:
            judet = judet.strip()
            if len(judet) > 100:
                raise ValidationError("Județul nu poate depăși 100 de caractere.")
        return judet

    # Sector
    def clean_sector(self):
        sector = self.cleaned_data.get('sector')
        if sector:
            sector = sector.strip()
            if len(sector) > 10:
                raise ValidationError("Sectorul nu poate depăși 10 caractere.")
        return sector

    # Localitate
    def clean_localitate(self):
        localitate = self.cleaned_data.get('localitate')
        if localitate:
            localitate = localitate.strip()
            if len(localitate) > 100:
                raise ValidationError("Localitatea nu poate depăși 100 de caractere.")
        return localitate

    # Strada
    def clean_strada(self):
        strada = self.cleaned_data.get('strada')
        if strada:
            strada = strada.strip()
            if len(strada) > 100:
                raise ValidationError("Strada nu poate depăși 100 de caractere.")
        return strada

    # Număr
    def clean_numar(self):
        numar = self.cleaned_data.get('numar')
        if numar:
            numar = numar.strip()
            if len(numar) > 10:
                raise ValidationError("Numărul nu poate depăși 10 caractere.")
        return numar

    # Bloc
    def clean_bloc(self):
        bloc = self.cleaned_data.get('bloc')
        if bloc:
            bloc = bloc.strip()
            if len(bloc) > 10:
                raise ValidationError("Blocul nu poate depăși 10 caractere.")
        return bloc

    # Scara
    def clean_scara(self):
        scara = self.cleaned_data.get('scara')
        if scara:
            scara = scara.strip()
            if len(scara) > 10:
                raise ValidationError("Scara nu poate depăși 10 caractere.")
        return scara

    # Apartament
    def clean_ap(self):
        ap = self.cleaned_data.get('ap')
        if ap:
            ap = ap.strip()
            if len(ap) > 10:
                raise ValidationError("Apartamentul nu poate depăși 10 caractere.")
        return ap

    # Cod poștal
    def clean_codpostal(self):
        codpostal = self.cleaned_data.get('codpostal')
        if codpostal:
            codpostal = codpostal.strip()
            if not re.fullmatch(r'\d{4,10}', codpostal):
                raise ValidationError("Codul poștal trebuie să conțină doar cifre, între 4 și 10 caractere.")
        return codpostal
    
    def save(self, commit=True):
        firma = super().save(commit=False)
        firma.set_password(self.cleaned_data['parola'])
        if commit:
            firma.save()
        return firma

class RegistruJurnalForm(forms.ModelForm):
    # Înlocuim debit și credit cu ChoiceField din PlanConturi
    debit = forms.ChoiceField(choices=[], required=True)
    credit = forms.ChoiceField(choices=[], required=True)
    suma = forms.DecimalField(max_digits=20, decimal_places=2,required=True)
    feldoc = forms.CharField(max_length=4,required=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        conturi = PlanConturi.objects.all()
        choices = [(c.simbol, f"{c.simbol} - {c.denumire}") for c in conturi]
        self.fields['debit'].choices = choices
        self.fields['credit'].choices = choices

    class Meta:
        model = RegistruJurnal
        # Nu includem datadoc pentru că e auto_now_add
        fields = ['feldoc','explicatii', 'debit', 'credit', 'suma']








