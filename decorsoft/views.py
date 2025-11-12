from django.shortcuts import render, redirect
from .forms import SignupForm, LoginForm,InregistrareFirmaForm,RegistruJurnalForm
from .models import Firma,RegistruJurnal
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.contrib.auth import logout
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden




# Pagina principală
def main_view(request):
    return render(request, 'main/main.html')

# Signup utilizator
def signup_view(request):
    if request.method == 'POST':
        form = SignupForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('login')  # după signup, redirecționează la login
    else:
        form = SignupForm()
    return render(request, 'main/signup.html', {'form': form})


# Login utilizator + tine-ma minte buton
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            parola = form.cleaned_data['parola']
            remember_checked = request.POST.get('remember') == 'on'
            
            user = authenticate(request, username=email, password=parola)
            if user is not None:
                login(request, user)
                # Setează expirarea sesiunii
                if remember_checked:
                    
                    request.session.set_expiry(1209600)  # 2 săptămâni
                    # Setează cookie-ul de sesiune să expire după 2 săptămâni
                    request.session['session_persistent'] = True
                else:
                    
                    request.session.set_expiry(0)  # expiră la închiderea browserului
                    request.session['session_persistent'] = False
                request.session.modified = True
                
                return redirect('dashboard_firma')
            else:
                messages.error(request, "Email sau parola incorectă")
    else:
        form = LoginForm()
    return render(request, 'main/login.html', {'form': form})




# Dashboard firmă
@login_required(login_url='/login/')
def dashboard_firma(request):
    return render(request, 'main/dashboard_firma.html', {'firma': request.user})


# Dashboard registru jurnal + interogare baza de date
@login_required(login_url='/login/')
def dashboard_firma_jurnal(request):
    firma = request.user
    registre = RegistruJurnal.objects.filter(firma=firma).order_by('-datadoc')
    
    # Totalul folosește doar suma, pentru debit și credit
    total_suma = registre.aggregate(total=Sum('suma'))['total'] or 0

    return render(request, 'main/dashboard_firma_jurnal.html', {
        'registre': registre,
        'total_debit': total_suma,   # folosim suma
        'total_credit': total_suma,  # folosim suma
        'total_suma': total_suma
    })

# Formular adaugare operatiune
@login_required(login_url='login')
@require_POST
def adauga_registru_ajax(request):
    form = RegistruJurnalForm(request.POST)

    if form.is_valid():
        registru = form.save(commit=False)
        registru.firma = request.user

        # Generăm nrdoc automat
        last_doc = RegistruJurnal.objects.filter(firma=request.user).order_by('-nrdoc').first()
        registru.nrdoc = (last_doc.nrdoc + 1) if last_doc else 1

        registru.save()

        return JsonResponse({
            'success': True,
            'message': 'Înregistrarea a fost adăugată!',
            'data': {
                'id': registru.id,
                'feldoc': registru.feldoc,
                'nrdoc': registru.nrdoc,
                'suma': str(registru.suma),
                'explicatii': registru.explicatii,
                'datadoc': registru.datadoc.strftime('%Y-%m-%d %H:%M'),
            }
        })
    else:
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)
    

# Stergere inregistrare AJAX
@login_required(login_url='login')
@require_POST
def sterge_registru_ajax(request):
    id_registru = request.POST.get('id')

    if not id_registru:
        return HttpResponseBadRequest("Lipsește ID-ul înregistrării.")

    registru = get_object_or_404(RegistruJurnal, id=id_registru)

    # Verificăm că înregistrarea aparține utilizatorului curent
    if registru.firma != request.user:
        return HttpResponseForbidden("Nu aveți permisiunea de a șterge această înregistrare.")

    registru.delete()

    return JsonResponse({
        'success': True,
        'message': f"Înregistrarea {id_registru} a fost ștearsă cu succes!"
    })

