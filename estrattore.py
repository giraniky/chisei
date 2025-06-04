import sys
import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.keys import Keys
from webdriver_manager.chrome import ChromeDriverManager

def risolvi_riferimento(rif):
    rif = rif.upper().strip().split()[0]
    mapping = {
        'N': '@RIFERIMENTON',
        'S': '@RAPTOR97X',
        'L': '@LUCREZIA1223',
        '352-': '@GRILLAZZI',
        '386-': '@MATTIA122',
    }
    for k, v in mapping.items():
        if rif.startswith(k):
            return v
    try:
        with open('legenda_custom.json','r') as f:
            leg = json.load(f)
        for k, v in leg.items():
            if rif.startswith(k.upper()):
                return v
    except:
        pass
    return '❌ Riferimento non configurato'

def semplifica_stato(stato_raw):
    if stato_raw and stato_raw[0].isdigit():
        code = stato_raw[0]
        mapping = {
            '0':'Ordine eliminato',
            '1':'In attesa di recensione',
            '2':'In attesa di rimborso',
            '3':'Rimborsato',
            '4':'Rimborsato',
            '5':'Rimborsato',
            '6':'Rimborsato',
        }
        return mapping.get(code, stato_raw)
    if 'rimborsato' in stato_raw.lower():
        return 'Rimborsato'
    return stato_raw or 'Non disponibile'

def estrai(numero_ordine, ruolo):
    opts = webdriver.ChromeOptions()
    opts.add_argument('--headless')
    opts.add_argument('--no-sandbox')
    opts.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=opts)

    driver.get('https://login.arateam.cloud')
    driver.find_element(By.NAME,'username').send_keys('Sheet')
    driver.find_element(By.NAME,'password').send_keys('SyncSheet'+Keys.RETURN)
    time.sleep(3)
    driver.get('https://login.arateam.cloud/panel/pages/orders/')
    time.sleep(3)
    driver.find_element(By.ID,'orders_searchBar').send_keys(numero_ordine)
    driver.find_element(By.ID,'orders_searchButton').click()
    time.sleep(3)

    row = driver.find_element(By.CSS_SELECTOR,'tbody tr')
    cols = row.find_elements(By.TAG_NAME,'td')
    stato_raw = cols[23].text.strip().splitlines()[0] if cols[23].text else ''
    stato = semplifica_stato(stato_raw)
    data_lines = cols[23].text.strip().splitlines()
    data_rim = next((l for l in data_lines if 'Rimborsato il' in l), 'Non disponibile')
    nome = cols[28].text.strip().splitlines()[0]
    try:
        link = cols[28].find_element(By.TAG_NAME,'a').get_attribute('href')
        agente = f"{nome} {link}"
    except:
        agente = nome
    if ruolo=='cliente':
        result = {'Stato rimborso': stato,'Data rimborso': data_rim,'Agente': agente}
    elif ruolo=='seller':
        result = {'Username agente': agente}
    elif ruolo=='agente':
        rif = cols[29].text.strip()
        seller = risolvi_riferimento(rif)
        result = {'Seller info': f"{rif} {seller}"}
    else:
        result = {'Errore':'Ruolo non valido'}
    driver.quit()
    return result

if __name__=='__main__':
    import argparse, json
    p=argparse.ArgumentParser()
    p.add_argument('ordine'); p.add_argument('ruolo')
    args=p.parse_args()
    data=estrai(args.ordine,args.ruolo)
    print(json.dumps(data))
