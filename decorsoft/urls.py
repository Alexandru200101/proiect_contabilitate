from django.urls import path
from . import views


urlpatterns = [
    # Pagina principală (landing page / dashboard)
    path('', views.main_view, name='main'),

    # Autentificare & înregistrare utilizatori (firma)
    path('login/', views.login_view, name='login'),
    path('signup/', views.signup_view, name='signup'),
    path('logout/', views.custom_logout, name='logout'),

    # Dashboard pentru firmă (după login)
    path('dashboard-firma/', views.dashboard_firma, name='dashboard_firma'),
    path('dashboard-firma-jurnal',views.dashboard_firma_jurnal,name ='dashboard_firma_jurnal'),

    # Gestionare registru jurnal (AJAX)
    path('adauga-registru-ajax/', views.adauga_registru_ajax, name='adauga_registru_ajax'),
    path('modifica-registru-ajax/', views.modifica_registru_ajax, name='modifica_registru_ajax'),
    path('sterge-registru-ajax/', views.sterge_registru_ajax, name='sterge_registru_ajax'),
    path('export-registru/', views.export_registru, name='export_registru'),    
    path('cont-profit-pierdere/', views.cont_profit_pierdere, name='cont_profit_pierdere'),
    path('jurnal/import/', views.import_jurnal_csv, name='import_jurnal_csv'),


    # Gestionare balanta firmă
    path('dashboard-firma-balanta/', views.dashboard_firma_balanta, name='dashboard_firma_balanta'),
    path('export/balanta/', views.export_balanta, name='export_balanta'),

    # Gestionare bilant firmă
    path('dashboard-firma-bilant/', views.dashboard_firma_bilant, name='dashboard_firma_bilant'),
    path('export/bilant/', views.export_bilant, name='export_bilant'),
    
    # Gestionare fisa cont
    path('fisa-cont/', views.dashboard_firma_fisa_cont, name='dashboard_firma_fisa_cont'),
    path('fisa-cont/<str:cont_simbol>/', views.fisa_cont_ajax, name='get_fisa_cont_ajax'),

    # Statistici firmă
    path('statistici/', views.dashboard_firma_statistici, name='dashboard_firma_statistici'),
    path('statistici/export-csv/', views.export_statistici_csv, name='export_statistici_csv'),

    # Administrare firme (doar pentru admin)
    path('admin-login/', views.admin_login_view, name='admin_login'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin-dashboard/firma/<uuid:firma_id>/', views.admin_dashboard_firma, name='admin_dashboard_firma'),
    path('admin-dashboard/firma/<uuid:firma_id>/sterge/', views.sterge_firma, name='sterge_firma'),
    path('admin-logout/', views.custom_logout_admin, name='admin_logout'),

    # Operațiuni firmă (gestionare date)
    path('inregistrare-firma/', views.inregistrare_firma, name='inregistrare_firma'),
    path('afisare-firme/', views.afisare_firme, name='afisare_firme'),
]

