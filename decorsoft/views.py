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
from datetime import date, datetime
from decimal import Decimal
from dateutil import parser
import logging


logger = logging.getLogger(__name__)
TVA_IMPLICIT = Decimal('0.21')





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
        registru.save()

        tva_operatie = None
        TVA = Decimal("0.21")

        # ---------------------------------
        # TVA colectată (client) – Debit 411
        # ---------------------------------
        if registru.debit == "411":
            valoare_tva = (registru.suma * TVA).quantize(Decimal("0.01"))

            tva_operatie = RegistruJurnal.objects.create(
                firma=request.user,
                datadoc=registru.datadoc,
                feldoc=f"{registru.feldoc} - TVA",
                nrdoc=f"{registru.nrdoc}-TVA",
                debit="411",
                credit="4427",
                suma=valoare_tva,
                explicatii=f"TVA colectată 21% pentru document {registru.nrdoc}",
                parent=registru  #  operațiune copil
            )

        # ---------------------------------
        # TVA deductibilă (furnizor) – Credit 401
        # ---------------------------------
        if registru.credit == "401":
            valoare_tva = (registru.suma * TVA).quantize(Decimal("0.01"))

            tva_operatie = RegistruJurnal.objects.create(
                firma=request.user,
                datadoc=registru.datadoc,
                feldoc=f"{registru.feldoc} - TVA",
                nrdoc=f"{registru.nrdoc}-TVA",
                debit="4426",
                credit="401",
                suma=valoare_tva,
                explicatii=f"TVA deductibilă 21% pentru document {registru.nrdoc}",
                parent=registru  #  operațiune copil
            )

        # -----------------------------
        # Răspuns AJAX
        # -----------------------------
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
                'tva_added': tva_operatie is not None,
                'tva_id': tva_operatie.id if tva_operatie else None
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

    # verificare că aparține utilizatorului
    if registru.firma != request.user:
        return HttpResponseForbidden("Nu aveți permisiunea de a șterge această înregistrare.")

    # 🔥 Șterge automat toate operațiunile TVA copil
    registru.tva_children.all().delete()

    # Șterge înregistrarea principală
    registru.delete()

    return JsonResponse({
        'success': True,
        'message': f"Înregistrarea {id_registru} și TVA-ul aferent au fost șterse!"
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
    
# Export registru jurnal CSV si PDF
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


@login_required
def import_jurnal_csv(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "message": "Metodă invalidă."})

    firma = request.user

    if "csv_file" not in request.FILES:
        return JsonResponse({"success": False, "message": "Nu ai selectat niciun fișier."})

    file = request.FILES["csv_file"]

    try:
        decoded_file = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(decoded_file)
        # Curățăm eventuale spații în header
        reader.fieldnames = [f.strip() for f in reader.fieldnames]
    except Exception as e:
        logger.exception("CSV invalid sau nu poate fi citit")
        return JsonResponse({"success": False, "message": "Fișier CSV invalid."})

    adaugate = 0
    erori = []

    for row_num, row in enumerate(reader, start=2):  # start=2 pentru header
        try:
            # Preluare câmpuri corecte
            debit = row.get("debit_scur", "").strip()
            credit = row.get("credit_scu", "").strip()
            suma_str = row.get("suma", "").strip()
            data_str = row.get("data", "").strip()
            tipdoc = row.get("tipdoc", "").strip()[:4]
            nrdoc = row.get("nrdoc", "").strip()
            explicatii = row.get("explicatii", "").strip()

            # Verificare câmpuri obligatorii
            if not debit:
                msg = f"Rând {row_num}: Eroare cont debit - câmp gol"
                logger.error(msg)
                erori.append(msg)
                continue
            if not credit:
                msg = f"Rând {row_num}: Eroare cont credit - câmp gol"
                logger.error(msg)
                erori.append(msg)
                continue

            # Verificăm dacă conturile există în planul de conturi
            if not PlanConturi.objects.filter(simbol=debit).exists():
                msg = f"Rând {row_num}: Cont debit invalid: '{debit}'"
                logger.error(msg)
                erori.append(msg)
                continue
            if not PlanConturi.objects.filter(simbol=credit).exists():
                msg = f"Rând {row_num}: Cont credit invalid: '{credit}'"
                logger.error(msg)
                erori.append(msg)
                continue

            # Conversie dată
            try:
                datadoc = parser.parse(data_str, dayfirst=True).date()
            except Exception as e:
                msg = f"Rând {row_num}: Eroare conversie dată - valoare: '{data_str}' | {str(e)}"
                logger.error(msg)
                erori.append(msg)
                continue

            # Conversie sumă
            try:
                suma = Decimal(suma_str)
            except Exception as e:
                msg = f"Rând {row_num}: Eroare conversie sumă - valoare: '{suma_str}' | {str(e)}"
                logger.error(msg)
                erori.append(msg)
                continue

            # Creare obiect RegistruJurnal
            RegistruJurnal.objects.create(
                firma=firma,
                feldoc=tipdoc,
                nrdoc=nrdoc,
                datadoc=datadoc,
                debit=debit,
                credit=credit,
                suma=suma,
                explicatii=explicatii
            )
            adaugate += 1

        except Exception as e:
            msg = f"Rând {row_num}: Eroare neașteptată - {str(e)}"
            logger.exception(msg)
            erori.append(msg)

    logger.info(f"Import finalizat: {adaugate} rânduri adăugate, {len(erori)} erori")
    return JsonResponse({
        "success": True,
        "message": f"Import finalizat: {adaugate} rânduri adăugate. Erori: {len(erori)}",
        "errors": erori
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
@login_required(login_url="/login/")
def dashboard_firma_balanta(request):
    firma = request.user

    # 1. Obținem toate rulajele într-o singură interogare
    rulaje = (
        RegistruJurnal.objects
        .filter(firma=firma)
        .values('debit')        # grupăm pe cont debit
        .annotate(total_debit=Sum('suma'))
    )

    rulaje_credit = (
        RegistruJurnal.objects
        .filter(firma=firma)
        .values('credit')       # grupăm pe cont credit
        .annotate(total_credit=Sum('suma'))
    )

    # Transformăm în dicționare pentru acces rapid
    debit_dict = {r['debit']: r['total_debit'] for r in rulaje}
    credit_dict = {r['credit']: r['total_credit'] for r in rulaje_credit}

    # 2. Luăm toate conturile
    conturi = PlanConturi.objects.all().order_by("simbol")

    raport_final = []

    for cont in conturi:
        simbol = cont.simbol

        rulaj_debit = debit_dict.get(simbol, 0)
        rulaj_credit = credit_dict.get(simbol, 0)

        if rulaj_debit == 0 and rulaj_credit == 0:
            continue  # skip conturile fără mișcare

        # Calcul sold final
        if cont.tip == "A":      # Activ
            sold = rulaj_debit - rulaj_credit
            sfd = max(sold, 0)
            sfc = max(-sold, 0)
        else:                    # Pasiv
            sold = rulaj_credit - rulaj_debit
            sfc = max(sold, 0)
            sfd = max(-sold, 0)

        raport_final.append({
            "simbol": simbol,
            "denumire": cont.denumire,
            "tip": cont.tip,
            "rulaj_debit": float(rulaj_debit),
            "rulaj_credit": float(rulaj_credit),
            "sold_final_debit": float(sfd),
            "sold_final_credit": float(sfc),
        })

    # Total general (tot într-o singură interogare)
    total_general = (
        RegistruJurnal.objects
        .filter(firma=firma)
        .aggregate(t=Sum("suma"))["t"] or 0
    )

    return render(request, "main/dashboard_firma_balanta.html", {
        "firma": firma,
        "raport_final": raport_final,
        "total_general_debit": total_general,
        "total_general_credit": total_general,
    })

@login_required(login_url='login')
def export_balanta(request):
    format_ = request.GET.get('format', 'csv')
    firma = request.user

    # Preluăm datele pentru balanță
    registre = RegistruJurnal.objects.filter(firma=firma).order_by('datadoc', 'nrdoc')
    conturi = PlanConturi.objects.all().order_by('simbol')

    # Construim lista de date
    date_balanta = []
    for cont in conturi:
        operatiuni_cont = registre.filter(Q(debit=cont.simbol) | Q(credit=cont.simbol))
        if not operatiuni_cont.exists():
            continue

        rulaj_debit = sum(op.suma for op in operatiuni_cont if op.debit == cont.simbol)
        rulaj_credit = sum(op.suma for op in operatiuni_cont if op.credit == cont.simbol)

        if cont.tip == 'A':
            sold_final = rulaj_debit - rulaj_credit
            sfd = max(sold_final, 0)
            sfc = max(-sold_final, 0)
        else:
            sold_final = rulaj_credit - rulaj_debit
            sfc = max(sold_final, 0)
            sfd = max(-sold_final, 0)

        date_balanta.append([
            cont.simbol,
            cont.denumire,
            cont.tip,
            rulaj_debit,
            rulaj_credit,
            sfd,
            sfc
        ])

    if format_ == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="balanta.csv"'

        writer = csv.writer(response)
        writer.writerow(['Simbol', 'Denumire', 'Tip', 'Rulaj Debit', 'Rulaj Credit', 'Sold Debit', 'Sold Credit'])
        for row in date_balanta:
            writer.writerow(row)

        return response

    elif format_ == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()

        # Tabel
        data = [['Simbol', 'Denumire', 'Tip', 'Rulaj Debit', 'Rulaj Credit', 'Sold Debit', 'Sold Credit']]
        data.extend(date_balanta)

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))

        doc.build([Paragraph("Balanță - Export", styles['Title']), table])
        pdf = buffer.getvalue()
        buffer.close()

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="balanta.pdf"'
        response.write(pdf)
        return response

    else:
        return HttpResponse("Format invalid", status=400)





@login_required(login_url='/login/')
def dashboard_firma_fisa_cont(request):
    firma = request.user

    # Luăm toate simbolurile de cont folosite de firmă
    simboluri = RegistruJurnal.objects.filter(firma=firma).values_list('debit', flat=True)
    simboluri2 = RegistruJurnal.objects.filter(firma=firma).values_list('credit', flat=True)

    simboluri_folosite = set(list(simboluri) + list(simboluri2))

    # Luăm doar conturile existente în PlanConturi
    conturi_folosite = PlanConturi.objects.filter(simbol__in=simboluri_folosite).order_by('simbol')

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


class SituatieConturi:
    """Calcul solduri finale pe baza RegistruJurnal pentru firma logată."""
    
    def __init__(self, firma):
        self.firma = firma
        self.solduri = self._get_solduri_finale()

    def _get_solduri_finale(self):
        """Calculează soldurile pentru fiecare cont din registrul jurnal."""
        solduri = {}

        # Preluăm toate conturile distincte
        conturi_debit = RegistruJurnal.objects.filter(
            firma=self.firma
        ).values_list('debit', flat=True).distinct()
        
        conturi_credit = RegistruJurnal.objects.filter(
            firma=self.firma
        ).values_list('credit', flat=True).distinct()

        # Combinăm toate conturile unice
        toate_conturile = set(conturi_debit) | set(conturi_credit)
        toate_conturile = {cont for cont in toate_conturile if cont and str(cont).strip()}

        for simbol in toate_conturile:
            try:
                simbol_str = str(simbol).strip()

                # Total debit pentru acest cont
                debit_total = RegistruJurnal.objects.filter(
                    firma=self.firma,
                    debit=simbol_str
                ).aggregate(total=Sum('suma'))['total'] or 0

                # Total credit pentru acest cont
                credit_total = RegistruJurnal.objects.filter(
                    firma=self.firma,
                    credit=simbol_str
                ).aggregate(total=Sum('suma'))['total'] or 0

                # Calculăm soldul final (pozitiv = debit, negativ = credit)
                sold_final = float(debit_total) - float(credit_total)

                solduri[simbol_str] = {
                    'debit_total': float(debit_total),
                    'credit_total': float(credit_total),
                    'sold_final': sold_final,
                    'SD': float(debit_total) if sold_final >= 0 else 0,
                    'SC': abs(float(credit_total)) if sold_final < 0 else 0
                }
                
            except (ValueError, TypeError) as e:
                print(f"Eroare la procesarea contului {simbol}: {e}")
                continue

        return solduri

    def get_sold(self, simbol, tip_sold='SD'):
        """
        Returnează soldul pentru un cont specific sau pentru toate sub-conturile.
        
        Args:
            simbol: Contul căutat (ex: '201', '47', '4711')
            tip_sold: 'SD' (sold debitor) sau 'SC' (sold creditor)
        """
        tip_sold = tip_sold.upper()
        simbol_str = str(simbol).strip()
        
        total = 0
        conturi_gasite = []
        
        # Verificăm dacă există contul exact
        if simbol_str in self.solduri:
            valoare = self.solduri[simbol_str].get(tip_sold, 0)
            total += valoare
            if valoare != 0:
                conturi_gasite.append(f"{simbol_str}: {valoare:.2f}")
        
        # Căutăm și sub-conturi
        for cont, sold in self.solduri.items():
            # Verificăm dacă este sub-cont (ex: '4711' este sub-cont al '471')
            if cont != simbol_str and cont.startswith(simbol_str):
                valoare = sold.get(tip_sold, 0)
                total += valoare
                if valoare != 0:
                    conturi_gasite.append(f"{cont}: {valoare:.2f}")
        
        # Logging detaliat
        if conturi_gasite:
            logger.info(f"Cont {simbol_str} ({tip_sold}): TOTAL = {total:.2f}")
            for cont_info in conturi_gasite:
                logger.info(f"  └─ {cont_info}")
        
        return total

    def get_toate_conturile(self):
        """Returnează lista tuturor conturilor cu soldurile lor."""
        return self.solduri

    def afiseaza_situatie(self):
        """Afișează situația conturilor pentru debug."""
        print("\n=== SITUAȚIA CONTURILOR ===")
        for cont in sorted(self.solduri.keys()):
            sold = self.solduri[cont]
            print(f"Cont {cont}: Debit={sold['debit_total']:.2f}, "
                  f"Credit={sold['credit_total']:.2f}, "
                  f"Sold Final={sold['sold_final']:.2f}")
        print("=" * 50 + "\n")


def calculeaza_bilant(situatie_conturi, sold_471_1an=0, sold_471_peste1an=0,
                      sold_475_1an=0, sold_475_peste1an=0,
                      sold_472_1an=0, sold_472_peste1an=0,
                      sold_478_1an=0, sold_478_peste1an=0):
    """
    Calculează bilanțul contabil conform OMFP 1802/2014.
    
    Args:
        situatie_conturi: Instanță SituatieConturi
        sold_471_*: Solduri pentru cheltuieli în avans pe perioade
        sold_475_*: Solduri pentru venituri în avans pe perioade
        sold_472_*: Solduri pentru subvenții pe perioade
        sold_478_*: Solduri pentru alte provizioane pe perioade
    """
    S = situatie_conturi

    def SD(cont):
        """Returnează soldul debitor pentru un cont."""
        return S.get_sold(str(cont), 'SD')

    def SC(cont):
        """Returnează soldul creditor pentru un cont."""
        return S.get_sold(str(cont), 'SC')

    rezultate = {}
    
    try:
        logger.info("=" * 80)
        logger.info("ÎNCEPE CALCULUL BILANȚULUI")
        logger.info("=" * 80)
        
        # ========== ACTIVE ==========
        
        logger.info("\n### A. ACTIVE IMOBILIZATE ###\n")
        
        # I. IMOBILIZĂRI NECORPORALE (rd_01)
        logger.info("I. IMOBILIZĂRI NECORPORALE (rd_01):")
        rd_01_componente = {
            'SD(201)': SD('201'),
            'SD(203)': SD('203'),
            'SD(205)': SD('205'),
            'SD(206)': SD('206'),
            'SD(2071)': SD('2071'),
            'SD(4094)': SD('4094'),
            'SD(208)': SD('208'),
            'SC(280)': -SC('280'),
            'SC(290)': -SC('290'),
            'SC(4904)': -SC('4904')
        }
        for key, val in rd_01_componente.items():
            if val != 0:
                logger.info(f"  {key} = {val:.2f}")
        rezultate['rd_01'] = sum(rd_01_componente.values())
        logger.info(f"  → TOTAL rd_01 = {rezultate['rd_01']:.2f}\n")
        
        # II. IMOBILIZĂRI CORPORALE (rd_02)
        logger.info("II. IMOBILIZĂRI CORPORALE (rd_02):")
        rd_02_componente = {
            'SD(211)': SD('211'), 'SD(212)': SD('212'), 'SD(213)': SD('213'),
            'SD(214)': SD('214'), 'SD(215)': SD('215'), 'SD(216)': SD('216'),
            'SD(217)': SD('217'), 'SD(223)': SD('223'), 'SD(224)': SD('224'),
            'SD(227)': SD('227'), 'SD(231)': SD('231'), 'SD(235)': SD('235'),
            'SD(4093)': SD('4093'), 'SC(281)': -SC('281'), 'SC(291)': -SC('291'),
            'SC(2931)': -SC('2931'), 'SC(2935)': -SC('2935'), 'SC(4903)': -SC('4903')
        }
        for key, val in rd_02_componente.items():
            if val != 0:
                logger.info(f"  {key} = {val:.2f}")
        rezultate['rd_02'] = sum(rd_02_componente.values())
        logger.info(f"  → TOTAL rd_02 = {rezultate['rd_02']:.2f}\n")
        
        # III. IMOBILIZĂRI FINANCIARE (rd_03)
        logger.info("III. IMOBILIZĂRI FINANCIARE (rd_03):")
        rd_03_componente = {
            'SD(261)': SD('261'), 'SD(262)': SD('262'), 'SD(263)': SD('263'),
            'SD(265)': SD('265'), 'SD(267)': SD('267'), 'SC(296)': -SC('296')
        }
        for key, val in rd_03_componente.items():
            if val != 0:
                logger.info(f"  {key} = {val:.2f}")
        rezultate['rd_03'] = sum(rd_03_componente.values())
        logger.info(f"  → TOTAL rd_03 = {rezultate['rd_03']:.2f}\n")
        
        # ACTIVE IMOBILIZATE - TOTAL (rd_04)
        rezultate['rd_04'] = rezultate['rd_01'] + rezultate['rd_02'] + rezultate['rd_03']
        logger.info(f"ACTIVE IMOBILIZATE - TOTAL (rd_04) = {rezultate['rd_04']:.2f}\n")

        # B. ACTIVE CIRCULANTE
        logger.info("\n### B. ACTIVE CIRCULANTE ###\n")
        
        # I. STOCURI (rd_05)
        logger.info("I. STOCURI (rd_05):")
        stocuri_sd = ['301','302','303','321','322','308','323','326','327','328',
                      '331','332','341','345','346','347','348','351','354','356',
                      '357','358','361','368','371','378','381','388','4091']
        stocuri_sc = ['391','392','393','394','395','396','397','398','4901']
        
        rd_05_total = 0
        for cont in stocuri_sd:
            val = SD(cont)
            if val != 0:
                logger.info(f"  SD({cont}) = {val:.2f}")
                rd_05_total += val
        
        for cont in stocuri_sc:
            val = SC(cont)
            if val != 0:
                logger.info(f"  SC({cont}) = -{val:.2f}")
                rd_05_total -= val
        
        rezultate['rd_05'] = rd_05_total
        logger.info(f"  → TOTAL rd_05 = {rezultate['rd_05']:.2f}\n")
        
        # II. CREANȚE (rd_06)
        logger.info("II. CREANȚE (rd_06):")
        logger.info("  a) Suma de încasat după un an (rd_06a):")
        
        creante_sd = ['4092','411','413','418','425','4282','431','436','437','4382',
                      '441','4424','4428','444','445','446','447','4482','451','453',
                      '456','4582','461','4662','473','5187','267']
        creante_sc = ['491','495','496','4902','296']
        
        rd_06a_total = 0
        for cont in creante_sd:
            val = SD(cont)
            if val != 0:
                logger.info(f"    SD({cont}) = {val:.2f}")
                rd_06a_total += val
        
        for cont in creante_sc:
            val = SC(cont)
            if val != 0:
                logger.info(f"    SC({cont}) = -{val:.2f}")
                rd_06a_total -= val
        
        rezultate['rd_06a'] = rd_06a_total
        logger.info(f"    → TOTAL rd_06a = {rezultate['rd_06a']:.2f}")
        
        logger.info("  b) Suma de încasat într-un an (rd_06b):")
        rezultate['rd_06b'] = SD('463')
        logger.info(f"    SD(463) = {rezultate['rd_06b']:.2f}")
        logger.info(f"    → TOTAL rd_06b = {rezultate['rd_06b']:.2f}")
        
        rezultate['rd_06'] = rezultate['rd_06a'] + rezultate['rd_06b']
        logger.info(f"  → TOTAL CREANȚE (rd_06) = {rezultate['rd_06']:.2f}\n")
        
        # III. INVESTIȚII PE TERMEN SCURT (rd_07)
        logger.info("III. INVESTIȚII PE TERMEN SCURT (rd_07):")
        investitii_sd = ['501','505','506','507','508','5113','5114']
        investitii_sc = ['591','595','596','598']
        
        rd_07_total = 0
        for cont in investitii_sd:
            val = SD(cont)
            if val != 0:
                logger.info(f"  SD({cont}) = {val:.2f}")
                rd_07_total += val
        
        for cont in investitii_sc:
            val = SC(cont)
            if val != 0:
                logger.info(f"  SC({cont}) = -{val:.2f}")
                rd_07_total -= val
        
        rezultate['rd_07'] = rd_07_total
        logger.info(f"  → TOTAL rd_07 = {rezultate['rd_07']:.2f}\n")
        
        # IV. CASA ȘI CONTURI LA BĂNCI (rd_08)
        logger.info("IV. CASA ȘI CONTURI LA BĂNCI (rd_08):")
        casa_conturi = ['508','5112','512','531','532','541','542']
        
        rd_08_total = 0
        for cont in casa_conturi:
            val = SD(cont)
            if val != 0:
                logger.info(f"  SD({cont}) = {val:.2f}")
                rd_08_total += val
        
        rezultate['rd_08'] = rd_08_total
        logger.info(f"  → TOTAL rd_08 = {rezultate['rd_08']:.2f}\n")
        
        # ACTIVE CIRCULANTE - TOTAL (rd_09)
        rezultate['rd_09'] = (
            rezultate['rd_05'] + rezultate['rd_06'] + 
            rezultate['rd_07'] + rezultate['rd_08']
        )
        logger.info(f"ACTIVE CIRCULANTE - TOTAL (rd_09) = {rezultate['rd_09']:.2f}\n")

        # C. CHELTUIELI ÎN AVANS (rd_10)
        logger.info("\n### C. CHELTUIELI ÎN AVANS ###\n")
        rezultate['rd_11'] = float(sold_471_1an)  # Sub un an
        rezultate['rd_12'] = float(sold_471_peste1an)  # Peste un an
        rezultate['rd_10'] = rezultate['rd_11'] + rezultate['rd_12']
        logger.info(f"Sub un an (rd_11) = {rezultate['rd_11']:.2f}")
        logger.info(f"Peste un an (rd_12) = {rezultate['rd_12']:.2f}")
        logger.info(f"TOTAL (rd_10) = {rezultate['rd_10']:.2f}\n")

        # D. DATORII: SUMELE CARE TREBUIE PLĂTITE ÎNTR-O PERIOADĂ DE PÂNĂ LA UN AN (rd_13)
        logger.info("\n### D. DATORII CURENTE (rd_13) ###\n")
        datorii_sc = ['161','162','166','167','168','269','401','403','404','405',
                      '408','419','421','423','424','426','427','4281','431','436',
                      '437','4381','441','4423','444','446','447','4481','451','453',
                      '455','456','457','4581','462','4661','467','473','509','5186','519','4428']
        
        rd_13_total = 0
        for cont in datorii_sc:
            val = SC(cont)
            if val != 0:
                logger.info(f"  SC({cont}) = {val:.2f}")
                rd_13_total += val
        
        val_169 = SD('169')
        if val_169 != 0:
            logger.info(f"  SD(169) = -{val_169:.2f}")
            rd_13_total -= val_169
        
        rezultate['rd_13'] = rd_13_total
        logger.info(f"  → TOTAL rd_13 = {rezultate['rd_13']:.2f}\n")

        # ACTIVE CIRCULANTE NETE / DATORII CURENTE NETE (rd_14)
        rezultate['rd_14'] = (
            rezultate['rd_09'] + rezultate['rd_11'] - 
            rezultate['rd_13'] - float(sold_475_1an) - 
            float(sold_472_1an) - float(sold_478_1an)
        )
        logger.info(f"ACTIVE CIRCULANTE NETE (rd_14) = {rezultate['rd_14']:.2f}")
        logger.info(f"  = rd_09({rezultate['rd_09']:.2f}) + rd_11({rezultate['rd_11']:.2f}) - rd_13({rezultate['rd_13']:.2f}) - sold_475_1an({float(sold_475_1an):.2f}) - sold_472_1an({float(sold_472_1an):.2f}) - sold_478_1an({float(sold_478_1an):.2f})\n")

        # TOTAL ACTIVE MINUS DATORII CURENTE (rd_15)
        rezultate['rd_15'] = rezultate['rd_04'] + rezultate['rd_12'] + rezultate['rd_14']
        logger.info(f"TOTAL ACTIVE MINUS DATORII CURENTE (rd_15) = {rezultate['rd_15']:.2f}")
        logger.info(f"  = rd_04({rezultate['rd_04']:.2f}) + rd_12({rezultate['rd_12']:.2f}) + rd_14({rezultate['rd_14']:.2f})\n")

        # ========== PASIVE ==========
        
        logger.info("\n### E. PROVIZIOANE ###\n")
        
        # Venituri în avans (rd_19)
        rezultate['rd_20'] = float(sold_475_1an)
        rezultate['rd_21'] = float(sold_475_peste1an)
        rezultate['rd_19'] = rezultate['rd_20'] + rezultate['rd_21']
        logger.info(f"Venituri în avans (rd_19):")
        logger.info(f"  Sub un an (rd_20) = {rezultate['rd_20']:.2f}")
        logger.info(f"  Peste un an (rd_21) = {rezultate['rd_21']:.2f}")
        logger.info(f"  TOTAL = {rezultate['rd_19']:.2f}\n")
        
        # Subvenții pentru investiții (rd_22)
        rezultate['rd_23'] = float(sold_472_1an)
        rezultate['rd_24'] = float(sold_472_peste1an)
        rezultate['rd_22'] = rezultate['rd_23'] + rezultate['rd_24']
        logger.info(f"Subvenții pentru investiții (rd_22):")
        logger.info(f"  Sub un an (rd_23) = {rezultate['rd_23']:.2f}")
        logger.info(f"  Peste un an (rd_24) = {rezultate['rd_24']:.2f}")
        logger.info(f"  TOTAL = {rezultate['rd_22']:.2f}\n")
        
        # Alte provizioane (rd_25)
        rezultate['rd_26'] = float(sold_478_1an)
        rezultate['rd_27'] = float(sold_478_peste1an)
        rezultate['rd_25'] = rezultate['rd_26'] + rezultate['rd_27']
        logger.info(f"Alte provizioane (rd_25):")
        logger.info(f"  Sub un an (rd_26) = {rezultate['rd_26']:.2f}")
        logger.info(f"  Peste un an (rd_27) = {rezultate['rd_27']:.2f}")
        logger.info(f"  TOTAL = {rezultate['rd_25']:.2f}\n")
        
        # Provizioane pentru pensii și obligații similare (rd_28)
        rezultate['rd_28'] = SC('2075')
        logger.info(f"Provizioane pentru pensii (rd_28):")
        logger.info(f"  SC(2075) = {rezultate['rd_28']:.2f}\n")
        
        # TOTAL PROVIZIOANE (rd_18)
        rezultate['rd_18'] = (
            rezultate['rd_19'] + rezultate['rd_22'] + 
            rezultate['rd_25'] + rezultate['rd_28']
        )
        logger.info(f"TOTAL PROVIZIOANE (rd_18) = {rezultate['rd_18']:.2f}\n")

        # F. CAPITAL ȘI REZERVE
        logger.info("\n### F. CAPITAL ȘI REZERVE ###\n")
        
        # Capitaluri cu sold creditor
        capital_sc = {
            'rd_29': ('1012', 'Capital subscris vărsat'),
            'rd_30': ('1011', 'Capital subscris nevărsat'),
            'rd_31': ('1015', 'Prime de capital'),
            'rd_32': ('1018', 'Alte datorii'),
            'rd_33': ('1031', 'Rezerve din reevaluare'),
            'rd_34': ('104', 'Prime legate de capitaluri proprii'),
            'rd_35': ('105', 'Diferențe de curs valutar'),
            'rd_36': ('106', 'Rezerve'),
            'rd_37': ('141', 'Profit sau pierdere reportată')
        }
        
        for rd_key, (cont, descriere) in capital_sc.items():
            val = SC(cont)
            rezultate[rd_key] = val
            if val != 0:
                logger.info(f"{rd_key} - SC({cont}) [{descriere}] = {val:.2f}")
        
        # Capitaluri cu sold debitor (se scad)
        logger.info("\nCapitaluri cu sold debitor (se scad):")
        capital_sd = {
            'rd_38': ('109', 'Capital subscris nevărsat'),
            'rd_39': ('149', 'Pierderi legate de instrumentele de capitaluri proprii'),
            'rd_40': ('117', 'Diferențe de curs valutar'),
            'rd_41': ('121', 'Profit sau pierdere')
        }
        
        for rd_key, (cont, descriere) in capital_sd.items():
            val = SD(cont)
            rezultate[rd_key] = val
            if val != 0:
                logger.info(f"{rd_key} - SD({cont}) [{descriere}] = -{val:.2f}")

        # Adăugăm rândurile 42-45 (dacă există alte conturi specifice)
        rezultate['rd_42'] = 0
        rezultate['rd_43'] = 0
        rezultate['rd_44'] = 0
        rezultate['rd_45'] = 0

        # TOTAL CAPITAL ȘI REZERVE înainte de repartizare (rd_46)
        rezultate['rd_46'] = sum(rezultate[f'rd_{i}'] for i in range(29, 46))
        logger.info(f"\nTOTAL CAPITAL înainte de repartizare (rd_46) = {rezultate['rd_46']:.2f}")
        
        # Repartizarea profitului (rd_47)
        rezultate['rd_47'] = SC('1016')
        logger.info(f"Repartizarea profitului (rd_47) = {rezultate['rd_47']:.2f}")
        
        # Rezultatul exercițiului (rd_48)
        rezultate['rd_48'] = SC('1017')
        logger.info(f"Rezultatul exercițiului (rd_48) = {rezultate['rd_48']:.2f}")
        
        # CAPITAL ȘI REZERVE - TOTAL (rd_49)
        rezultate['rd_49'] = rezultate['rd_46'] + rezultate['rd_47'] + rezultate['rd_48']
        logger.info(f"\nCAPITAL ȘI REZERVE - TOTAL (rd_49) = {rezultate['rd_49']:.2f}")
        
        logger.info("\n" + "=" * 80)
        logger.info("VERIFICARE ECHILIBRARE BILANȚ")
        logger.info("=" * 80)
        total_active = rezultate['rd_15']
        total_pasive = rezultate['rd_49'] + rezultate['rd_18']
        diferenta = total_active - total_pasive
        logger.info(f"Total Active (rd_15): {total_active:.2f}")
        logger.info(f"Total Pasive (rd_49 + rd_18): {total_pasive:.2f}")
        logger.info(f"Diferență: {diferenta:.2f}")
        logger.info(f"Echilibrat: {'DA' if abs(diferenta) < 0.01 else 'NU'}")
        logger.info("=" * 80 + "\n")

        # Convertim toate valorile în float pentru consistență
        for key in rezultate:
            rezultate[key] = float(rezultate[key] or 0)

    except Exception as e:
        print(f"Eroare în calculul bilanțului: {e}")
        import traceback
        traceback.print_exc()
        return {f'rd_{i}': 0.0 for i in range(1, 50)}

    return rezultate


@login_required(login_url='login')
def dashboard_firma_bilant(request):
    """
    Afișează pagina cu bilanțul contabil.
    """
    firma = request.user
    
    # Configurăm logging pentru a afișa în consolă
    logging.basicConfig(
        level=logging.INFO,
        format='%(message)s',
        force=True
    )
    
    try:
        logger.info("\n" + "=" * 80)
        logger.info(f"CALCULARE BILANȚ PENTRU FIRMA: {firma}")
        logger.info("=" * 80 + "\n")
        
        # Calculăm situația conturilor
        situatie_conturi = SituatieConturi(firma)
        
        # DEBUG: Afișăm situația conturilor dacă este cerut
        if request.GET.get('debug'):
            situatie_conturi.afiseaza_situatie()
        
        # Calculăm bilanțul
        bilant = calculeaza_bilant(situatie_conturi)
        
        # Verificăm dacă bilanțul este echilibrat
        total_active = bilant.get('rd_15', 0)
        total_pasive = bilant.get('rd_49', 0) + bilant.get('rd_18', 0)
        
        diferenta = abs(total_active - total_pasive)
        bilant_echilibrat = diferenta < 0.01  # Toleranță pentru rotunjiri
        
        context = {
            'firma': firma,
            'bilant': bilant,
            'bilant_echilibrat': bilant_echilibrat,
            'total_active': total_active,
            'total_pasive': total_pasive,
            'diferenta': diferenta
        }
        
        return render(request, 'main/dashboard_firma_bilant.html', context)
        
    except Exception as e:
        logger.error(f"EROARE LA AFIȘAREA BILANȚULUI: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        return render(request, 'main/dashboard_firma_bilant.html', {
            'firma': firma,
            'bilant': {},
            'bilant_echilibrat': False,
            'eroare': str(e)
        })


# --- View pentru export Bilanț ---
@login_required(login_url='login')
def export_bilant(request):
    format_ = request.GET.get('format', 'csv')
    firma = request.user

    S = SituatieConturi(firma)
    bilant = calculeaza_bilant(S)

    # --- Export CSV ---
    if format_ == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="bilant.csv"'
        writer = csv.writer(response)
        writer.writerow(['Rând', 'Valoare'])
        for k, v in bilant.items():
            writer.writerow([k, v])
        return response

    # --- Export PDF ---
    elif format_ == 'pdf':
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        data = [['Rând', 'Valoare']] + [[k, v] for k,v in bilant.items()]
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.lightblue),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),
            ('GRID',(0,0),(-1,-1),0.5,colors.grey)
        ]))
        doc.build([Paragraph("Bilanț - Export", styles['Title']), table])
        pdf = buffer.getvalue()
        buffer.close()
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="bilant.pdf"'
        return response

    else:
        return HttpResponse("Format invalid", status=400)




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