# modificare inregistrare AJAX
@login_required(login_url='login')
@require_POST
def modifica_registru_ajax(request):
    id_registru = request.POST.get('id')
    registru = get_object_or_404(RegistruJurnal, id=id_registru)

    # Verificăm că înregistrarea aparține utilizatorului curent
    if registru.firma != request.user:
        return HttpResponseForbidden("Nu aveți permisiunea de a modifica această înregistrare.")

    form = RegistruJurnalForm(request.POST, instance=registru)

    if form.is_valid():
        registru = form.save()
        return JsonResponse({
            'success': True,
            'message': 'Înregistrarea a fost modificată cu succes!',
            'data': {
                'id': registru.id,
                'feldoc': registru.feldoc,
                'nrdoc': registru.nrdoc,
                'suma': str(registru.suma),
                'explicatii': registru.explicatii,
                'datadoc': registru.datadoc.strftime('%Y-%m-%d %H:%M'),
                'debit': registru.debit,
                'credit': registru.credit,
            }
        })
    else:
        return JsonResponse({'success': False, 'errors': form.errors}, status=400)




@login_required(login_url='login')
def registru_jurnal_partial(request):
    firma = request.user
    form = RegistruJurnalForm()
    registre = RegistruJurnal.objects.filter(firma=firma).order_by('-datadoc')

    # Răspundem doar cu fragmentul HTML, nu cu tot layoutul dashboard
    return render(request, 'main/registru_jurnal_partial.html', {
        'form': form,
        'registre': registre
    })
    




# Pagina admin-dashboard + bara cautare firma dupa denumire
@login_required(login_url='admin_login')
def admin_dashboard(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    query = request.GET.get('q', '')
    firme = []

    if query:
        firme = Firma.objects.filter(
            Q(denumire__icontains=query)
        )

    return render(request, 'main/admin_dashboard.html', {
        'query': query,
        'firme': firme
    })

# Login superuser
def admin_login_view(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect('admin_dashboard')

    mesaj = None
    next_url = request.GET.get('next', '')

    if request.method == "POST":
        username = request.POST.get("username")
        parola = request.POST.get("password")

        user = authenticate(request, username=username, password=parola)

        if user is not None and user.is_superuser:
            login(request, user)
            messages.success(request, "Autentificare reușită!")
            # dacă există next, redirecționează acolo
            if request.POST.get('next'):
                return redirect(request.POST.get('next'))
            elif next_url:
                return redirect(next_url)
            else:
                return redirect("admin_dashboard")
        else:
            mesaj = "Username sau parola incorectă!"
            messages.error(request, "Autentificare eșuată!")

    return render(request, "main/admin_login.html", {"mesaj": mesaj, "next": next_url})

# Functionalitati in admin_dashboard 
# 1 -> Introducere firma in baza de date
@login_required
def inregistrare_firma(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    form = InregistrareFirmaForm()
    if request.method == "POST":
        form = InregistrareFirmaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Firma a fost înregistrată cu succes!")
            return redirect('admin_dashboard')
        else:
            messages.error(request, "Corectează erorile din formular!")
            
    
    return render(request, 'main/inregistrare_firma.html', {'form': form})

# 2 -> Afisare firme si detalii
@login_required
def afisare_firme(request):
    if not request.user.is_superuser:
        raise PermissionDenied

    firme = Firma.objects.all()
    return render(request,'main/afisare_firme.html',{'firme':firme})

# Trimitere la un dashboard pentru o anumita firma
# Incarcare formular schimbare date 
@login_required
def admin_dashboard_firma(request, firma_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    firma = get_object_or_404(Firma, id=firma_id)
    form = InregistrareFirmaForm(request.POST or None, instance=firma)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, f"Firma '{firma.denumire}' a fost modificată cu succes!")
        return redirect('admin_dashboard_firma', firma_id=firma.id)
    elif request.method == 'POST':
        messages.error(request, "Formularul conține erori, te rugăm să corectezi datele.")

    return render(request, 'main/admin_dashboard_firma.html', {'firma': firma, 'form': form})


# Functionalitati dashboard_firma
# 1 -> Sterge o firma  
@login_required
def sterge_firma(request, firma_id):
    if not request.user.is_superuser:
        raise PermissionDenied

    firma = get_object_or_404(Firma, id=firma_id)

    if request.method == 'POST':
        firma.delete()
        messages.success(request, f"Firma '{firma.denumire}' a fost ștearsă cu succes!")
        return redirect('afisare_firme')  # redirect la lista firmelor









# Logout pentru ADMIN
def custom_logout_admin(request):
    logout(request)
    messages.info(request, "Te-ai delogat cu succes din panoul de administrare!")
    return redirect('admin_login')


# Logout pentru utilizator (firmă)
def custom_logout(request):
    logout(request)
    messages.info(request, "Te-ai delogat cu succes din contul firmei!")
    return redirect('login')

