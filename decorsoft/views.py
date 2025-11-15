from django.shortcuts import render, redirect,get_object_or_404
from .forms import SignupForm, LoginForm,InregistrareFirmaForm,RegistruJurnalForm
from .models import Firma,RegistruJurnal,PlanConturi
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.contrib import messages
from django.db.models import Q,Sum
from django.db import transaction
from django.http import JsonResponse,HttpResponseBadRequest, HttpResponseForbidden,HttpResponse
from django.views.decorators.http import require_POST
import csv
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from django.db.models import Q
from datetime import date
from decimal import Decimal






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
    conturi = PlanConturi.objects.all()

    return render(request, 'main/dashboard_firma_jurnal.html', {
        'registre': registre,
        'total_debit': total_suma,   # folosim suma
        'total_credit': total_suma,  # folosim suma
        'total_suma': total_suma,
        'conturi': conturi
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
        # last_doc = RegistruJurnal.objects.filter(firma=request.user).order_by('-nrdoc').first()
        # registru.nrdoc = (last_doc.nrdoc + 1) if last_doc else 1

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
    
#Export registru jurnal CSV si PDF
@login_required(login_url='login')
def export_registru(request):
    format_ = request.GET.get('format')
    ids = request.GET.get('ids', '')

    if not ids:
        return HttpResponse("Nicio operațiune selectată.", status=400)

    id_list = ids.split(',')
    operatiuni = RegistruJurnal.objects.filter(id__in=id_list, firma=request.user)

    if format_ == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="operatiuni.csv"'
        writer = csv.writer(response)
        writer.writerow(['Nr Doc', 'Tip Doc', 'Data', 'Debit', 'Credit', 'Suma', 'Explicatii'])
        for op in operatiuni:
            writer.writerow([op.nrdoc, op.feldoc, op.datadoc.strftime('%Y-%m-%d'), op.debit, op.credit, op.suma, op.explicatii])
        return response

    elif format_ == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        data = [['Nr Doc', 'Tip Doc', 'Data', 'Debit', 'Credit', 'Suma', 'Explicații']]
        for op in operatiuni:
            data.append([
                op.nrdoc,
                op.feldoc,
                op.datadoc.strftime('%Y-%m-%d') if op.datadoc else '',
                op.debit,
                op.credit,
                str(op.suma),
                op.explicatii or ''
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        doc.build([Paragraph("Registru Jurnal - Export", styles['Title']), table])
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="operatiuni.pdf"'
        response.write(pdf)
        return response

    else:
        return HttpResponse("Format invalid", status=400)
    


# CPP - Cont profit și pierdere
@login_required(login_url='/login/')
@transaction.atomic
def cont_profit_pierdere(request):
    """
    Generează și închide automat conturile 6 și 7 în contul 121 (Profit și Pierdere)
    pentru firma logată. Returnează JSON response.
    """
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.method == 'POST':
        # Este cerere AJAX sau POST
        return _process_profit_loss_accounts(request)
    else:
        # Este cerere normală GET - afișează template-ul
        return _render_profit_loss_template(request)

def _process_profit_loss_accounts(request):
    """Procesează închiderea conturilor și returnează JSON response."""
    try:
        firma = request.user
        data_inchidere = date.today()

        # Luăm toate operațiunile firmei care implică conturi 6 sau 7
        registre = RegistruJurnal.objects.filter(
            firma=firma
        ).filter(
            Q(debit__startswith='6') | Q(credit__startswith='6') |
            Q(debit__startswith='7') | Q(credit__startswith='7')
        )

        # Conturi de cheltuieli și venituri
        conturi_cheltuieli = PlanConturi.objects.filter(simbol__startswith='6')
        conturi_venituri = PlanConturi.objects.filter(simbol__startswith='7')

        total_cheltuieli = Decimal('0.00')
        total_venituri = Decimal('0.00')
        operatii_inchidere = []

        # --- INCHIDEM CONTURILE DE CHELTUIELI ---
        for cont in conturi_cheltuieli:
            rulaj_debit = sum(
                op.suma for op in registre.filter(debit=cont.simbol)
            )
            rulaj_credit = sum(
                op.suma for op in registre.filter(credit=cont.simbol)
            )
            sold = rulaj_debit - rulaj_credit
            if sold <= 0:
                continue  # cont fără sold

            total_cheltuieli += sold

            # Creăm înregistrare de închidere în jurnal
            operatie = RegistruJurnal.objects.create(
                firma=firma,
                datadoc=data_inchidere,
                feldoc="INCHEIERE 6->121",
                nrdoc=f"INC-{cont.simbol}",
                debit="121",       # 121 = Profit și pierdere
                credit=cont.simbol,
                suma=sold,
                explicatii=f"Închidere cont cheltuieli {cont.simbol} - {cont.denumire}"
            )
            operatii_inchidere.append({
                'tip': 'cheltuieli',
                'cont': cont.simbol,
                'denumire': cont.denumire,
                'suma': float(sold),
                'operatie_id': operatie.id
            })

        # --- INCHIDEM CONTURILE DE VENITURI ---
        for cont in conturi_venituri:
            rulaj_debit = sum(
                op.suma for op in registre.filter(debit=cont.simbol)
            )
            rulaj_credit = sum(
                op.suma for op in registre.filter(credit=cont.simbol)
            )
            sold = rulaj_credit - rulaj_debit
            if sold <= 0:
                continue  # cont fără sold

            total_venituri += sold

            # Creăm înregistrare de închidere în jurnal
            operatie = RegistruJurnal.objects.create(
                firma=firma,
                datadoc=data_inchidere,
                feldoc="INCHEIERE 7->121",
                nrdoc=f"INC-{cont.simbol}",
                debit=cont.simbol,
                credit="121",      # 121 = Profit și pierdere
                suma=sold,
                explicatii=f"Închidere cont venit {cont.simbol} - {cont.denumire}"
            )
            operatii_inchidere.append({
                'tip': 'venituri',
                'cont': cont.simbol,
                'denumire': cont.denumire,
                'suma': float(sold),
                'operatie_id': operatie.id
            })

        # Calculăm rezultatul final (profit/pierdere)
        rezultat = total_venituri - total_cheltuieli
        tip_rezultat = "PROFIT" if rezultat > 0 else "PIERDERE"

        operatii_finale = []

        # Închidem contul 121 în funcție de rezultat
        if rezultat != 0:
            if rezultat > 0:
                # Profit -> Debit 121 / Credit 129 (Repartizare profit)
                operatie_finala = RegistruJurnal.objects.create(
                    firma=firma,
                    datadoc=data_inchidere,
                    feldoc="REZULTAT FINAL",
                    nrdoc="INC-121",
                    debit="121",
                    credit="129",
                    suma=rezultat,
                    explicatii="Închidere cont 121 - Repartizare profit"
                )
                operatii_finale.append({
                    'tip': 'profit',
                    'debit': '121',
                    'credit': '129',
                    'suma': float(rezultat),
                    'operatie_id': operatie_finala.id
                })
            else:
                # Pierdere -> Debit 117 (Rezultat reportat) / Credit 121
                operatie_finala = RegistruJurnal.objects.create(
                    firma=firma,
                    datadoc=data_inchidere,
                    feldoc="REZULTAT FINAL",
                    nrdoc="INC-121",
                    debit="117",
                    credit="121",
                    suma=abs(rezultat),
                    explicatii="Închidere cont 121 - Înregistrare pierdere"
                )
                operatii_finale.append({
                    'tip': 'pierdere',
                    'debit': '117',
                    'credit': '121',
                    'suma': float(abs(rezultat)),
                    'operatie_id': operatie_finala.id
                })

        return JsonResponse({
            'success': True,
            'message': 'Închiderea conturilor de profit și pierdere a fost efectuată cu succes!',
            'data': {
                'total_cheltuieli': float(total_cheltuieli),
                'total_venituri': float(total_venituri),
                'rezultat': float(abs(rezultat)),
                'tip_rezultat': tip_rezultat,
                'operatii_inchidere': operatii_inchidere,
                'operatii_finale': operatii_finale,
                'data_inchidere': data_inchidere.isoformat(),
                'numar_operatii': len(operatii_inchidere) + len(operatii_finale)
            }
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'A apărut o eroare la procesarea închiderii conturilor: {str(e)}'
        }, status=400)

def _render_profit_loss_template(request):
    """Render template-ul normal pentru cereri GET."""
    firma = request.user
    return render(request, 'main/cont_profit_pierdere.html', {
        'firma': firma
    })


# Incarcare partial registru jurnal (AJAX)
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
    
# Balanta
@login_required(login_url='/login/')
def dashboard_firma_balanta(request):
    """
    Generează raportul complet pentru firma logată cu toate operațiunile din jurnal
    """
    firma = request.user

    # Toate înregistrările din jurnalul firmei, ordonate cronologic
    registre = RegistruJurnal.objects.filter(firma=firma).order_by('datadoc', 'nrdoc')

    # Toate conturile existente
    conturi = PlanConturi.objects.all().order_by('simbol')

    # Lista pentru operațiunile din jurnal
    operatiuni_jurnal = []

    for registru in registre:
        operatiuni_jurnal.append({
            'id': registru.id,
            'feldoc': registru.feldoc,
            'nrdoc': registru.nrdoc,
            'datadoc': registru.datadoc,
            'debit_cont': registru.debit,
            'credit_cont': registru.credit,
            'suma': registru.suma,
            'explicatii': registru.explicatii or '-',
            'firma': registru.firma
        })

    # Calculăm raportul final pentru fiecare cont
    raport_final = []

    for cont in conturi:
        # Filtram operațiunile care implică acest cont
        operatiuni_cont = registre.filter(Q(debit=cont.simbol) | Q(credit=cont.simbol))

        if not operatiuni_cont.exists():
            continue

        rulaj_debit = 0
        rulaj_credit = 0

        # CORECT: Rulajele reprezintă totalul sumelor în debit/credit
        for op in operatiuni_cont:
            if op.debit == cont.simbol:
                rulaj_debit += op.suma
            if op.credit == cont.simbol:
                rulaj_credit += op.suma

        # Calculăm soldul final în funcție de tipul contului
        if cont.tip == 'A':  # CONT ACTIV
            sold_final = rulaj_debit - rulaj_credit
            if sold_final >= 0:
                sfd = sold_final
                sfc = 0
            else:
                # Cont activ cu sold creditor (situație excepțională)
                sfd = 0
                sfc = abs(sold_final)
        else:  # CONT PASIV
            sold_final = rulaj_credit - rulaj_debit
            if sold_final >= 0:
                sfc = sold_final
                sfd = 0
            else:
                # Cont pasiv cu sold debitor (situație excepțională)
                sfc = 0
                sfd = abs(sold_final)

        raport_final.append({
            'simbol': cont.simbol,
            'denumire': cont.denumire,
            'tip': cont.tip,
            'rulaj_debit': rulaj_debit,
            'rulaj_credit': rulaj_credit,
            'sold_final_debit': sfd,
            'sold_final_credit': sfc,
        })

    # Total general (ar trebui să fie egal pentru debit și credit)
    total_general = sum(registru.suma for registru in registre)

    return render(request, 'main/dashboard_firma_balanta.html', {
        'firma': firma,
        'raport_final': raport_final,
        'operatiuni_jurnal': operatiuni_jurnal,
        'total_general_debit': total_general,
        'total_general_credit': total_general,
        'total_operatiuni': len(operatiuni_jurnal)
    })




@login_required(login_url='/login/')
def dashboard_firma_fisa_cont(request):
    """
    Pagina principală pentru fișa de cont - afișează doar conturile folosite
    """
    firma = request.user
    
    # Obținem doar conturile care apar în RegistruJurnal pentru firma conectată
    conturi_folosite = PlanConturi.objects.filter(
        Q(registrujurnal_debit__firma=firma) | Q(registrujurnal_credit__firma=firma)
    ).distinct().order_by('simbol')
    
    return render(request, 'main/dashboard_firma_fisa_cont.html', {
        'firma': firma,
        'conturi': conturi_folosite
    })


@login_required(login_url='/login/')
def fisa_cont_ajax(request, cont_simbol):
    """
    Generează fișa de cont pentru un cont specific (AJAX)
    """
    firma = request.user
    
    # Verificăm că contul există și a fost folosit de firma conectată
    cont = get_object_or_404(PlanConturi, simbol=cont_simbol)
    
    # Filtrăm operațiunile care implică acest cont pentru firma conectată
    registre = RegistruJurnal.objects.filter(
        firma=firma
    ).filter(
        Q(debit=cont.simbol) | Q(credit=cont.simbol)
    ).order_by('datadoc', 'nrdoc')
    
    # Calculăm rulajele
    rulaj_debit = sum(op.suma for op in registre if op.debit == cont.simbol)
    rulaj_credit = sum(op.suma for op in registre if op.credit == cont.simbol)
    
    # Calculăm soldul inițial (dacă există - în cazul tău probabil 0)
    sold_initial_debit = 0
    sold_initial_credit = 0
    
    # Calculăm soldul final în funcție de tipul contului
    if cont.tip == 'A':  # Cont ACTIV
        sold = (sold_initial_debit - sold_initial_credit) + (rulaj_debit - rulaj_credit)
        if sold >= 0:
            sold_final_debit = sold
            sold_final_credit = 0
        else:
            sold_final_debit = 0
            sold_final_credit = abs(sold)
    else:  # Cont PASIV (P)
        sold = (sold_initial_credit - sold_initial_debit) + (rulaj_credit - rulaj_debit)
        if sold >= 0:
            sold_final_credit = sold
            sold_final_debit = 0
        else:
            sold_final_credit = 0
            sold_final_debit = abs(sold)
    
    # Pregătim operațiunile cu sold progresiv (rulant)
    operatiuni_cu_sold = []
    sold_curent_debit = sold_initial_debit
    sold_curent_credit = sold_initial_credit
    
    for op in registre:
        # Actualizăm soldul curent
        if op.debit == cont.simbol:
            sold_curent_debit += op.suma
        if op.credit == cont.simbol:
            sold_curent_credit += op.suma
        
        # Calculăm soldul net
        if cont.tip == 'A':
            sold_net = sold_curent_debit - sold_curent_credit
            sold_d = sold_net if sold_net >= 0 else 0
            sold_c = abs(sold_net) if sold_net < 0 else 0
        else:
            sold_net = sold_curent_credit - sold_curent_debit
            sold_c = sold_net if sold_net >= 0 else 0
            sold_d = abs(sold_net) if sold_net < 0 else 0
        
        operatiuni_cu_sold.append({
            'operatie': op,
            'sold_debit': sold_d,
            'sold_credit': sold_c
        })
    
    return render(request, 'main/fisa_cont_partial.html', {
        'cont': cont,
        'registre': registre,
        'operatiuni_cu_sold': operatiuni_cu_sold,
        'sold_initial_debit': sold_initial_debit,
        'sold_initial_credit': sold_initial_credit,
        'rulaj_debit': rulaj_debit,
        'rulaj_credit': rulaj_credit,
        'sold_final_debit': sold_final_debit,
        'sold_final_credit': sold_final_credit
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

