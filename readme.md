 Contabilitate Django

Aplicație web pentru gestionarea contabilității firmelor, construită în Django.
Proiectul oferă funcționalități precum:

- gestionarea jurnalului contabil

- balanță contabilă

- registru financiar

- fișe de cont

- rapoarte PDF

- administrare conturi și firme

- sistem de autentificare și roluri

Funcționalități principale:
    Modul Jurnal:

- introducere operațiuni contabile (debit/credit)

- filtrare după cont, firmă

- export PDF / CSV

validare conturi și balanță în timp real

    Modul Balanță:

- generare balanță sintetică/analitică

- totaluri automate (debit, credit, sold)

- export PDF

    Gestionare conturi

- plan de conturi complet

- adăugare / editare / dezactivare conturi

- tipuri de conturi (activ, pasiv, mixt)

    Rapoarte PDF

- generare PDF folosind ReportLab

- antet firmă, dată, număr pagină

- stilizare profesională

    Autentificare & Roluri:

- administratori

- firma

login/logout, permisiuni Django

    Statistici:

- grafice

- indicatori financiari(modelul altman)

    Tehnologii folosite:

Python 3.12

Django 5.x

MySQL 8.x (prod & dev)

Docker + Docker Compose

Gunicorn (server WSGI producție)

Nginx (opțional pentru deploy)

ReportLab (rapoarte PDF)

Pandas (rapoarte XLSX)


Exemplu pentru .env:

DEBUG=True
SECRET_KEY=cheie_sigura
DB_NAME=db_name
DB_USER=root
DB_PASSWORD=parola_db
DB_HOST=127.0.0.1       
DB_PORT=3306

