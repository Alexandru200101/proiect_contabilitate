from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin, Group,Permission
from django.db import models
import uuid
from django.conf import settings 


# Create your models here.

class FirmaManager(BaseUserManager):
    def create_user(self, denumire, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Emailul este obligatoriu")
        email = self.normalize_email(email)
        firma = self.model(denumire=denumire, email=email, **extra_fields)
        firma.set_password(password)
        firma.save(using=self._db)
        return firma

    def create_superuser(self, denumire, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)  # Adaugă această linie
        
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
    
        return self.create_user(denumire, email, password, **extra_fields)


class Firma(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    denumire = models.CharField(max_length=255, unique=True)
    atribut = models.CharField(max_length=100, blank=True, null=True)
    email = models.EmailField(unique=True)
    cui = models.CharField(max_length=10, blank=True, null=True)
    regcom = models.CharField(max_length=50, blank=True, null=True)
    caen = models.CharField(max_length=10, blank=True, null=True)
    cap_social = models.DecimalField(max_digits=20, decimal_places=2, blank=True, null=True)
    localitate = models.CharField(max_length=100, blank=True, null=True)
    strada = models.CharField(max_length=100, blank=True, null=True)
    numar = models.CharField(max_length=10, blank=True, null=True)
    bloc = models.CharField(max_length=10, blank=True, null=True)
    scara = models.CharField(max_length=10, blank=True, null=True)
    ap = models.CharField(max_length=10, blank=True, null=True)
    judet = models.CharField(max_length=100, blank=True, null=True)
    sector = models.CharField(max_length=10, blank=True, null=True)
    codpostal = models.CharField(max_length=20, blank=True, null=True)
    telefon = models.CharField(max_length=30, blank=True, null=True)

    
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    objects = FirmaManager()

    USERNAME_FIELD = 'email'   # câmpul pentru autentificare
    REQUIRED_FIELDS = ['denumire']  # câmpuri obligatorii la createsuperuser

    groups = models.ManyToManyField(
        Group,
        related_name='firma_set',  # schimbă aici ca să nu fie clash cu auth.User
        blank=True,
        help_text='Grupurile acestui utilizator.',
        verbose_name='groups'
    )
    user_permissions = models.ManyToManyField(
        Permission,
        related_name='firma_user_set',  # schimbă aici
        blank=True,
        help_text='Permisiunile specifice acestui utilizator.',
        verbose_name='user permissions'
    )

    def __str__(self):
        return self.denumire
    
class PlanConturi(models.Model):
    id = models.UUIDField(primary_key = True,default = uuid.uuid4,editable = False)
    simbol = models.CharField(max_length = 300, blank=True, null=True)
    analitic = models.CharField(max_length = 300, blank=True, null=True)
    denumire = models.CharField(max_length = 300, blank=True, null=True)
    tip = models.CharField(max_length = 300, blank=True, null=True)

    def __str__(self):
        return f"{self.simbol} - {self.denumire}"
    

class RegistruJurnal(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    firma = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='registre_jurnale'
    )
    feldoc = models.CharField(max_length=4)
    nrdoc = models.PositiveIntegerField(editable=False)  # 🔹 acum e generat automat, fără null
    datadoc = models.DateTimeField(auto_now_add=True)
    explicatii = models.CharField(max_length=100, blank=True, null=True)
    debit = models.CharField(max_length=15)
    credit = models.CharField(max_length=15)
    suma = models.DecimalField(max_digits=20, decimal_places=2)

    def save(self, *args, **kwargs):
        # dacă e un document nou, setează automat numărul următor
        if not self.pk:
            last_doc = RegistruJurnal.objects.filter(firma=self.firma).order_by('-nrdoc').first()
            if last_doc:
                self.nrdoc = last_doc.nrdoc + 1
            else:
                self.nrdoc = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.firma.denumire_firma} - {self.feldoc or 'DOC'} {self.nrdoc}"
    

# Se va sterge
class Rapoarte(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    registru_jurnal = models.BooleanField(default=False)
    balanta = models.BooleanField(default=False)
    bilant = models.BooleanField(default=False)
    analiza = models.BooleanField(default=False)

    firma = models.ForeignKey('Firma', on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return f"Rapoarte {self.firma.denumire}"



